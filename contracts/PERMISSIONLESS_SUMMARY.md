# Permissionless Market Creation - Quick Reference

## Summary

The parimutuel betting system now supports **permissionless market creation**. Any user can create prediction markets by paying a **0.015 SOL creation fee** to the platform treasury.

## Key Changes

### 1. Market Structure Updated

```rust
pub struct Market {
    pub creator: Pubkey,            // Changed from 'admin' - user who paid fee
    pub oracle_authority: Pubkey,   // Oracle for resolution
    pub token_mint: Pubkey,         // Token to track
    // ... rest of fields
}
```

### 2. Creation Fee Constant

```rust
pub const MARKET_CREATION_FEE: u64 = 15_000_000; // 0.015 SOL
```

### 3. New Account in InitializeMarket

```rust
pub struct InitializeMarket<'info> {
    pub market: Account<'info, Market>,
    pub treasury: AccountInfo<'info>,  // NEW: Receives 0.015 SOL
    pub creator: Signer<'info>,        // Changed from 'admin'
    pub system_program: Program<'info, System>,
}
```

## Usage Example

```typescript
const treasuryWallet = new PublicKey("YourTreasuryAddress...");
const oracleAuthority = new PublicKey("YourOracleAddress...");

await program.methods
  .parimutuelInitializeMarket(
    "my_market",
    oracleAuthority,
    tokenMint,
    new anchor.BN(1_000_000_000000), // $1M target
    new anchor.BN(deadline)
  )
  .accounts({
    market: marketPda,
    treasury: treasuryWallet,        // NEW: Treasury account
    creator: userKeypair.publicKey,  // User pays 0.015 SOL
    systemProgram: SystemProgram.programId,
  })
  .signers([userKeypair])
  .rpc();
```

## Fee Breakdown

| Component | Amount | Purpose |
|-----------|--------|---------|
| Creation Fee | 0.015 SOL | Platform revenue (treasury) |
| Rent | ~0.002 SOL | Account rent (refundable) |
| **Total** | **~0.017 SOL** | Required balance |

## Validations

✅ Creator balance >= 0.015 SOL + rent  
✅ Deadline must be in future  
✅ Target market cap > 0  

## Error Codes

- `InsufficientFunds`: Not enough SOL for creation
- `InvalidDeadline`: Deadline in past
- `InvalidAmount`: Target is zero

## Benefits

🌐 **Decentralized**: No admin approval needed  
💰 **Revenue**: Platform earns from each market  
🚀 **Scalable**: Unlimited market creation  
🔒 **Secure**: Balance validation prevents failures  

## Documentation

- Full guide: `PERMISSIONLESS_MARKETS.md`
- Oracle system: `ORACLE_PARIMUTUEL_GUIDE.md`
- Original usage: `PARIMUTUEL_USAGE.md`
