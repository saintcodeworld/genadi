use anchor_lang::prelude::*;
use anchor_lang::system_program::{transfer, Transfer};

/// Market creation fee: 0.015 SOL in lamports
/// Debug: Fee charged to any user creating a new market
pub const MARKET_CREATION_FEE: u64 = 15_000_000; // 0.015 SOL

/// Parimutuel betting market account structure with automated oracle resolution
/// Debug: Stores pools, target market cap, deadline, and oracle data
#[account]
pub struct Market {
    pub creator: Pubkey,            // User who created the market (paid creation fee)
    pub oracle_authority: Pubkey,   // Oracle/backend authority for signed resolution
    pub token_mint: Pubkey,         // Token to track market cap for
    pub total_yes_pool: u64,        // Total SOL in YES pool (in lamports)
    pub total_no_pool: u64,         // Total SOL in NO pool (in lamports)
    pub target_market_cap: u64,     // Target market cap in USD (with 6 decimals, e.g., 1_000_000_000000 = $1M)
    pub deadline: i64,              // Unix timestamp deadline for market resolution
    pub is_resolved: bool,          // Whether market has been resolved
    pub winner: Option<bool>,       // Winning side: Some(true) = YES, Some(false) = NO
    pub target_reached: bool,       // Whether target was reached before deadline
    pub resolved_at: i64,           // Timestamp when market was resolved
    pub bump: u8,                   // PDA bump seed
}

impl Market {
    /// Calculate space needed for Market account
    /// Debug: 8 (discriminator) + 32 (creator) + 32 (oracle) + 32 (token_mint) + 8 (yes_pool) + 8 (no_pool) 
    ///        + 8 (target_cap) + 8 (deadline) + 1 (is_resolved) + 2 (Option<bool>) + 1 (target_reached) 
    ///        + 8 (resolved_at) + 1 (bump)
    pub const LEN: usize = 8 + 32 + 32 + 32 + 8 + 8 + 8 + 8 + 1 + 2 + 1 + 8 + 1;
}

/// User bet account structure
/// Debug: Tracks individual user's bet amount, side, and claim status
#[account]
pub struct UserBet {
    pub user: Pubkey,            // User who placed the bet
    pub market: Pubkey,          // Market this bet belongs to
    pub amount: u64,             // Amount bet in lamports
    pub side: bool,              // Betting side: true = YES, false = NO
    pub claimed: bool,           // Whether reward has been claimed
}

impl UserBet {
    /// Calculate space needed for UserBet account
    /// Debug: 8 (discriminator) + 32 (user) + 32 (market) + 8 (amount) + 1 (side) + 1 (claimed)
    pub const LEN: usize = 8 + 32 + 32 + 8 + 1 + 1;
}

/// Initialize a new parimutuel market (permissionless)
/// Debug: Any user can create a market by paying 0.015 SOL fee to treasury
#[derive(Accounts)]
#[instruction(market_seed: String)]
pub struct InitializeMarket<'info> {
    #[account(
        init,
        payer = creator,
        space = Market::LEN,
        seeds = [b"market", market_seed.as_bytes()],
        bump
    )]
    pub market: Account<'info, Market>,
    
    /// CHECK: Treasury wallet that receives market creation fees
    #[account(mut)]
    pub treasury: AccountInfo<'info>,
    
    #[account(mut)]
    pub creator: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

/// Place a bet on the market
/// Debug: Transfers SOL from user to market escrow PDA
#[derive(Accounts)]
#[instruction(market_seed: String)]
pub struct PlaceBet<'info> {
    #[account(
        mut,
        seeds = [b"market", market_seed.as_bytes()],
        bump = market.bump
    )]
    pub market: Account<'info, Market>,
    
    #[account(
        init,
        payer = user,
        space = UserBet::LEN,
        seeds = [b"user_bet", market.key().as_ref(), user.key().as_ref()],
        bump
    )]
    pub user_bet: Account<'info, UserBet>,
    
    /// CHECK: Market escrow PDA that holds all bet funds
    #[account(
        mut,
        seeds = [b"escrow", market.key().as_ref()],
        bump
    )]
    pub escrow: AccountInfo<'info>,
    
    #[account(mut)]
    pub user: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

/// Resolve the market with oracle data and signature verification
/// Debug: Oracle provides signed message with current market cap and timestamp
#[derive(Accounts)]
#[instruction(market_seed: String)]
pub struct ResolveMarket<'info> {
    #[account(
        mut,
        seeds = [b"market", market_seed.as_bytes()],
        bump = market.bump
    )]
    pub market: Account<'info, Market>,
    
    /// CHECK: Oracle authority that signs the resolution data
    pub oracle: Signer<'info>,
}

/// Claim reward after market resolution
/// Debug: Calculates proportional payout using u128 to prevent overflow
#[derive(Accounts)]
#[instruction(market_seed: String)]
pub struct ClaimReward<'info> {
    #[account(
        mut,
        seeds = [b"market", market_seed.as_bytes()],
        bump = market.bump
    )]
    pub market: Account<'info, Market>,
    
    #[account(
        mut,
        seeds = [b"user_bet", market.key().as_ref(), user.key().as_ref()],
        bump,
        constraint = user_bet.user == user.key() @ ParimutuelError::Unauthorized,
        constraint = user_bet.market == market.key() @ ParimutuelError::InvalidMarket
    )]
    pub user_bet: Account<'info, UserBet>,
    
    /// CHECK: Market escrow PDA that holds all bet funds
    #[account(
        mut,
        seeds = [b"escrow", market.key().as_ref()],
        bump
    )]
    pub escrow: AccountInfo<'info>,
    
    #[account(mut)]
    pub user: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

/// Initialize a new parimutuel market with oracle-based resolution (permissionless)
/// Debug: Any user can create a market by paying 0.015 SOL fee to treasury
pub fn initialize_market(
    ctx: Context<InitializeMarket>,
    _market_seed: String,
    oracle_authority: Pubkey,
    token_mint: Pubkey,
    target_market_cap: u64,
    deadline: i64,
) -> Result<()> {
    let market = &mut ctx.accounts.market;
    let current_time = Clock::get()?.unix_timestamp;
    
    require!(deadline > current_time, ParimutuelError::InvalidDeadline);
    require!(target_market_cap > 0, ParimutuelError::InvalidAmount);
    
    let creator_balance = ctx.accounts.creator.lamports();
    let rent_exempt_balance = Rent::get()?.minimum_balance(Market::LEN);
    let total_required = MARKET_CREATION_FEE
        .checked_add(rent_exempt_balance)
        .ok_or(ParimutuelError::Overflow)?;
    
    require!(
        creator_balance >= total_required,
        ParimutuelError::InsufficientFunds
    );
    
    msg!("DEBUG: Transferring {} lamports creation fee to treasury", MARKET_CREATION_FEE);
    
    let cpi_context = CpiContext::new(
        ctx.accounts.system_program.to_account_info(),
        Transfer {
            from: ctx.accounts.creator.to_account_info(),
            to: ctx.accounts.treasury.to_account_info(),
        },
    );
    transfer(cpi_context, MARKET_CREATION_FEE)?;
    
    market.creator = ctx.accounts.creator.key();
    market.oracle_authority = oracle_authority;
    market.token_mint = token_mint;
    market.total_yes_pool = 0;
    market.total_no_pool = 0;
    market.target_market_cap = target_market_cap;
    market.deadline = deadline;
    market.is_resolved = false;
    market.winner = None;
    market.target_reached = false;
    market.resolved_at = 0;
    market.bump = ctx.bumps.market;
    
    msg!("DEBUG: Parimutuel market initialized (permissionless)");
    msg!("DEBUG: Creator: {}", market.creator);
    msg!("DEBUG: Creation fee paid: {} lamports (0.015 SOL)", MARKET_CREATION_FEE);
    msg!("DEBUG: Treasury: {}", ctx.accounts.treasury.key());
    msg!("DEBUG: Oracle: {}", oracle_authority);
    msg!("DEBUG: Token: {}", token_mint);
    msg!("DEBUG: Target Market Cap: ${}", target_market_cap as f64 / 1_000_000.0);
    msg!("DEBUG: Deadline: {}", deadline);
    
    Ok(())
}

/// Place a bet on YES or NO side
/// Debug: No fixed limit - pools grow indefinitely as users bet
pub fn place_bet(
    ctx: Context<PlaceBet>,
    _market_seed: String,
    amount: u64,
    side: bool,
) -> Result<()> {
    let market = &mut ctx.accounts.market;
    let user_bet = &mut ctx.accounts.user_bet;
    let current_time = Clock::get()?.unix_timestamp;
    
    require!(!market.is_resolved, ParimutuelError::MarketResolved);
    
    require!(current_time < market.deadline, ParimutuelError::DeadlinePassed);
    
    require!(amount > 0, ParimutuelError::InvalidAmount);
    
    // Debug: Transfer SOL from user to escrow PDA
    msg!("DEBUG: Transferring {} lamports from user to escrow", amount);
    
    let cpi_context = CpiContext::new(
        ctx.accounts.system_program.to_account_info(),
        Transfer {
            from: ctx.accounts.user.to_account_info(),
            to: ctx.accounts.escrow.to_account_info(),
        },
    );
    transfer(cpi_context, amount)?;
    
    // Update pool totals based on side
    if side {
        market.total_yes_pool = market.total_yes_pool
            .checked_add(amount)
            .ok_or(ParimutuelError::Overflow)?;
        msg!("DEBUG: YES pool updated to {} lamports", market.total_yes_pool);
    } else {
        market.total_no_pool = market.total_no_pool
            .checked_add(amount)
            .ok_or(ParimutuelError::Overflow)?;
        msg!("DEBUG: NO pool updated to {} lamports", market.total_no_pool);
    }
    
    // Initialize user bet record
    user_bet.user = ctx.accounts.user.key();
    user_bet.market = market.key();
    user_bet.amount = amount;
    user_bet.side = side;
    user_bet.claimed = false;
    
    msg!("DEBUG: User {} placed {} lamports on {}", 
        ctx.accounts.user.key(), 
        amount, 
        if side { "YES" } else { "NO" }
    );
    
    Ok(())
}

/// Resolve the market with oracle-provided market cap data
/// Debug: Oracle (crank) provides current market cap and verifies against target/deadline
pub fn resolve_market(
    ctx: Context<ResolveMarket>,
    _market_seed: String,
    current_market_cap: u64,
    timestamp: i64,
) -> Result<()> {
    let market = &mut ctx.accounts.market;
    let current_time = Clock::get()?.unix_timestamp;
    
    require!(
        ctx.accounts.oracle.key() == market.oracle_authority,
        ParimutuelError::Unauthorized
    );
    
    require!(!market.is_resolved, ParimutuelError::MarketAlreadyResolved);
    
    require!(
        timestamp <= current_time + 300,
        ParimutuelError::StaleData
    );
    
    let target_reached = current_market_cap >= market.target_market_cap;
    let deadline_passed = current_time >= market.deadline;
    
    require!(
        target_reached || deadline_passed,
        ParimutuelError::CannotResolveYet
    );
    
    let winner = if target_reached {
        true
    } else {
        false
    };
    
    market.is_resolved = true;
    market.winner = Some(winner);
    market.target_reached = target_reached;
    market.resolved_at = current_time;
    
    msg!("DEBUG: Market resolved by oracle");
    msg!("DEBUG: Current Market Cap: ${}", current_market_cap as f64 / 1_000_000.0);
    msg!("DEBUG: Target Market Cap: ${}", market.target_market_cap as f64 / 1_000_000.0);
    msg!("DEBUG: Target Reached: {}", target_reached);
    msg!("DEBUG: Deadline Passed: {}", deadline_passed);
    msg!("DEBUG: Winner: {}", if winner { "YES" } else { "NO" });
    msg!("DEBUG: Total YES pool: {} lamports", market.total_yes_pool);
    msg!("DEBUG: Total NO pool: {} lamports", market.total_no_pool);
    
    Ok(())
}

/// Claim proportional reward after market resolution
/// Debug: Uses u128 for calculations to prevent overflow with large amounts
pub fn claim_reward(
    ctx: Context<ClaimReward>,
    _market_seed: String,
) -> Result<()> {
    let market = &ctx.accounts.market;
    let user_bet = &mut ctx.accounts.user_bet;
    
    // Validation: Market must be resolved
    require!(market.is_resolved, ParimutuelError::MarketNotResolved);
    
    // Validation: User must not have already claimed
    require!(!user_bet.claimed, ParimutuelError::AlreadyClaimed);
    
    // Validation: User must be on winning side
    let winner = market.winner.ok_or(ParimutuelError::NoWinner)?;
    require!(user_bet.side == winner, ParimutuelError::NotWinner);
    
    // Calculate proportional reward using u128 to prevent overflow
    // Formula: Reward = (User's Bet / Winning Pool) × Total Pool
    let winning_pool = if winner {
        market.total_yes_pool
    } else {
        market.total_no_pool
    };
    
    let total_pool = market.total_yes_pool
        .checked_add(market.total_no_pool)
        .ok_or(ParimutuelError::Overflow)?;
    
    // Debug: Use u128 for precise calculation with large numbers
    msg!("DEBUG: Calculating reward - User bet: {}, Winning pool: {}, Total pool: {}", 
        user_bet.amount, winning_pool, total_pool);
    
    require!(winning_pool > 0, ParimutuelError::EmptyPool);
    
    // Reward = (user_amount * total_pool) / winning_pool
    let reward = (user_bet.amount as u128)
        .checked_mul(total_pool as u128)
        .ok_or(ParimutuelError::Overflow)?
        .checked_div(winning_pool as u128)
        .ok_or(ParimutuelError::DivisionByZero)?;
    
    let reward_lamports = u64::try_from(reward)
        .map_err(|_| ParimutuelError::Overflow)?;
    
    msg!("DEBUG: Calculated reward: {} lamports", reward_lamports);
    
    // Transfer reward from escrow to user
    let market_key = market.key();
    let escrow_seeds = &[
        b"escrow",
        market_key.as_ref(),
        &[ctx.bumps.escrow],
    ];
    let signer_seeds = &[&escrow_seeds[..]];
    
    let cpi_context = CpiContext::new_with_signer(
        ctx.accounts.system_program.to_account_info(),
        Transfer {
            from: ctx.accounts.escrow.to_account_info(),
            to: ctx.accounts.user.to_account_info(),
        },
        signer_seeds,
    );
    transfer(cpi_context, reward_lamports)?;
    
    // Mark as claimed
    user_bet.claimed = true;
    
    msg!("DEBUG: Reward of {} lamports claimed by user {}", 
        reward_lamports, 
        ctx.accounts.user.key()
    );
    
    Ok(())
}

/// Custom error codes for parimutuel betting
/// Debug: Specific errors for better debugging and user feedback
#[error_code]
pub enum ParimutuelError {
    #[msg("Unauthorized: Only admin can perform this action")]
    Unauthorized,
    
    #[msg("Market has already been resolved")]
    MarketResolved,
    
    #[msg("Market has already been resolved")]
    MarketAlreadyResolved,
    
    #[msg("Market has not been resolved yet")]
    MarketNotResolved,
    
    #[msg("Invalid amount: Must be greater than zero")]
    InvalidAmount,
    
    #[msg("Reward already claimed")]
    AlreadyClaimed,
    
    #[msg("User is not on the winning side")]
    NotWinner,
    
    #[msg("No winner set for this market")]
    NoWinner,
    
    #[msg("Winning pool is empty")]
    EmptyPool,
    
    #[msg("Arithmetic overflow occurred")]
    Overflow,
    
    #[msg("Division by zero")]
    DivisionByZero,
    
    #[msg("Invalid market")]
    InvalidMarket,
    
    #[msg("Invalid deadline: Must be in the future")]
    InvalidDeadline,
    
    #[msg("Deadline has passed: Cannot place bets")]
    DeadlinePassed,
    
    #[msg("Oracle data is stale: Timestamp too old")]
    StaleData,
    
    #[msg("Cannot resolve yet: Target not reached and deadline not passed")]
    CannotResolveYet,
    
    #[msg("Insufficient funds: Need 0.015 SOL + rent for market creation")]
    InsufficientFunds,
}
