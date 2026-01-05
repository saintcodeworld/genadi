use anchor_lang::prelude::*;

pub mod parimutuel;
pub use parimutuel::*;

declare_id!("GYDiDN3Snsff7ZJDqmSXyJciWZX4aXGqnLbTsSjXpPgB");

#[program]
pub mod mememarket {
    use super::*;

    /// Initialize a new parimutuel market
    /// Charges 0.015 SOL creation fee to treasury
    pub fn parimutuel_initialize_market(
        ctx: Context<InitializeMarket>,
        market_seed: String,
        oracle_authority: Pubkey,
        token_mint: Pubkey,
        target_market_cap: u64,
        deadline: i64,
    ) -> Result<()> {
        parimutuel::initialize_market(ctx, market_seed, oracle_authority, token_mint, target_market_cap, deadline)
    }

    /// Place a bet on YES or NO
    pub fn parimutuel_place_bet(
        ctx: Context<PlaceBet>,
        market_seed: String,
        amount: u64,
        side: bool,
    ) -> Result<()> {
        parimutuel::place_bet(ctx, market_seed, amount, side)
    }

    /// Resolve market (oracle only)
    pub fn parimutuel_resolve_market(
        ctx: Context<ResolveMarket>,
        market_seed: String,
        current_market_cap: u64,
        timestamp: i64,
    ) -> Result<()> {
        parimutuel::resolve_market(ctx, market_seed, current_market_cap, timestamp)
    }

    /// Claim reward after market resolution
    pub fn parimutuel_claim_reward(
        ctx: Context<ClaimReward>,
        market_seed: String,
    ) -> Result<()> {
        parimutuel::claim_reward(ctx, market_seed)
    }
}
