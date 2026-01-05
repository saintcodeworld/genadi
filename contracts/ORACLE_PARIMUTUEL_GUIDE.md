# Oracle-Based Parimutuel Betting System

## Overview

This system implements **automated parimutuel betting markets** that resolve based on real-world token market cap data. Markets are resolved automatically by an off-chain oracle (crank worker) that monitors market conditions and triggers resolution when criteria are met.

### Permissionless Market Creation

✅ **Anyone can create markets** by paying a 0.015 SOL creation fee  
✅ **Fee goes to treasury wallet** for platform sustainability  
✅ **Creator defines parameters**: target market cap, token, and deadline  
✅ **Balance validation**: Ensures creator has sufficient funds before creation

## Architecture

```
┌─────────────────┐
│   Users Place   │
│   Bets (YES/NO) │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  On-Chain Smart Contract        │
│  - Stores bets in escrow PDA    │
│  - Tracks target & deadline     │
│  - Validates oracle signatures  │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Off-Chain Crank Worker         │
│  - Monitors token market cap    │
│  - Fetches data from APIs       │
│  - Calls resolve when ready     │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  External APIs                  │
│  - DexScreener (primary)        │
│  - Birdeye (fallback)           │
└─────────────────────────────────┘
```

## Market Resolution Logic

### Outcome Rules

**YES wins** if:
- Token market cap reaches or exceeds the target **before** the deadline

**NO wins** if:
- Deadline passes **without** the token reaching the target market cap

### Example Scenarios

#### Scenario 1: Target Reached
```
Market: "Will PEPE reach $1M market cap in 24 hours?"
Target: $1,000,000
Deadline: Jan 6, 2024 00:00 UTC
Current Time: Jan 5, 2024 18:00 UTC
Current Market Cap: $1,250,000

Result: YES wins (target reached before deadline)
```

#### Scenario 2: Deadline Passed
```
Market: "Will BONK reach $5M market cap in 7 days?"
Target: $5,000,000
Deadline: Jan 10, 2024 00:00 UTC
Current Time: Jan 10, 2024 00:01 UTC
Current Market Cap: $4,500,000

Result: NO wins (deadline passed without reaching target)
```

## Data Structures

### Market Account (Updated)

```rust
#[account]
pub struct Market {
    pub admin: Pubkey,              // Market creator
    pub oracle_authority: Pubkey,   // Oracle that can resolve
    pub token_mint: Pubkey,         // Token to track
    pub total_yes_pool: u64,        // Total SOL bet on YES
    pub total_no_pool: u64,         // Total SOL bet on NO
    pub target_market_cap: u64,     // Target in USD (6 decimals)
    pub deadline: i64,              // Unix timestamp
    pub is_resolved: bool,          // Resolution status
    pub winner: Option<bool>,       // true = YES, false = NO
    pub target_reached: bool,       // Was target reached?
    pub resolved_at: i64,           // When resolved
    pub bump: u8,                   // PDA bump
}
```

### UserBet Account (Unchanged)

```rust
#[account]
pub struct UserBet {
    pub user: Pubkey,               // Bettor
    pub market: Pubkey,             // Market reference
    pub amount: u64,                // Bet amount (lamports)
    pub side: bool,                 // true = YES, false = NO
    pub claimed: bool,              // Claimed status
}
```

## Instructions

### 1. Initialize Market (Permissionless)

**Any user can create a market by paying 0.015 SOL**

```typescript
const treasuryWallet = new PublicKey("TreasuryWalletAddress...");
const oracleAuthority = new PublicKey("OracleAuthorityAddress..."); // Platform oracle
const tokenMint = new PublicKey("TokenMintAddress...");
const targetMarketCap = 1_000_000_000000; // $1M with 6 decimals
const deadline = Math.floor(Date.now() / 1000) + 86400; // 24 hours from now

const [marketPda] = PublicKey.findProgramAddressSync(
  [Buffer.from("market"), Buffer.from("pepe_1m_24h")],
  program.programId
);

// Check user has enough balance (0.015 SOL fee + rent)
const balance = await connection.getBalance(userKeypair.publicKey);
if (balance < 17_000_000) { // ~0.017 SOL
  throw new Error("Insufficient balance for market creation");
}

await program.methods
  .parimutuelInitializeMarket(
    "pepe_1m_24h",                    // market_seed
    oracleAuthority,                  // oracle_authority (platform oracle)
    tokenMint,                        // token_mint
    new anchor.BN(targetMarketCap),   // target_market_cap
    new anchor.BN(deadline)           // deadline
  )
  .accounts({
    market: marketPda,
    treasury: treasuryWallet,         // Platform treasury (receives 0.015 SOL)
    creator: userKeypair.publicKey,   // User creating market (pays fee)
    systemProgram: SystemProgram.programId,
  })
  .signers([userKeypair])
  .rpc();
```

**Parameters:**
- `market_seed`: Unique identifier (e.g., "btc_100k_7days")
- `oracle_authority`: Public key of oracle that will resolve (use platform oracle)
- `token_mint`: Solana token mint address to track
- `target_market_cap`: Target in USD with 6 decimals (e.g., 1_000_000_000000 = $1M)
- `deadline`: Unix timestamp when market expires

**Accounts:**
- `market`: PDA for the market account
- `treasury`: Platform treasury wallet (receives 0.015 SOL fee)
- `creator`: User creating the market (pays 0.015 SOL + rent)
- `system_program`: Solana System Program

**Fee Structure:**
- **Creation Fee**: 0.015 SOL (sent to treasury)
- **Rent**: ~0.002 SOL (refundable)
- **Total Required**: ~0.017 SOL

**Validations:**
- Creator must have sufficient balance (0.015 SOL + rent)
- Deadline must be in the future
- Target market cap must be greater than zero

### 2. Place Bet (Updated with Deadline Check)

```typescript
const [marketPda] = PublicKey.findProgramAddressSync(
  [Buffer.from("market"), Buffer.from("pepe_1m_24h")],
  program.programId
);

const [userBetPda] = PublicKey.findProgramAddressSync(
  [Buffer.from("user_bet"), marketPda.toBuffer(), userKeypair.publicKey.toBuffer()],
  program.programId
);

const [escrowPda] = PublicKey.findProgramAddressSync(
  [Buffer.from("escrow"), marketPda.toBuffer()],
  program.programId
);

await program.methods
  .parimutuelPlaceBet(
    "pepe_1m_24h",
    new anchor.BN(1_000_000_000), // 1 SOL
    true                          // YES
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

**Validations:**
- Market must not be resolved
- Current time must be before deadline
- Amount must be greater than zero

### 3. Resolve Market (Oracle-Based)

**⚠️ This is called by the crank worker, not manually**

```typescript
const currentMarketCap = 1_250_000_000000; // $1.25M from API
const timestamp = Math.floor(Date.now() / 1000);

await program.methods
  .parimutuelResolveMarket(
    "pepe_1m_24h",
    new anchor.BN(currentMarketCap),
    new anchor.BN(timestamp)
  )
  .accounts({
    market: marketPda,
    oracle: oracleKeypair.publicKey,
  })
  .signers([oracleKeypair])
  .rpc();
```

**Parameters:**
- `current_market_cap`: Current market cap from API (USD with 6 decimals)
- `timestamp`: Unix timestamp of the data

**Validations:**
- Only oracle authority can call
- Market must not be already resolved
- Data must not be stale (< 5 minutes old)
- Either target reached OR deadline passed

### 4. Claim Reward (Unchanged)

```typescript
await program.methods
  .parimutuelClaimReward("pepe_1m_24h")
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

## Security Features

### 1. Oracle Authority Verification

```rust
require!(
    ctx.accounts.oracle.key() == market.oracle_authority,
    ParimutuelError::Unauthorized
);
```

Only the designated oracle can resolve markets.

### 2. Stale Data Protection

```rust
require!(
    timestamp <= current_time + 300, // 5 minute tolerance
    ParimutuelError::StaleData
);
```

Prevents resolution with outdated market cap data.

### 3. Resolution Conditions

```rust
let target_reached = current_market_cap >= market.target_market_cap;
let deadline_passed = current_time >= market.deadline;

require!(
    target_reached || deadline_passed,
    ParimutuelError::CannotResolveYet
);
```

Markets can only be resolved when conditions are met.

### 4. Deadline Enforcement

```rust
// In place_bet
require!(current_time < market.deadline, ParimutuelError::DeadlinePassed);
```

Prevents betting after deadline.

## Crank Worker Setup

### Quick Start

1. **Install dependencies:**
```bash
cd contracts/crank
npm install
```

2. **Generate oracle keypair:**
```bash
solana-keygen new -o oracle-keypair.json
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Configure markets:**
```json
{
  "markets": [
    {
      "marketSeed": "pepe_1m_24h",
      "tokenMint": "PEPETokenMint...",
      "targetMarketCap": 1000000000000,
      "deadline": 1704499200,
      "checkIntervalMs": 60000
    }
  ]
}
```

5. **Start the crank:**
```bash
npm start
```

### Production Deployment

Use PM2 for production:

```bash
npm install -g pm2
pm2 start npm --name "parimutuel-crank" -- start
pm2 startup
pm2 save
```

## Complete Example Flow

### Step 1: Admin Creates Market

```typescript
// Admin creates a market for PEPE reaching $1M in 24 hours
const marketSeed = "pepe_1m_24h";
const oracleAuthority = new PublicKey("OraclePublicKey...");
const pepeMint = new PublicKey("PEPEMintAddress...");
const targetMcap = 1_000_000_000000; // $1M
const deadline = Math.floor(Date.now() / 1000) + 86400; // 24h

await program.methods
  .parimutuelInitializeMarket(
    marketSeed,
    oracleAuthority,
    pepeMint,
    new anchor.BN(targetMcap),
    new anchor.BN(deadline)
  )
  .accounts({
    market: marketPda,
    admin: adminKeypair.publicKey,
    systemProgram: SystemProgram.programId,
  })
  .signers([adminKeypair])
  .rpc();
```

### Step 2: Users Place Bets

```typescript
// Alice bets 2 SOL on YES
await program.methods
  .parimutuelPlaceBet(
    marketSeed,
    new anchor.BN(2_000_000_000),
    true // YES
  )
  .accounts({ /* ... */ })
  .signers([aliceKeypair])
  .rpc();

// Bob bets 3 SOL on NO
await program.methods
  .parimutuelPlaceBet(
    marketSeed,
    new anchor.BN(3_000_000_000),
    false // NO
  )
  .accounts({ /* ... */ })
  .signers([bobKeypair])
  .rpc();
```

### Step 3: Crank Monitors & Resolves

```typescript
// Crank worker automatically:
// 1. Fetches PEPE market cap from DexScreener
// 2. Checks if target reached or deadline passed
// 3. Calls resolve_market when conditions met

// Example: PEPE reaches $1.2M after 18 hours
// Crank automatically resolves with YES winner
```

### Step 4: Winners Claim Rewards

```typescript
// Alice claims her reward (she bet on YES)
await program.methods
  .parimutuelClaimReward(marketSeed)
  .accounts({ /* ... */ })
  .signers([aliceKeypair])
  .rpc();

// Alice receives: (2 SOL / 2 SOL) × 5 SOL = 5 SOL
// (She gets all the pool since she was the only YES bettor)
```

## Error Codes

| Error | Description | Solution |
|-------|-------------|----------|
| `Unauthorized` | Oracle signature mismatch | Use correct oracle keypair |
| `InvalidDeadline` | Deadline in the past | Set future deadline |
| `DeadlinePassed` | Betting after deadline | Wait for resolution |
| `StaleData` | Oracle data too old | Fetch fresh data |
| `CannotResolveYet` | Conditions not met | Wait for target or deadline |
| `MarketAlreadyResolved` | Already resolved | Cannot resolve twice |

## API Integration

### DexScreener API

```typescript
const response = await axios.get(
  `https://api.dexscreener.com/latest/dex/tokens/${tokenMint}`
);

const marketCap = parseFloat(response.data.pairs[0].fdv);
```

**Pros:**
- Free, no API key required
- Good coverage of Solana tokens
- Real-time data

**Cons:**
- Rate limits (~300 req/min)
- May not have all tokens

### Birdeye API

```typescript
const response = await axios.get(
  `https://public-api.birdeye.so/defi/token_overview?address=${tokenMint}`,
  { headers: { "X-API-KEY": apiKey } }
);

const marketCap = response.data.data.mc;
```

**Pros:**
- Comprehensive Solana data
- Reliable and accurate
- Good rate limits

**Cons:**
- Requires API key
- Free tier limited to 100 req/day

## Best Practices

### 1. Oracle Key Management
- Store oracle keypair securely
- Use different keys for dev/prod
- Rotate keys periodically
- Never commit keys to git

### 2. Market Configuration
- Set realistic targets
- Allow sufficient time (24h+ recommended)
- Use well-known tokens with liquidity
- Test on devnet first

### 3. Crank Monitoring
- Use process managers (PM2)
- Set up health checks
- Monitor logs for errors
- Alert on failed resolutions

### 4. User Experience
- Display current market cap on frontend
- Show time remaining to deadline
- Calculate and display current odds
- Notify users of resolution

## Frontend Integration Example

```typescript
// Fetch market data
const market = await program.account.market.fetch(marketPda);

// Calculate current odds
const totalPool = market.totalYesPool.toNumber() + market.totalNoPool.toNumber();
const yesOdds = totalPool / market.totalYesPool.toNumber();
const noOdds = totalPool / market.totalNoPool.toNumber();

// Display to user
console.log(`YES odds: ${yesOdds.toFixed(2)}x`);
console.log(`NO odds: ${noOdds.toFixed(2)}x`);
console.log(`Target: $${market.targetMarketCap.toNumber() / 1_000_000}`);
console.log(`Deadline: ${new Date(market.deadline.toNumber() * 1000)}`);
console.log(`Time remaining: ${timeRemaining}`);
```

## Troubleshooting

### Crank Not Resolving

1. Check oracle keypair matches `oracle_authority`
2. Verify API connectivity and responses
3. Ensure conditions are met (target or deadline)
4. Check crank logs for errors

### Resolution Fails

1. Verify oracle has enough SOL for transaction fees
2. Check data timestamp is not stale
3. Ensure market not already resolved
4. Verify RPC endpoint is responsive

### No Market Cap Data

1. Verify token mint address is correct
2. Check token has liquidity on DEXs
3. Try alternative API (Birdeye)
4. Confirm token is on Solana mainnet

## Limitations & Considerations

1. **API Dependency**: System relies on external APIs (DexScreener/Birdeye)
2. **Oracle Trust**: Users must trust the oracle authority
3. **Network Delays**: Resolution may have slight delays
4. **Gas Costs**: Oracle pays transaction fees for resolution
5. **Market Cap Volatility**: Rapid price changes may affect fairness

## Future Enhancements

- Multi-oracle consensus for increased security
- Switchboard Functions integration for decentralized oracles
- Time-weighted average market cap (TWAP) for fairness
- Automated market maker (AMM) for dynamic odds
- Flash loan protection mechanisms
- Governance for oracle selection
