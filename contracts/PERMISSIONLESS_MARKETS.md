# Permissionless Market Creation

## Overview

The parimutuel betting system now supports **permissionless market creation**, allowing any user to create prediction markets by paying a 0.015 SOL creation fee.

## Key Features

✅ **Anyone Can Create Markets**: No admin approval required  
✅ **Fixed Creation Fee**: 0.015 SOL per market  
✅ **Treasury Revenue**: All fees go to platform treasury wallet  
✅ **Balance Validation**: Ensures creator has sufficient funds  
✅ **User-Defined Parameters**: Creator sets target, token, and deadline  

## Market Creation Fee

```rust
pub const MARKET_CREATION_FEE: u64 = 15_000_000; // 0.015 SOL in lamports
```

### Fee Breakdown

| Component | Amount | Purpose |
|-----------|--------|---------|
| Creation Fee | 0.015 SOL | Platform revenue (goes to treasury) |
| Rent | ~0.002 SOL | Account rent-exemption (refundable) |
| **Total Required** | **~0.017 SOL** | Minimum balance needed |

## How It Works

### 1. User Creates Market

```typescript
const treasuryWallet = new PublicKey("TreasuryWalletAddress...");
const oracleAuthority = new PublicKey("OracleAuthorityAddress...");
const tokenMint = new PublicKey("TokenToTrack...");

const [marketPda] = PublicKey.findProgramAddressSync(
  [Buffer.from("market"), Buffer.from("my_market_seed")],
  program.programId
);

await program.methods
  .parimutuelInitializeMarket(
    "my_market_seed",                     // Unique market identifier
    oracleAuthority,                      // Oracle that will resolve
    tokenMint,                            // Token to track market cap
    new anchor.BN(1_000_000_000000),      // Target: $1M
    new anchor.BN(deadline)               // Unix timestamp
  )
  .accounts({
    market: marketPda,
    treasury: treasuryWallet,             // Platform treasury
    creator: userKeypair.publicKey,       // User creating market
    systemProgram: SystemProgram.programId,
  })
  .signers([userKeypair])
  .rpc();
```

### 2. Fee Transfer

The contract automatically:
1. Validates creator has enough SOL (0.015 + rent)
2. Transfers 0.015 SOL to treasury wallet
3. Creates market account (rent paid from creator)
4. Stores creator's public key in market

### 3. Market Parameters

Creator must specify:

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `market_seed` | String | Unique identifier | "btc_100k_24h" |
| `oracle_authority` | Pubkey | Oracle resolver | Platform oracle key |
| `token_mint` | Pubkey | Token to track | SOL, BONK, PEPE, etc. |
| `target_market_cap` | u64 | Target in USD (6 decimals) | 1_000_000_000000 = $1M |
| `deadline` | i64 | Unix timestamp | 1704499200 |

## Validation Rules

### Balance Check

```rust
let creator_balance = ctx.accounts.creator.lamports();
let rent_exempt_balance = Rent::get()?.minimum_balance(Market::LEN);
let total_required = MARKET_CREATION_FEE + rent_exempt_balance;

require!(
    creator_balance >= total_required,
    ParimutuelError::InsufficientFunds
);
```

**Error**: `InsufficientFunds` if creator doesn't have enough SOL

### Deadline Validation

```rust
require!(deadline > current_time, ParimutuelError::InvalidDeadline);
```

**Error**: `InvalidDeadline` if deadline is in the past

### Target Validation

```rust
require!(target_market_cap > 0, ParimutuelError::InvalidAmount);
```

**Error**: `InvalidAmount` if target is zero

## Complete Example

```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { PublicKey, Keypair } from "@solana/web3.js";

async function createMarket(
  program: Program,
  creator: Keypair,
  treasuryWallet: PublicKey,
  oracleAuthority: PublicKey
) {
  // Market configuration
  const marketSeed = "pepe_1m_7days";
  const tokenMint = new PublicKey("PEPETokenMintAddress...");
  const targetMarketCap = 1_000_000_000000; // $1M with 6 decimals
  const deadline = Math.floor(Date.now() / 1000) + 7 * 86400; // 7 days

  // Derive market PDA
  const [marketPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("market"), Buffer.from(marketSeed)],
    program.programId
  );

  console.log("Creating market:", marketSeed);
  console.log("Creator:", creator.publicKey.toString());
  console.log("Treasury:", treasuryWallet.toString());
  console.log("Target:", `$${targetMarketCap / 1_000_000}`);
  console.log("Deadline:", new Date(deadline * 1000).toISOString());

  // Check creator balance
  const balance = await program.provider.connection.getBalance(
    creator.publicKey
  );
  const requiredBalance = 15_000_000 + 2_000_000; // 0.015 + ~0.002 rent
  
  if (balance < requiredBalance) {
    throw new Error(
      `Insufficient balance. Have: ${balance / 1e9} SOL, Need: ${requiredBalance / 1e9} SOL`
    );
  }

  // Create market
  const tx = await program.methods
    .parimutuelInitializeMarket(
      marketSeed,
      oracleAuthority,
      tokenMint,
      new anchor.BN(targetMarketCap),
      new anchor.BN(deadline)
    )
    .accounts({
      market: marketPda,
      treasury: treasuryWallet,
      creator: creator.publicKey,
      systemProgram: anchor.web3.SystemProgram.programId,
    })
    .signers([creator])
    .rpc();

  console.log("✅ Market created!");
  console.log("Transaction:", tx);
  console.log("Market PDA:", marketPda.toString());

  return { marketPda, tx };
}

// Usage
const treasuryWallet = new PublicKey("YourTreasuryWalletAddress...");
const oracleAuthority = new PublicKey("YourOracleAuthorityAddress...");

await createMarket(program, userKeypair, treasuryWallet, oracleAuthority);
```

## Frontend Integration

### Market Creation Form

```typescript
interface MarketCreationForm {
  tokenMint: string;
  targetMarketCap: number;
  deadline: Date;
  marketName: string;
}

async function handleCreateMarket(formData: MarketCreationForm) {
  try {
    // Validate inputs
    if (!formData.tokenMint || !formData.targetMarketCap || !formData.deadline) {
      throw new Error("All fields are required");
    }

    // Check user balance
    const balance = await connection.getBalance(wallet.publicKey);
    const requiredBalance = 17_000_000; // 0.017 SOL
    
    if (balance < requiredBalance) {
      alert(`You need at least 0.017 SOL to create a market. Current balance: ${balance / 1e9} SOL`);
      return;
    }

    // Generate unique market seed
    const marketSeed = `${formData.marketName}_${Date.now()}`;

    // Create market
    const { marketPda, tx } = await createMarket(
      program,
      wallet,
      TREASURY_WALLET,
      ORACLE_AUTHORITY
    );

    // Show success
    alert(`Market created successfully! Transaction: ${tx}`);
    
    // Redirect to market page
    router.push(`/market/${marketPda.toString()}`);
  } catch (error) {
    console.error("Failed to create market:", error);
    alert(`Error: ${error.message}`);
  }
}
```

### Display Creation Fee

```tsx
<div className="market-creation-fee">
  <h3>Market Creation Fee</h3>
  <div className="fee-breakdown">
    <div className="fee-item">
      <span>Platform Fee:</span>
      <span>0.015 SOL</span>
    </div>
    <div className="fee-item">
      <span>Rent (refundable):</span>
      <span>~0.002 SOL</span>
    </div>
    <div className="fee-total">
      <span>Total Required:</span>
      <span>~0.017 SOL</span>
    </div>
  </div>
  <p className="fee-note">
    The 0.015 SOL fee supports platform development and operations.
  </p>
</div>
```

## Treasury Management

### Treasury Wallet Setup

The treasury wallet should be:
- **Secure**: Multi-sig or hardware wallet recommended
- **Monitored**: Track incoming creation fees
- **Accessible**: For platform operations and development

### Tracking Revenue

```typescript
// Get all markets created
const markets = await program.account.market.all();

// Calculate total fees collected
const totalMarkets = markets.length;
const totalFeesCollected = totalMarkets * 0.015; // SOL

console.log(`Total Markets Created: ${totalMarkets}`);
console.log(`Total Fees Collected: ${totalFeesCollected} SOL`);

// Get treasury balance
const treasuryBalance = await connection.getBalance(TREASURY_WALLET);
console.log(`Treasury Balance: ${treasuryBalance / 1e9} SOL`);
```

## Market Data Structure

```rust
pub struct Market {
    pub creator: Pubkey,            // User who created and paid fee
    pub oracle_authority: Pubkey,   // Oracle for resolution
    pub token_mint: Pubkey,         // Token being tracked
    pub total_yes_pool: u64,        // Total YES bets
    pub total_no_pool: u64,         // Total NO bets
    pub target_market_cap: u64,     // Target in USD (6 decimals)
    pub deadline: i64,              // Expiry timestamp
    pub is_resolved: bool,          // Resolution status
    pub winner: Option<bool>,       // Outcome
    pub target_reached: bool,       // Was target hit?
    pub resolved_at: i64,           // Resolution time
    pub bump: u8,                   // PDA bump
}
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `InsufficientFunds` | Not enough SOL | Add more SOL to wallet |
| `InvalidDeadline` | Deadline in past | Set future deadline |
| `InvalidAmount` | Target is zero | Set positive target |
| Account already exists | Market seed used | Use unique market seed |

### Error Messages

```typescript
try {
  await createMarket(...);
} catch (error) {
  if (error.message.includes("InsufficientFunds")) {
    console.error("You need at least 0.017 SOL to create a market");
  } else if (error.message.includes("InvalidDeadline")) {
    console.error("Deadline must be in the future");
  } else if (error.message.includes("InvalidAmount")) {
    console.error("Target market cap must be greater than zero");
  } else if (error.message.includes("already in use")) {
    console.error("Market seed already exists. Choose a different name.");
  } else {
    console.error("Failed to create market:", error.message);
  }
}
```

## Best Practices

### 1. Market Seed Generation

Use unique, descriptive seeds:

```typescript
// Good
const marketSeed = `${tokenSymbol}_${targetMcap}_${durationDays}d_${timestamp}`;
// Example: "PEPE_1M_7d_1704499200"

// Bad
const marketSeed = "market1"; // Too generic, likely to collide
```

### 2. Deadline Selection

```typescript
// Minimum 1 hour
const MIN_DURATION = 3600;

// Maximum 30 days
const MAX_DURATION = 30 * 86400;

const deadline = Math.floor(Date.now() / 1000) + duration;

if (duration < MIN_DURATION || duration > MAX_DURATION) {
  throw new Error("Duration must be between 1 hour and 30 days");
}
```

### 3. Target Market Cap

```typescript
// Use realistic targets based on current market cap
const currentMcap = await fetchCurrentMarketCap(tokenMint);
const targetMcap = currentMcap * 2; // 2x current

// Convert to contract format (6 decimals)
const targetMcapContract = Math.floor(targetMcap * 1_000_000);
```

### 4. Oracle Authority

```typescript
// Use platform's official oracle
const OFFICIAL_ORACLE = new PublicKey("PlatformOracleAddress...");

// Don't use random or untrusted oracles
// ❌ const oracle = Keypair.generate().publicKey;
```

## Security Considerations

### 1. Treasury Wallet Security

- Use multi-signature wallet for production
- Implement withdrawal limits
- Regular audits of treasury balance
- Separate hot/cold wallets

### 2. Market Seed Validation

```typescript
// Validate market seed format
function validateMarketSeed(seed: string): boolean {
  // Max 32 characters
  if (seed.length > 32) return false;
  
  // Alphanumeric and underscores only
  if (!/^[a-zA-Z0-9_]+$/.test(seed)) return false;
  
  return true;
}
```

### 3. Rate Limiting

Consider implementing rate limits to prevent spam:

```typescript
// Frontend rate limiting
const RATE_LIMIT = 5; // Max 5 markets per hour per user
const userMarkets = await getUserRecentMarkets(wallet.publicKey, 3600);

if (userMarkets.length >= RATE_LIMIT) {
  throw new Error("Rate limit exceeded. Please wait before creating more markets.");
}
```

## Analytics & Monitoring

### Track Market Creation Metrics

```typescript
interface MarketMetrics {
  totalMarketsCreated: number;
  totalFeesCollected: number;
  averageTargetMcap: number;
  averageDuration: number;
  topCreators: { creator: string; count: number }[];
}

async function getMarketMetrics(): Promise<MarketMetrics> {
  const markets = await program.account.market.all();
  
  return {
    totalMarketsCreated: markets.length,
    totalFeesCollected: markets.length * 0.015,
    averageTargetMcap: markets.reduce((sum, m) => 
      sum + m.account.targetMarketCap.toNumber(), 0) / markets.length,
    averageDuration: markets.reduce((sum, m) => 
      sum + (m.account.deadline.toNumber() - Date.now() / 1000), 0) / markets.length,
    topCreators: getTopCreators(markets),
  };
}
```

## Migration Notes

### Existing Markets

Markets created before this update will have:
- `creator` field set to the admin who created them
- Same functionality as new permissionless markets

### Backward Compatibility

The system is fully backward compatible. Old markets continue to work normally.

## FAQ

**Q: Can I get a refund on the creation fee?**  
A: No, the 0.015 SOL creation fee is non-refundable. However, the rent (~0.002 SOL) can be recovered by closing the market account after resolution.

**Q: What happens if my market gets no bets?**  
A: The market will still resolve at the deadline. The creation fee is not refunded.

**Q: Can I create unlimited markets?**  
A: Yes, but each requires 0.015 SOL. Consider implementing frontend rate limiting to prevent spam.

**Q: Who can resolve my market?**  
A: Only the oracle authority you specified during creation can resolve the market.

**Q: Can I change market parameters after creation?**  
A: No, all parameters are immutable once the market is created.

**Q: What if I set the wrong oracle authority?**  
A: The market will never resolve unless that oracle resolves it. Double-check the oracle address before creating.

## Summary

Permissionless market creation enables:
- 🌐 **Decentralization**: Anyone can create markets
- 💰 **Revenue**: Platform earns 0.015 SOL per market
- 🚀 **Scalability**: Unlimited market creation
- 🔒 **Security**: Balance validation prevents failed transactions
- 📊 **Flexibility**: Users define their own parameters

The 0.015 SOL fee ensures quality markets while generating sustainable platform revenue.
