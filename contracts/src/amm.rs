use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

declare_id!("MemeMarket1111111111111111111111111111111111");

#[program]
pub mod amm {
    use super::*;

    /// Initialize AMM pool for YES/NO shares
    pub fn initialize_pool(
        ctx: Context<InitializePool>,
        pool_id: Pubkey,
        market_id: Pubkey,
        yes_mint: Pubkey,
        no_mint: Pubkey,
        initial_yes_amount: u64,
        initial_no_amount: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        
        pool.authority = ctx.accounts.authority.key();
        pool.pool_id = pool_id;
        pool.market_id = market_id;
        pool.yes_mint = yes_mint;
        pool.no_mint = no_mint;
        pool.yes_reserves = initial_yes_amount;
        pool.no_reserves = initial_no_amount;
        pool.total_supply = 0;
        pool.fee_numerator = 30; // 0.3% fee
        pool.fee_denominator = 10000;
        pool.created_at = Clock::get()?.unix_timestamp;
        
        // Calculate initial k (constant product)
        pool.k = initial_yes_amount
            .checked_mul(initial_no_amount)
            .unwrap();
        
        emit!(PoolInitialized {
            pool_id,
            market_id,
            yes_reserves: initial_yes_amount,
            no_reserves: initial_no_amount,
            k: pool.k,
        });
        
        Ok(())
    }

    /// Swap YES shares for NO shares
    pub fn swap_yes_for_no(
        ctx: Context<SwapYesForNo>,
        pool_id: Pubkey,
        yes_amount_in: u64,
        minimum_no_out: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        
        require!(yes_amount_in > 0, ErrorCode::InvalidAmount);
        require!(pool.yes_reserves > 0 && pool.no_reserves > 0, ErrorCode::EmptyPool);
        
        // Calculate fee
        let fee = yes_amount_in
            .checked_mul(pool.fee_numerator)
            .unwrap()
            .checked_div(pool.fee_denominator)
            .unwrap();
        
        let yes_amount_after_fee = yes_amount_in.checked_sub(fee).unwrap();
        
        // Calculate output using constant product formula
        let new_yes_reserves = pool.yes_reserves.checked_add(yes_amount_after_fee).unwrap();
        let new_no_reserves = pool.k
            .checked_div(new_yes_reserves)
            .unwrap();
        
        let no_amount_out = pool.no_reserves.checked_sub(new_no_reserves).unwrap();
        
        require!(no_amount_out >= minimum_no_out, ErrorCode::SlippageExceeded);
        
        // Transfer YES shares from user to pool
        let cpi_accounts = Transfer {
            from: ctx.accounts.user_yes_shares.to_account_info(),
            to: ctx.accounts.pool_yes_shares.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, yes_amount_in)?;
        
        // Transfer NO shares from pool to user
        let seeds = &[
            b"pool",
            pool_id.as_ref(),
            &[ctx.bumps.pool],
        ];
        let signer = &[&seeds[..]];
        
        let cpi_accounts = Transfer {
            from: ctx.accounts.pool_no_shares.to_account_info(),
            to: ctx.accounts.user_no_shares.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
        token::transfer(cpi_ctx, no_amount_out)?;
        
        // Update pool state
        pool.yes_reserves = new_yes_reserves;
        pool.no_reserves = new_no_reserves;
        
        emit!(SwapExecuted {
            pool_id,
            user: ctx.accounts.user.key(),
            yes_amount_in,
            no_amount_out,
            fee,
        });
        
        Ok(())
    }

    /// Swap NO shares for YES shares
    pub fn swap_no_for_yes(
        ctx: Context<SwapNoForYes>,
        pool_id: Pubkey,
        no_amount_in: u64,
        minimum_yes_out: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        
        require!(no_amount_in > 0, ErrorCode::InvalidAmount);
        require!(pool.yes_reserves > 0 && pool.no_reserves > 0, ErrorCode::EmptyPool);
        
        // Calculate fee
        let fee = no_amount_in
            .checked_mul(pool.fee_numerator)
            .unwrap()
            .checked_div(pool.fee_denominator)
            .unwrap();
        
        let no_amount_after_fee = no_amount_in.checked_sub(fee).unwrap();
        
        // Calculate output using constant product formula
        let new_no_reserves = pool.no_reserves.checked_add(no_amount_after_fee).unwrap();
        let new_yes_reserves = pool.k
            .checked_div(new_no_reserves)
            .unwrap();
        
        let yes_amount_out = pool.yes_reserves.checked_sub(new_yes_reserves).unwrap();
        
        require!(yes_amount_out >= minimum_yes_out, ErrorCode::SlippageExceeded);
        
        // Transfer NO shares from user to pool
        let cpi_accounts = Transfer {
            from: ctx.accounts.user_no_shares.to_account_info(),
            to: ctx.accounts.pool_no_shares.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, no_amount_in)?;
        
        // Transfer YES shares from pool to user
        let seeds = &[
            b"pool",
            pool_id.as_ref(),
            &[ctx.bumps.pool],
        ];
        let signer = &[&seeds[..]];
        
        let cpi_accounts = Transfer {
            from: ctx.accounts.pool_yes_shares.to_account_info(),
            to: ctx.accounts.user_yes_shares.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
        token::transfer(cpi_ctx, yes_amount_out)?;
        
        // Update pool state
        pool.yes_reserves = new_yes_reserves;
        pool.no_reserves = new_no_reserves;
        
        emit!(SwapExecuted {
            pool_id,
            user: ctx.accounts.user.key(),
            yes_amount_out,
            no_amount_in,
            fee,
        });
        
        Ok(())
    }

    /// Add liquidity to the pool
    pub fn add_liquidity(
        ctx: Context<AddLiquidity>,
        pool_id: Pubkey,
        yes_amount: u64,
        no_amount: u64,
        minimum_lp_tokens: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        
        require!(yes_amount > 0 && no_amount > 0, ErrorCode::InvalidAmount);
        
        // Calculate LP tokens to mint based on current pool size
        let lp_tokens_to_mint = if pool.total_supply == 0 {
            // First liquidity provider gets proportional to initial deposits
            yes_amount.checked_mul(no_amount).unwrap()
        } else {
            // Calculate based on existing reserves
            let yes_ratio = yes_amount
                .checked_mul(pool.total_supply)
                .unwrap()
                .checked_div(pool.yes_reserves)
                .unwrap();
            let no_ratio = no_amount
                .checked_mul(pool.total_supply)
                .unwrap()
                .checked_div(pool.no_reserves)
                .unwrap();
            
            // Use the minimum to maintain ratio
            std::cmp::min(yes_ratio, no_ratio)
        };
        
        require!(lp_tokens_to_mint >= minimum_lp_tokens, ErrorCode::SlippageExceeded);
        
        // Transfer shares from user to pool
        let cpi_accounts = Transfer {
            from: ctx.accounts.user_yes_shares.to_account_info(),
            to: ctx.accounts.pool_yes_shares.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, yes_amount)?;
        
        let cpi_accounts = Transfer {
            from: ctx.accounts.user_no_shares.to_account_info(),
            to: ctx.accounts.pool_no_shares.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, no_amount)?;
        
        // Mint LP tokens
        let seeds = &[
            b"pool",
            pool_id.as_ref(),
            b"lp_mint",
            &[ctx.bumps.lp_mint],
        ];
        let signer = &[&seeds[..]];
        
        let cpi_accounts = token::MintTo {
            mint: ctx.accounts.lp_mint.to_account_info(),
            to: ctx.accounts.user_lp_tokens.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
        token::mint_to(cpi_ctx, lp_tokens_to_mint)?;
        
        // Update pool state
        pool.yes_reserves += yes_amount;
        pool.no_reserves += no_amount;
        pool.k = pool.yes_reserves.checked_mul(pool.no_reserves).unwrap();
        pool.total_supply += lp_tokens_to_mint;
        
        emit!(LiquidityAdded {
            pool_id,
            user: ctx.accounts.user.key(),
            yes_amount,
            no_amount,
            lp_tokens_minted: lp_tokens_to_mint,
        });
        
        Ok(())
    }

    /// Remove liquidity from the pool
    pub fn remove_liquidity(
        ctx: Context<RemoveLiquidity>,
        pool_id: Pubkey,
        lp_amount: u64,
        minimum_yes_out: u64,
        minimum_no_out: u64,
    ) -> Result<()> {
        let pool = &mut ctx.accounts.pool;
        
        require!(lp_amount > 0, ErrorCode::InvalidAmount);
        require!(pool.total_supply > 0, ErrorCode::EmptyPool);
        
        // Calculate proportional amounts
        let yes_amount_out = lp_amount
            .checked_mul(pool.yes_reserves)
            .unwrap()
            .checked_div(pool.total_supply)
            .unwrap();
        
        let no_amount_out = lp_amount
            .checked_mul(pool.no_reserves)
            .unwrap()
            .checked_div(pool.total_supply)
            .unwrap();
        
        require!(yes_amount_out >= minimum_yes_out, ErrorCode::SlippageExceeded);
        require!(no_amount_out >= minimum_no_out, ErrorCode::SlippageExceeded);
        
        // Burn LP tokens
        let seeds = &[
            b"pool",
            pool_id.as_ref(),
            b"lp_mint",
            &[ctx.bumps.lp_mint],
        ];
        let signer = &[&seeds[..]];
        
        let cpi_accounts = token::Burn {
            mint: ctx.accounts.lp_mint.to_account_info(),
            from: ctx.accounts.user_lp_tokens.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
        token::burn(cpi_ctx, lp_amount)?;
        
        // Transfer shares from pool to user
        let seeds = &[
            b"pool",
            pool_id.as_ref(),
            &[ctx.bumps.pool],
        ];
        let signer = &[&seeds[..]];
        
        let cpi_accounts = Transfer {
            from: ctx.accounts.pool_yes_shares.to_account_info(),
            to: ctx.accounts.user_yes_shares.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
        token::transfer(cpi_ctx, yes_amount_out)?;
        
        let cpi_accounts = Transfer {
            from: ctx.accounts.pool_no_shares.to_account_info(),
            to: ctx.accounts.user_no_shares.to_account_info(),
            authority: pool.to_account_info(),
        };
        let cpi_ctx = CpiContext::new_with_signer(cpi_program, cpi_accounts, signer);
        token::transfer(cpi_ctx, no_amount_out)?;
        
        // Update pool state
        pool.yes_reserves -= yes_amount_out;
        pool.no_reserves -= no_amount_out;
        pool.k = pool.yes_reserves.checked_mul(pool.no_reserves).unwrap();
        pool.total_supply -= lp_amount;
        
        emit!(LiquidityRemoved {
            pool_id,
            user: ctx.accounts.user.key(),
            lp_tokens_burned: lp_amount,
            yes_amount_out,
            no_amount_out,
        });
        
        Ok(())
    }

    /// Get current price for YES shares in terms of NO shares
    pub fn get_yes_price(ctx: Context<GetPrice>) -> Result<u64> {
        let pool = &ctx.accounts.pool;
        
        if pool.no_reserves == 0 {
            return Err(ErrorCode::EmptyPool.into());
        }
        
        let price = pool.yes_reserves.checked_div(pool.no_reserves).unwrap();
        Ok(price)
    }

    /// Get current price for NO shares in terms of YES shares
    pub fn get_no_price(ctx: Context<GetPrice>) -> Result<u64> {
        let pool = &ctx.accounts.pool;
        
        if pool.yes_reserves == 0 {
            return Err(ErrorCode::EmptyPool.into());
        }
        
        let price = pool.no_reserves.checked_div(pool.yes_reserves).unwrap();
        Ok(price)
    }
}

// Account structures
#[account]
pub struct AmmPool {
    pub authority: Pubkey,
    pub pool_id: Pubkey,
    pub market_id: Pubkey,
    pub yes_mint: Pubkey,
    pub no_mint: Pubkey,
    pub yes_reserves: u64,
    pub no_reserves: u64,
    pub k: u128, // Constant product
    pub total_supply: u64,
    pub fee_numerator: u64,
    pub fee_denominator: u64,
    pub created_at: i64,
}

// Context structs
#[derive(Accounts)]
#[instruction(pool_id: Pubkey)]
pub struct InitializePool<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    
    #[account(
        init,
        payer = authority,
        space = 8 + 32 + 32 + 32 + 32 + 8 + 8 + 16 + 8 + 8 + 8 + 8,
        seeds = [b"pool", pool_id.as_ref()],
        bump
    )]
    pub pool: Account<'info, AmmPool>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(pool_id: Pubkey)]
pub struct SwapYesForNo<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref()],
        bump
    )]
    pub pool: Account<'info, AmmPool>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref(), b"yes_shares"],
        bump,
        token::mint = yes_mint,
        token::authority = pool,
    )]
    pub pool_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref(), b"no_shares"],
        bump,
        token::mint = no_mint,
        token::authority = pool,
    )]
    pub pool_no_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = yes_mint,
        token::authority = user,
    )]
    pub user_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = no_mint,
        token::authority = user,
    )]
    pub user_no_shares: Box<Account<'info, TokenAccount>>,
    
    pub yes_mint: Box<Account<'info, token::Mint>>,
    pub no_mint: Box<Account<'info, token::Mint>>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
#[instruction(pool_id: Pubkey)]
pub struct SwapNoForYes<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref()],
        bump
    )]
    pub pool: Account<'info, AmmPool>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref(), b"yes_shares"],
        bump,
        token::mint = yes_mint,
        token::authority = pool,
    )]
    pub pool_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref(), b"no_shares"],
        bump,
        token::mint = no_mint,
        token::authority = pool,
    )]
    pub pool_no_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = yes_mint,
        token::authority = user,
    )]
    pub user_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = no_mint,
        token::authority = user,
    )]
    pub user_no_shares: Box<Account<'info, TokenAccount>>,
    
    pub yes_mint: Box<Account<'info, token::Mint>>,
    pub no_mint: Box<Account<'info, token::Mint>>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
#[instruction(pool_id: Pubkey)]
pub struct AddLiquidity<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref()],
        bump
    )]
    pub pool: Account<'info, AmmPool>,
    
    #[account(
        init_if_needed,
        payer = user,
        seeds = [b"pool", pool_id.as_ref(), b"lp_mint"],
        bump,
        mint::decimals = 6,
        mint::authority = pool,
        mint::freeze_authority = pool,
    )]
    pub lp_mint: Box<Account<'info, token::Mint>>,
    
    #[account(
        init_if_needed,
        payer = user,
        seeds = [b"pool", pool_id.as_ref(), b"yes_shares"],
        bump,
        token::mint = yes_mint,
        token::authority = pool,
    )]
    pub pool_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        init_if_needed,
        payer = user,
        seeds = [b"pool", pool_id.as_ref(), b"no_shares"],
        bump,
        token::mint = no_mint,
        token::authority = pool,
    )]
    pub pool_no_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        init_if_needed,
        payer = user,
        seeds = [b"user", user.key().as_ref(), pool_id.as_ref(), b"lp_tokens"],
        bump,
        token::mint = lp_mint,
        token::authority = user,
    )]
    pub user_lp_tokens: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = yes_mint,
        token::authority = user,
    )]
    pub user_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = no_mint,
        token::authority = user,
    )]
    pub user_no_shares: Box<Account<'info, TokenAccount>>,
    
    pub yes_mint: Box<Account<'info, token::Mint>>,
    pub no_mint: Box<Account<'info, token::Mint>>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
#[instruction(pool_id: Pubkey)]
pub struct RemoveLiquidity<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref()],
        bump
    )]
    pub pool: Account<'info, AmmPool>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref(), b"lp_mint"],
        bump
    )]
    pub lp_mint: Box<Account<'info, token::Mint>>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref(), b"yes_shares"],
        bump,
        token::mint = yes_mint,
        token::authority = pool,
    )]
    pub pool_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        seeds = [b"pool", pool_id.as_ref(), b"no_shares"],
        bump,
        token::mint = no_mint,
        token::authority = pool,
    )]
    pub pool_no_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = lp_mint,
        token::authority = user,
    )]
    pub user_lp_tokens: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = yes_mint,
        token::authority = user,
    )]
    pub user_yes_shares: Box<Account<'info, TokenAccount>>,
    
    #[account(
        mut,
        token::mint = no_mint,
        token::authority = user,
    )]
    pub user_no_shares: Box<Account<'info, TokenAccount>>,
    
    pub yes_mint: Box<Account<'info, token::Mint>>,
    pub no_mint: Box<Account<'info, token::Mint>>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct GetPrice<'info> {
    pub pool: Account<'info, AmmPool>,
}

// Error codes
#[error_code]
pub enum ErrorCode {
    #[msg("Invalid amount")]
    InvalidAmount,
    #[msg("Pool is empty")]
    EmptyPool,
    #[msg("Slippage exceeded")]
    SlippageExceeded,
    #[msg("Insufficient liquidity")]
    InsufficientLiquidity,
}

// Events
#[event]
pub struct PoolInitialized {
    pub pool_id: Pubkey,
    pub market_id: Pubkey,
    pub yes_reserves: u64,
    pub no_reserves: u64,
    pub k: u128,
}

#[event]
pub struct SwapExecuted {
    pub pool_id: Pubkey,
    pub user: Pubkey,
    pub yes_amount_in: u64,
    pub no_amount_out: u64,
    pub fee: u64,
}

#[event]
pub struct LiquidityAdded {
    pub pool_id: Pubkey,
    pub user: Pubkey,
    pub yes_amount: u64,
    pub no_amount: u64,
    pub lp_tokens_minted: u64,
}

#[event]
pub struct LiquidityRemoved {
    pub pool_id: Pubkey,
    pub user: Pubkey,
    pub lp_tokens_burned: u64,
    pub yes_amount_out: u64,
    pub no_amount_out: u64,
}
