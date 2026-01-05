# Parimutuel Betting Program - Usage Guide

## Overview

This Anchor program implements a **Parimutuel Betting System** on Solana where users can bet on YES or NO outcomes with no fixed limits. All funds are pooled, and winners receive proportional payouts based on their contribution to the winning pool.

## Core Features

### 1. **No Fixed Limit**
- `total_yes_pool` and `total_no_pool` grow indefinitely as users place bets
- No 1 SOL cap or any other artificial limits

### 2. **PDA Escrow**
- All bet funds are transferred to a Program Derived Address (PDA) escrow
- Funds are held securely until market resolution and claims

### 3. **Proportional Payout Formula**
```
Reward = (User's Bet Amount / Total Winning Pool) × (Total YES Pool + Total NO Pool)
```

### 4. **Precision Handling**
- Uses `u128` for all reward calculations to prevent overflow
- Handles large lamport amounts safely

### 5. **Admin Resolution**
- Only the market admin can call `resolve_market(winner: bool)`
- Sets the winning outcome (YES = true, NO = false)

## Data Structures

### Market Account
```rust
#[account]
pub struct Market {
    pub admin: Pubkey,           // Admin who can resolve the market
    pub total_yes_pool: u64,     // Total SOL in YES pool (lamports)
    pub total_no_pool: u64,      // Total SOL in NO pool (lamports)
    pub is_resolved: bool,       // Market resolution status
    pub winner: Option<bool>,    // Some(true) = YES, Some(false) = NO
    pub bump: u8,                // PDA bump seed
}
```

### UserBet Account
```rust
#[account]
pub struct UserBet {
    pub user: Pubkey,            // User who placed the bet
    pub market: Pubkey,          // Market this bet belongs to
    pub amount: u64,             // Bet amount in lamports
    pub side: bool,              // true = YES, false = NO
    pub claimed: bool,           // Reward claim status
}
```

## Instructions

### 1. Initialize Market
```typescript
await program.methods
  .parimutuelInitializeMarket(marketSeed)
  .accounts({
    market: marketPda,
    admin: adminKeypair.publicKey,
    systemProgram: SystemProgram.programId,
  })
  .signers([adminKeypair])
  .rpc();
```

**Parameters:**
- `market_seed`: String - Unique identifier for the market

**Accounts:**
- `market`: PDA derived from `["market", market_seed]`
- `admin`: Signer - Admin who can resolve the market
- `system_program`: System Program

### 2. Place Bet
```typescript
await program.methods
  .parimutuelPlaceBet(
    marketSeed,
    new anchor.BN(1_000_000_000), // 1 SOL in lamports
    true                           // true = YES, false = NO
  )
  .accounts({
    market: marketPda,
    userBet: userBetPda,
    escrow: escrowPda,
    user: userKeypair.publicKey,
    systemProgram: SystemProgram.programId,
  })
  .signers([userKeypair])
  .rpc();
```

**Parameters:**
- `market_seed`: String - Market identifier
- `amount`: u64 - Bet amount in lamports
- `side`: bool - Betting side (true = YES, false = NO)

**Accounts:**
- `market`: PDA derived from `["market", market_seed]`
- `user_bet`: PDA derived from `["user_bet", market_key, user_key]`
- `escrow`: PDA derived from `["escrow", market_key]`
- `user`: Signer - User placing the bet
- `system_program`: System Program

**Validation:**
- Market must not be resolved
- Amount must be greater than zero
- Transfers SOL from user to escrow PDA

### 3. Resolve Market (Admin Only)
```typescript
await program.methods
  .parimutuelResolveMarket(
    marketSeed,
    true  // true = YES wins, false = NO wins
  )
  .accounts({
    market: marketPda,
    admin: adminKeypair.publicKey,
  })
  .signers([adminKeypair])
  .rpc();
```

**Parameters:**
- `market_seed`: String - Market identifier
- `winner`: bool - Winning side (true = YES, false = NO)

**Accounts:**
- `market`: PDA derived from `["market", market_seed]`
- `admin`: Signer - Must match market.admin

**Validation:**
- Only admin can call this instruction
- Market must not already be resolved

### 4. Claim Reward
```typescript
await program.methods
  .parimutuelClaimReward(marketSeed)
  .accounts({
    market: marketPda,
    userBet: userBetPda,
    escrow: escrowPda,
    user: userKeypair.publicKey,
    systemProgram: SystemProgram.programId,
  })
  .signers([userKeypair])
  .rpc();
```

**Parameters:**
- `market_seed`: String - Market identifier

**Accounts:**
- `market`: PDA derived from `["market", market_seed]`
- `user_bet`: PDA derived from `["user_bet", market_key, user_key]`
- `escrow`: PDA derived from `["escrow", market_key]`
- `user`: Signer - User claiming reward
- `system_program`: System Program

**Validation:**
- Market must be resolved
- User must not have already claimed
- User must be on the winning side
- Winning pool must not be empty

**Calculation:**
```rust
// Using u128 to prevent overflow
let reward = (user_bet.amount as u128)
    .checked_mul(total_pool as u128)
    .checked_div(winning_pool as u128);
```

## Example Scenario

### Setup
```
Market: "will_btc_reach_100k"
Admin: AdminKeypair
```

### Betting Phase
```
User A bets 2 SOL on YES
User B bets 3 SOL on YES
User C bets 5 SOL on NO

Total YES Pool: 5 SOL
Total NO Pool: 5 SOL
Total Pool: 10 SOL
```

### Resolution
```
Admin resolves: YES wins (winner = true)
```

### Claiming Rewards
```
User A's reward: (2 SOL / 5 SOL) × 10 SOL = 4 SOL
User B's reward: (3 SOL / 5 SOL) × 10 SOL = 6 SOL
User C: Cannot claim (bet on losing side)
```

## PDA Seeds

| Account | Seeds |
|---------|-------|
| Market | `["market", market_seed]` |
| User Bet | `["user_bet", market_key, user_key]` |
| Escrow | `["escrow", market_key]` |

## Error Codes

| Error | Description |
|-------|-------------|
| `Unauthorized` | Only admin can perform this action |
| `MarketResolved` | Cannot bet on resolved market |
| `MarketAlreadyResolved` | Market has already been resolved |
| `MarketNotResolved` | Market must be resolved before claiming |
| `InvalidAmount` | Amount must be greater than zero |
| `AlreadyClaimed` | Reward has already been claimed |
| `NotWinner` | User is not on the winning side |
| `NoWinner` | No winner set for this market |
| `EmptyPool` | Winning pool is empty |
| `Overflow` | Arithmetic overflow occurred |
| `DivisionByZero` | Division by zero error |
| `InvalidMarket` | Invalid market reference |

## Security Features

1. **Admin-only resolution**: Only the market creator can resolve the outcome
2. **One-time claims**: Users cannot claim rewards multiple times
3. **Overflow protection**: All calculations use `u128` to prevent overflow
4. **PDA escrow**: Funds are held in a secure PDA, not in user accounts
5. **Validation checks**: Comprehensive validation on all instructions

## Debug Logging

The program includes extensive debug logging:
- Market initialization
- Bet placement with pool updates
- Market resolution with final pool amounts
- Reward calculations and claims

Use `solana logs` to view debug output during testing.

## Building and Deploying

```bash
# Build the program
anchor build

# Run tests
anchor test

# Deploy to devnet
anchor deploy --provider.cluster devnet
```

## Integration Notes

- All amounts are in **lamports** (1 SOL = 1,000,000,000 lamports)
- Market seeds should be unique and descriptive
- Consider implementing a frontend to display pool sizes and odds
- Add time-based resolution mechanisms for automated markets
- Consider adding a fee mechanism for platform sustainability
