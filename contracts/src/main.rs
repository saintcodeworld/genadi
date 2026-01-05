use anchor_lang::prelude::*;

declare_id!("MemeMarket1111111111111111111111111111111111");

#[program]
pub mod mememarket {
    use super::*;
    
    pub mod amm;
    pub use amm::*;
}
