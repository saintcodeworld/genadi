use anchor_lang::prelude::*;
use anchor_lang::system_program;

declare_id!("MemeMarketCLOB111111111111111111111111111111");

/// Price precision: 1_000_000 = $1.00 (6 decimals like USDC)
/// This allows prices from $0.000001 to $1.000000
pub const PRICE_PRECISION: u64 = 1_000_000;

/// Default SOL equivalent of $1 in lamports (will be updated by oracle)
/// At ~$130/SOL: 1 SOL = 1_000_000_000 lamports, so $1 ≈ 7_692_308 lamports
pub const DEFAULT_ONE_DOLLAR_LAMPORTS: u64 = 7_700_000; // ~$1 at $130/SOL

#[program]
pub mod orderbook {
    use super::*;

    /// Initialize the order book for a market
    /// Debug: Creates order book with configurable SOL price
    pub fn initialize_orderbook(
        ctx: Context<InitializeOrderbook>,
        market_id: Pubkey,
        one_dollar_lamports: u64, // SOL equivalent of $1 in lamports
    ) -> Result<()> {
        let orderbook = &mut ctx.accounts.orderbook;
        
        orderbook.authority = ctx.accounts.authority.key();
        orderbook.market_id = market_id;
        orderbook.one_dollar_lamports = one_dollar_lamports;
        orderbook.yes_order_count = 0;
        orderbook.no_order_count = 0;
        orderbook.total_yes_shares = 0;
        orderbook.total_no_shares = 0;
        orderbook.total_volume_lamports = 0;
        orderbook.last_yes_price = PRICE_PRECISION / 2; // Start at 50%
        orderbook.last_no_price = PRICE_PRECISION / 2;  // Start at 50%
        orderbook.created_at = Clock::get()?.unix_timestamp;
        orderbook.is_active = true;
        
        // Debug: Log orderbook initialization
        msg!("DEBUG: Orderbook initialized for market {:?}", market_id);
        msg!("DEBUG: 1 USD = {} lamports", one_dollar_lamports);
        
        emit!(OrderbookInitialized {
            market_id,
            one_dollar_lamports,
            timestamp: orderbook.created_at,
        });
        
        Ok(())
    }

    /// Update SOL price (called by oracle or admin)
    /// Debug: Allows updating the SOL/USD exchange rate
    pub fn update_sol_price(
        ctx: Context<UpdateSolPrice>,
        new_one_dollar_lamports: u64,
    ) -> Result<()> {
        let orderbook = &mut ctx.accounts.orderbook;
        
        require!(
            ctx.accounts.authority.key() == orderbook.authority,
            ErrorCode::Unauthorized
        );
        require!(new_one_dollar_lamports > 0, ErrorCode::InvalidAmount);
        
        let old_price = orderbook.one_dollar_lamports;
        orderbook.one_dollar_lamports = new_one_dollar_lamports;
        
        // Debug: Log price update
        msg!("DEBUG: SOL price updated from {} to {} lamports/$1", old_price, new_one_dollar_lamports);
        
        emit!(SolPriceUpdated {
            market_id: orderbook.market_id,
            old_lamports_per_dollar: old_price,
            new_lamports_per_dollar: new_one_dollar_lamports,
            timestamp: Clock::get()?.unix_timestamp,
        });
        
        Ok(())
    }

    /// Place a limit order to buy YES or NO shares
    /// Core Polymarket rule: YES price + NO price = $1
    /// Debug: Creates order and attempts matching
    pub fn place_order(
        ctx: Context<PlaceOrder>,
        order_id: Pubkey,
        side: OrderSide,      // YES or NO
        price: u64,           // Price in PRICE_PRECISION units (0-1_000_000)
        quantity: u64,        // Number of shares to buy
    ) -> Result<()> {
        let orderbook = &mut ctx.accounts.orderbook;
        let order = &mut ctx.accounts.order;
        let user = &ctx.accounts.user;
        
        require!(orderbook.is_active, ErrorCode::OrderbookInactive);
        require!(price > 0 && price < PRICE_PRECISION, ErrorCode::InvalidPrice);
        require!(quantity > 0, ErrorCode::InvalidAmount);
        
        // Calculate required SOL collateral for this order
        // cost = (price / PRICE_PRECISION) * quantity * one_dollar_lamports
        let cost_lamports = price
            .checked_mul(quantity)
            .ok_or(ErrorCode::MathOverflow)?
            .checked_mul(orderbook.one_dollar_lamports)
            .ok_or(ErrorCode::MathOverflow)?
            .checked_div(PRICE_PRECISION)
            .ok_or(ErrorCode::MathOverflow)?;
        
        // Debug: Log order details
        msg!("DEBUG: Placing {} order - price: {}, qty: {}, cost: {} lamports", 
            if side == OrderSide::Yes { "YES" } else { "NO" },
            price, quantity, cost_lamports);
        
        // Transfer SOL from user to orderbook vault
        let cpi_context = CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: user.to_account_info(),
                to: ctx.accounts.vault.to_account_info(),
            },
        );
        system_program::transfer(cpi_context, cost_lamports)?;
        
        // Initialize order
        order.order_id = order_id;
        order.owner = user.key();
        order.market_id = orderbook.market_id;
        order.side = side.clone();
        order.price = price;
        order.original_quantity = quantity;
        order.filled_quantity = 0;
        order.remaining_quantity = quantity;
        order.lamports_deposited = cost_lamports;
        order.status = OrderStatus::Open;
        order.created_at = Clock::get()?.unix_timestamp;
        
        // Update orderbook counts
        match side {
            OrderSide::Yes => orderbook.yes_order_count += 1,
            OrderSide::No => orderbook.no_order_count += 1,
        }
        
        emit!(OrderPlaced {
            order_id,
            owner: user.key(),
            market_id: orderbook.market_id,
            side: side.clone(),
            price,
            quantity,
            cost_lamports,
            timestamp: order.created_at,
        });
        
        Ok(())
    }

    /// Match orders: When YES price + NO price = $1, mint shares
    /// This is the core Polymarket mechanism
    /// Debug: Matches two complementary orders and mints shares
    pub fn match_orders(
        ctx: Context<MatchOrders>,
    ) -> Result<()> {
        let orderbook = &mut ctx.accounts.orderbook;
        let yes_order = &mut ctx.accounts.yes_order;
        let no_order = &mut ctx.accounts.no_order;
        
        require!(orderbook.is_active, ErrorCode::OrderbookInactive);
        require!(yes_order.side == OrderSide::Yes, ErrorCode::InvalidOrderSide);
        require!(no_order.side == OrderSide::No, ErrorCode::InvalidOrderSide);
        require!(yes_order.status == OrderStatus::Open, ErrorCode::OrderNotOpen);
        require!(no_order.status == OrderStatus::Open, ErrorCode::OrderNotOpen);
        require!(yes_order.market_id == no_order.market_id, ErrorCode::MarketMismatch);
        
        // Core rule: YES price + NO price must equal $1 (PRICE_PRECISION)
        let combined_price = yes_order.price.checked_add(no_order.price)
            .ok_or(ErrorCode::MathOverflow)?;
        
        require!(combined_price == PRICE_PRECISION, ErrorCode::PricesMustSumToOne);
        
        // Calculate match quantity (minimum of both remaining quantities)
        let match_quantity = std::cmp::min(
            yes_order.remaining_quantity,
            no_order.remaining_quantity
        );
        
        require!(match_quantity > 0, ErrorCode::NoMatchQuantity);
        
        // Debug: Log match details
        msg!("DEBUG: Matching orders - YES price: {}, NO price: {}, qty: {}",
            yes_order.price, no_order.price, match_quantity);
        
        // Update YES order
        yes_order.filled_quantity += match_quantity;
        yes_order.remaining_quantity -= match_quantity;
        if yes_order.remaining_quantity == 0 {
            yes_order.status = OrderStatus::Filled;
        } else {
            yes_order.status = OrderStatus::PartiallyFilled;
        }
        
        // Update NO order
        no_order.filled_quantity += match_quantity;
        no_order.remaining_quantity -= match_quantity;
        if no_order.remaining_quantity == 0 {
            no_order.status = OrderStatus::Filled;
        } else {
            no_order.status = OrderStatus::PartiallyFilled;
        }
        
        // Mint shares to respective owners
        // YES shares go to yes_order.owner
        // NO shares go to no_order.owner
        let yes_user_shares = &mut ctx.accounts.yes_user_shares;
        let no_user_shares = &mut ctx.accounts.no_user_shares;
        
        yes_user_shares.owner = yes_order.owner;
        yes_user_shares.market_id = orderbook.market_id;
        yes_user_shares.yes_shares += match_quantity;
        
        no_user_shares.owner = no_order.owner;
        no_user_shares.market_id = orderbook.market_id;
        no_user_shares.no_shares += match_quantity;
        
        // Update orderbook state
        orderbook.total_yes_shares += match_quantity;
        orderbook.total_no_shares += match_quantity;
        orderbook.last_yes_price = yes_order.price;
        orderbook.last_no_price = no_order.price;
        
        // Calculate volume in lamports
        let volume = match_quantity
            .checked_mul(orderbook.one_dollar_lamports)
            .ok_or(ErrorCode::MathOverflow)?;
        orderbook.total_volume_lamports += volume;
        
        emit!(OrdersMatched {
            yes_order_id: yes_order.order_id,
            no_order_id: no_order.order_id,
            market_id: orderbook.market_id,
            yes_owner: yes_order.owner,
            no_owner: no_order.owner,
            yes_price: yes_order.price,
            no_price: no_order.price,
            quantity: match_quantity,
            timestamp: Clock::get()?.unix_timestamp,
        });
        
        Ok(())
    }

    /// Sell shares back (merge operation)
    /// When user sells YES and another sells NO at complementary prices,
    /// shares are burned and SOL is returned
    /// Debug: Burns shares and returns SOL to sellers
    pub fn sell_shares(
        ctx: Context<SellShares>,
        sell_order_id: Pubkey,
        side: OrderSide,
        price: u64,
        quantity: u64,
    ) -> Result<()> {
        let orderbook = &mut ctx.accounts.orderbook;
        let user_shares = &mut ctx.accounts.user_shares;
        let sell_order = &mut ctx.accounts.sell_order;
        
        require!(orderbook.is_active, ErrorCode::OrderbookInactive);
        require!(price > 0 && price < PRICE_PRECISION, ErrorCode::InvalidPrice);
        require!(quantity > 0, ErrorCode::InvalidAmount);
        
        // Verify user has enough shares
        match side {
            OrderSide::Yes => {
                require!(user_shares.yes_shares >= quantity, ErrorCode::InsufficientShares);
            },
            OrderSide::No => {
                require!(user_shares.no_shares >= quantity, ErrorCode::InsufficientShares);
            },
        }
        
        // Debug: Log sell order
        msg!("DEBUG: Selling {} {} shares at price {}",
            quantity,
            if side == OrderSide::Yes { "YES" } else { "NO" },
            price);
        
        // Create sell order
        sell_order.order_id = sell_order_id;
        sell_order.owner = ctx.accounts.user.key();
        sell_order.market_id = orderbook.market_id;
        sell_order.side = side.clone();
        sell_order.price = price;
        sell_order.original_quantity = quantity;
        sell_order.filled_quantity = 0;
        sell_order.remaining_quantity = quantity;
        sell_order.lamports_deposited = 0; // Seller deposits shares, not SOL
        sell_order.status = OrderStatus::Open;
        sell_order.is_sell = true;
        sell_order.created_at = Clock::get()?.unix_timestamp;
        
        // Lock the shares (mark as pending sale)
        match side {
            OrderSide::Yes => {
                user_shares.yes_shares_locked += quantity;
            },
            OrderSide::No => {
                user_shares.no_shares_locked += quantity;
            },
        }
        
        emit!(SellOrderPlaced {
            order_id: sell_order_id,
            owner: ctx.accounts.user.key(),
            market_id: orderbook.market_id,
            side,
            price,
            quantity,
            timestamp: sell_order.created_at,
        });
        
        Ok(())
    }

    /// Match sell orders (merge shares)
    /// When YES seller + NO seller prices sum to $1, burn shares and pay out SOL
    /// Debug: Burns shares from both parties and returns SOL
    pub fn match_sell_orders(
        ctx: Context<MatchSellOrders>,
    ) -> Result<()> {
        let orderbook = &mut ctx.accounts.orderbook;
        let yes_sell_order = &mut ctx.accounts.yes_sell_order;
        let no_sell_order = &mut ctx.accounts.no_sell_order;
        let yes_user_shares = &mut ctx.accounts.yes_user_shares;
        let no_user_shares = &mut ctx.accounts.no_user_shares;
        
        require!(orderbook.is_active, ErrorCode::OrderbookInactive);
        require!(yes_sell_order.is_sell && no_sell_order.is_sell, ErrorCode::NotASellOrder);
        require!(yes_sell_order.side == OrderSide::Yes, ErrorCode::InvalidOrderSide);
        require!(no_sell_order.side == OrderSide::No, ErrorCode::InvalidOrderSide);
        require!(yes_sell_order.status == OrderStatus::Open, ErrorCode::OrderNotOpen);
        require!(no_sell_order.status == OrderStatus::Open, ErrorCode::OrderNotOpen);
        
        // Core rule: YES price + NO price must equal $1
        let combined_price = yes_sell_order.price.checked_add(no_sell_order.price)
            .ok_or(ErrorCode::MathOverflow)?;
        require!(combined_price == PRICE_PRECISION, ErrorCode::PricesMustSumToOne);
        
        // Calculate match quantity
        let match_quantity = std::cmp::min(
            yes_sell_order.remaining_quantity,
            no_sell_order.remaining_quantity
        );
        
        require!(match_quantity > 0, ErrorCode::NoMatchQuantity);
        
        // Debug: Log merge operation
        msg!("DEBUG: Merging shares - YES price: {}, NO price: {}, qty: {}",
            yes_sell_order.price, no_sell_order.price, match_quantity);
        
        // Calculate payouts
        let yes_payout = yes_sell_order.price
            .checked_mul(match_quantity)
            .ok_or(ErrorCode::MathOverflow)?
            .checked_mul(orderbook.one_dollar_lamports)
            .ok_or(ErrorCode::MathOverflow)?
            .checked_div(PRICE_PRECISION)
            .ok_or(ErrorCode::MathOverflow)?;
        
        let no_payout = no_sell_order.price
            .checked_mul(match_quantity)
            .ok_or(ErrorCode::MathOverflow)?
            .checked_mul(orderbook.one_dollar_lamports)
            .ok_or(ErrorCode::MathOverflow)?
            .checked_div(PRICE_PRECISION)
            .ok_or(ErrorCode::MathOverflow)?;
        
        // Burn shares
        yes_user_shares.yes_shares -= match_quantity;
        yes_user_shares.yes_shares_locked -= match_quantity;
        no_user_shares.no_shares -= match_quantity;
        no_user_shares.no_shares_locked -= match_quantity;
        
        // Update orderbook
        orderbook.total_yes_shares -= match_quantity;
        orderbook.total_no_shares -= match_quantity;
        
        // Update orders
        yes_sell_order.filled_quantity += match_quantity;
        yes_sell_order.remaining_quantity -= match_quantity;
        if yes_sell_order.remaining_quantity == 0 {
            yes_sell_order.status = OrderStatus::Filled;
        }
        
        no_sell_order.filled_quantity += match_quantity;
        no_sell_order.remaining_quantity -= match_quantity;
        if no_sell_order.remaining_quantity == 0 {
            no_sell_order.status = OrderStatus::Filled;
        }
        
        // Transfer SOL from vault to sellers
        // Note: In production, use proper PDA signing for vault transfers
        **ctx.accounts.vault.try_borrow_mut_lamports()? -= yes_payout + no_payout;
        **ctx.accounts.yes_seller.try_borrow_mut_lamports()? += yes_payout;
        **ctx.accounts.no_seller.try_borrow_mut_lamports()? += no_payout;
        
        emit!(SharesMerged {
            yes_order_id: yes_sell_order.order_id,
            no_order_id: no_sell_order.order_id,
            market_id: orderbook.market_id,
            yes_seller: yes_sell_order.owner,
            no_seller: no_sell_order.owner,
            quantity: match_quantity,
            yes_payout,
            no_payout,
            timestamp: Clock::get()?.unix_timestamp,
        });
        
        Ok(())
    }

    /// Cancel an open order and refund SOL
    /// Debug: Cancels order and returns deposited SOL
    pub fn cancel_order(
        ctx: Context<CancelOrder>,
    ) -> Result<()> {
        let order = &mut ctx.accounts.order;
        let user = &ctx.accounts.user;
        
        require!(order.owner == user.key(), ErrorCode::Unauthorized);
        require!(
            order.status == OrderStatus::Open || order.status == OrderStatus::PartiallyFilled,
            ErrorCode::OrderNotCancellable
        );
        
        // Calculate refund for unfilled portion
        let refund_ratio = order.remaining_quantity as u128 * 1_000_000 / order.original_quantity as u128;
        let refund_lamports = (order.lamports_deposited as u128 * refund_ratio / 1_000_000) as u64;
        
        // Debug: Log cancellation
        msg!("DEBUG: Cancelling order {:?}, refunding {} lamports", 
            order.order_id, refund_lamports);
        
        // Transfer refund from vault to user
        **ctx.accounts.vault.try_borrow_mut_lamports()? -= refund_lamports;
        **user.try_borrow_mut_lamports()? += refund_lamports;
        
        order.status = OrderStatus::Cancelled;
        
        emit!(OrderCancelled {
            order_id: order.order_id,
            owner: user.key(),
            refund_lamports,
            timestamp: Clock::get()?.unix_timestamp,
        });
        
        Ok(())
    }

    /// Redeem winning shares after market resolution
    /// Winners get $1 per share, losers get $0
    /// Debug: Pays out winners after market resolution
    pub fn redeem_shares(
        ctx: Context<RedeemShares>,
        winning_outcome: OrderSide,
    ) -> Result<()> {
        let orderbook = &ctx.accounts.orderbook;
        let user_shares = &mut ctx.accounts.user_shares;
        let user = &ctx.accounts.user;
        
        require!(!orderbook.is_active, ErrorCode::MarketStillActive);
        require!(user_shares.owner == user.key(), ErrorCode::Unauthorized);
        
        let shares_to_redeem = match winning_outcome {
            OrderSide::Yes => user_shares.yes_shares,
            OrderSide::No => user_shares.no_shares,
        };
        
        require!(shares_to_redeem > 0, ErrorCode::NoSharesToRedeem);
        
        // Winning shares are worth $1 each
        let payout = shares_to_redeem
            .checked_mul(orderbook.one_dollar_lamports)
            .ok_or(ErrorCode::MathOverflow)?;
        
        // Debug: Log redemption
        msg!("DEBUG: Redeeming {} {} shares for {} lamports",
            shares_to_redeem,
            if winning_outcome == OrderSide::Yes { "YES" } else { "NO" },
            payout);
        
        // Zero out shares
        match winning_outcome {
            OrderSide::Yes => user_shares.yes_shares = 0,
            OrderSide::No => user_shares.no_shares = 0,
        }
        
        // Transfer payout
        **ctx.accounts.vault.try_borrow_mut_lamports()? -= payout;
        **user.try_borrow_mut_lamports()? += payout;
        
        emit!(SharesRedeemed {
            owner: user.key(),
            market_id: orderbook.market_id,
            winning_outcome,
            shares_redeemed: shares_to_redeem,
            payout_lamports: payout,
            timestamp: Clock::get()?.unix_timestamp,
        });
        
        Ok(())
    }
}

// ============================================================================
// Account Structures
// ============================================================================

#[account]
pub struct Orderbook {
    pub authority: Pubkey,
    pub market_id: Pubkey,
    pub one_dollar_lamports: u64,    // SOL equivalent of $1
    pub yes_order_count: u64,
    pub no_order_count: u64,
    pub total_yes_shares: u64,       // Total YES shares in circulation
    pub total_no_shares: u64,        // Total NO shares in circulation
    pub total_volume_lamports: u64,  // Total trading volume
    pub last_yes_price: u64,         // Last matched YES price
    pub last_no_price: u64,          // Last matched NO price
    pub created_at: i64,
    pub is_active: bool,
}

#[account]
pub struct Order {
    pub order_id: Pubkey,
    pub owner: Pubkey,
    pub market_id: Pubkey,
    pub side: OrderSide,
    pub price: u64,                  // Price in PRICE_PRECISION units
    pub original_quantity: u64,
    pub filled_quantity: u64,
    pub remaining_quantity: u64,
    pub lamports_deposited: u64,
    pub status: OrderStatus,
    pub is_sell: bool,               // true if selling shares, false if buying
    pub created_at: i64,
}

#[account]
pub struct UserShares {
    pub owner: Pubkey,
    pub market_id: Pubkey,
    pub yes_shares: u64,
    pub no_shares: u64,
    pub yes_shares_locked: u64,      // Locked in pending sell orders
    pub no_shares_locked: u64,       // Locked in pending sell orders
}

// ============================================================================
// Enums
// ============================================================================

#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq)]
pub enum OrderSide {
    Yes,
    No,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone, PartialEq, Eq)]
pub enum OrderStatus {
    Open,
    PartiallyFilled,
    Filled,
    Cancelled,
}

// ============================================================================
// Context Structs
// ============================================================================

#[derive(Accounts)]
#[instruction(market_id: Pubkey)]
pub struct InitializeOrderbook<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    
    #[account(
        init,
        payer = authority,
        space = 8 + 32 + 32 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 8 + 1,
        seeds = [b"orderbook", market_id.as_ref()],
        bump
    )]
    pub orderbook: Account<'info, Orderbook>,
    
    /// CHECK: Vault PDA for holding SOL collateral
    #[account(
        mut,
        seeds = [b"vault", market_id.as_ref()],
        bump
    )]
    pub vault: AccountInfo<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdateSolPrice<'info> {
    pub authority: Signer<'info>,
    
    #[account(mut)]
    pub orderbook: Account<'info, Orderbook>,
}

#[derive(Accounts)]
#[instruction(order_id: Pubkey)]
pub struct PlaceOrder<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(mut)]
    pub orderbook: Account<'info, Orderbook>,
    
    #[account(
        init,
        payer = user,
        space = 8 + 32 + 32 + 32 + 1 + 8 + 8 + 8 + 8 + 8 + 1 + 1 + 8,
        seeds = [b"order", order_id.as_ref()],
        bump
    )]
    pub order: Account<'info, Order>,
    
    /// CHECK: Vault for SOL collateral
    #[account(mut)]
    pub vault: AccountInfo<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct MatchOrders<'info> {
    #[account(mut)]
    pub orderbook: Account<'info, Orderbook>,
    
    #[account(mut)]
    pub yes_order: Account<'info, Order>,
    
    #[account(mut)]
    pub no_order: Account<'info, Order>,
    
    #[account(
        init_if_needed,
        payer = matcher,
        space = 8 + 32 + 32 + 8 + 8 + 8 + 8,
        seeds = [b"shares", yes_order.owner.as_ref(), orderbook.market_id.as_ref()],
        bump
    )]
    pub yes_user_shares: Account<'info, UserShares>,
    
    #[account(
        init_if_needed,
        payer = matcher,
        space = 8 + 32 + 32 + 8 + 8 + 8 + 8,
        seeds = [b"shares", no_order.owner.as_ref(), orderbook.market_id.as_ref()],
        bump
    )]
    pub no_user_shares: Account<'info, UserShares>,
    
    #[account(mut)]
    pub matcher: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
#[instruction(sell_order_id: Pubkey)]
pub struct SellShares<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(mut)]
    pub orderbook: Account<'info, Orderbook>,
    
    #[account(
        mut,
        seeds = [b"shares", user.key().as_ref(), orderbook.market_id.as_ref()],
        bump
    )]
    pub user_shares: Account<'info, UserShares>,
    
    #[account(
        init,
        payer = user,
        space = 8 + 32 + 32 + 32 + 1 + 8 + 8 + 8 + 8 + 8 + 1 + 1 + 8,
        seeds = [b"sell_order", sell_order_id.as_ref()],
        bump
    )]
    pub sell_order: Account<'info, Order>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct MatchSellOrders<'info> {
    #[account(mut)]
    pub orderbook: Account<'info, Orderbook>,
    
    #[account(mut)]
    pub yes_sell_order: Account<'info, Order>,
    
    #[account(mut)]
    pub no_sell_order: Account<'info, Order>,
    
    #[account(mut)]
    pub yes_user_shares: Account<'info, UserShares>,
    
    #[account(mut)]
    pub no_user_shares: Account<'info, UserShares>,
    
    /// CHECK: Vault for SOL
    #[account(mut)]
    pub vault: AccountInfo<'info>,
    
    /// CHECK: YES seller receives SOL
    #[account(mut)]
    pub yes_seller: AccountInfo<'info>,
    
    /// CHECK: NO seller receives SOL
    #[account(mut)]
    pub no_seller: AccountInfo<'info>,
    
    #[account(mut)]
    pub matcher: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct CancelOrder<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    #[account(mut)]
    pub order: Account<'info, Order>,
    
    /// CHECK: Vault for SOL refund
    #[account(mut)]
    pub vault: AccountInfo<'info>,
}

#[derive(Accounts)]
pub struct RedeemShares<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    
    pub orderbook: Account<'info, Orderbook>,
    
    #[account(mut)]
    pub user_shares: Account<'info, UserShares>,
    
    /// CHECK: Vault for payout
    #[account(mut)]
    pub vault: AccountInfo<'info>,
}

// ============================================================================
// Error Codes
// ============================================================================

#[error_code]
pub enum ErrorCode {
    #[msg("Unauthorized access")]
    Unauthorized,
    #[msg("Invalid amount")]
    InvalidAmount,
    #[msg("Invalid price - must be between 0 and 1")]
    InvalidPrice,
    #[msg("YES price + NO price must equal $1")]
    PricesMustSumToOne,
    #[msg("Orderbook is inactive")]
    OrderbookInactive,
    #[msg("Order is not open")]
    OrderNotOpen,
    #[msg("Order is not cancellable")]
    OrderNotCancellable,
    #[msg("Invalid order side")]
    InvalidOrderSide,
    #[msg("Market mismatch")]
    MarketMismatch,
    #[msg("No quantity to match")]
    NoMatchQuantity,
    #[msg("Insufficient shares")]
    InsufficientShares,
    #[msg("Not a sell order")]
    NotASellOrder,
    #[msg("Market is still active")]
    MarketStillActive,
    #[msg("No shares to redeem")]
    NoSharesToRedeem,
    #[msg("Math overflow")]
    MathOverflow,
}

// ============================================================================
// Events
// ============================================================================

#[event]
pub struct OrderbookInitialized {
    pub market_id: Pubkey,
    pub one_dollar_lamports: u64,
    pub timestamp: i64,
}

#[event]
pub struct SolPriceUpdated {
    pub market_id: Pubkey,
    pub old_lamports_per_dollar: u64,
    pub new_lamports_per_dollar: u64,
    pub timestamp: i64,
}

#[event]
pub struct OrderPlaced {
    pub order_id: Pubkey,
    pub owner: Pubkey,
    pub market_id: Pubkey,
    pub side: OrderSide,
    pub price: u64,
    pub quantity: u64,
    pub cost_lamports: u64,
    pub timestamp: i64,
}

#[event]
pub struct OrdersMatched {
    pub yes_order_id: Pubkey,
    pub no_order_id: Pubkey,
    pub market_id: Pubkey,
    pub yes_owner: Pubkey,
    pub no_owner: Pubkey,
    pub yes_price: u64,
    pub no_price: u64,
    pub quantity: u64,
    pub timestamp: i64,
}

#[event]
pub struct SellOrderPlaced {
    pub order_id: Pubkey,
    pub owner: Pubkey,
    pub market_id: Pubkey,
    pub side: OrderSide,
    pub price: u64,
    pub quantity: u64,
    pub timestamp: i64,
}

#[event]
pub struct SharesMerged {
    pub yes_order_id: Pubkey,
    pub no_order_id: Pubkey,
    pub market_id: Pubkey,
    pub yes_seller: Pubkey,
    pub no_seller: Pubkey,
    pub quantity: u64,
    pub yes_payout: u64,
    pub no_payout: u64,
    pub timestamp: i64,
}

#[event]
pub struct OrderCancelled {
    pub order_id: Pubkey,
    pub owner: Pubkey,
    pub refund_lamports: u64,
    pub timestamp: i64,
}

#[event]
pub struct SharesRedeemed {
    pub owner: Pubkey,
    pub market_id: Pubkey,
    pub winning_outcome: OrderSide,
    pub shares_redeemed: u64,
    pub payout_lamports: u64,
    pub timestamp: i64,
}
