# Parimutuel Market Cap Crank

Off-chain worker service that monitors token market caps via DexScreener/Birdeye APIs and automatically resolves parimutuel betting markets when conditions are met.

## Overview

The crank continuously monitors configured markets and triggers resolution when:
1. **Target Reached**: Token market cap exceeds the target value
2. **Deadline Passed**: The deadline timestamp is reached without hitting the target

## Features

- ✅ **Dual API Support**: DexScreener (primary) + Birdeye (fallback)
- ✅ **Automatic Resolution**: Calls on-chain `resolve_market` when conditions met
- ✅ **Signature Verification**: Uses oracle keypair to sign transactions
- ✅ **Multi-Market Support**: Monitor multiple markets simultaneously
- ✅ **Configurable Intervals**: Set custom check frequencies per market
- ✅ **Comprehensive Logging**: Debug logs for monitoring and troubleshooting

## Installation

```bash
cd contracts/crank
npm install
```

## Configuration

### 1. Generate Oracle Keypair

```bash
solana-keygen new -o oracle-keypair.json
```

**Important**: This keypair must match the `oracle_authority` set when initializing markets.

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env`:

```env
RPC_URL=https://api.devnet.solana.com
PROGRAM_ID=MemeMarket1111111111111111111111111111111111
ORACLE_KEYPAIR_PATH=./oracle-keypair.json
IDL_PATH=../target/idl/mememarket.json
MARKETS_CONFIG=./markets-config.json
BIRDEYE_API_KEY=optional_birdeye_api_key
```

### 3. Configure Markets

Edit `markets-config.json`:

```json
{
  "markets": [
    {
      "marketSeed": "pepe_1m_mcap_7days",
      "tokenMint": "PEPETokenMintAddress...",
      "targetMarketCap": 1000000000000,
      "deadline": 1704499200,
      "checkIntervalMs": 60000
    }
  ]
}
```

**Field Descriptions:**
- `marketSeed`: Unique identifier for the market (must match on-chain market)
- `tokenMint`: Solana token mint address to track
- `targetMarketCap`: Target in USD with 6 decimals (e.g., 1_000_000_000000 = $1M)
- `deadline`: Unix timestamp when market expires
- `checkIntervalMs`: How often to check (milliseconds)

## Usage

### Start the Crank

```bash
npm start
```

### Development Mode (with auto-reload)

```bash
npm run dev
```

### Build TypeScript

```bash
npm run build
```

## How It Works

### 1. Market Monitoring Loop

```
┌─────────────────────────────────────────┐
│  Crank starts, loads markets config     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  For each market:                       │
│  1. Fetch on-chain market account       │
│  2. Check if already resolved            │
│  3. Fetch current market cap from API   │
│  4. Compare with target & deadline      │
└──────────────┬──────────────────────────┘
               │
               ▼
      ┌────────┴────────┐
      │ Conditions met? │
      └────────┬────────┘
               │
        ┌──────┴──────┐
        │             │
       YES           NO
        │             │
        ▼             ▼
  ┌─────────┐   ┌─────────┐
  │ Resolve │   │  Wait   │
  │ Market  │   │ & Loop  │
  └─────────┘   └─────────┘
```

### 2. Resolution Logic

```typescript
// YES wins if target reached before deadline
if (currentMarketCap >= targetMarketCap) {
  winner = true; // YES
}
// NO wins if deadline passes without reaching target
else if (currentTime >= deadline) {
  winner = false; // NO
}
```

### 3. API Data Sources

**Primary: DexScreener**
```
GET https://api.dexscreener.com/latest/dex/tokens/{tokenMint}
```

**Fallback: Birdeye** (requires API key)
```
GET https://public-api.birdeye.so/defi/token_overview?address={tokenMint}
Headers: X-API-KEY: {apiKey}
```

## Security

### Oracle Authority Verification

The on-chain program verifies that the transaction is signed by the authorized oracle:

```rust
require!(
    ctx.accounts.oracle.key() == market.oracle_authority,
    ParimutuelError::Unauthorized
);
```

### Stale Data Protection

The program rejects data older than 5 minutes:

```rust
require!(
    timestamp <= current_time + 300,
    ParimutuelError::StaleData
);
```

### Resolution Conditions

Markets can only be resolved when:
1. Target market cap is reached, OR
2. Deadline has passed

```rust
require!(
    target_reached || deadline_passed,
    ParimutuelError::CannotResolveYet
);
```

## Deployment

### Production Deployment Options

#### 1. **VPS/Cloud Server** (Recommended)

```bash
# Install dependencies
npm install --production

# Use PM2 for process management
npm install -g pm2

# Start with PM2
pm2 start npm --name "parimutuel-crank" -- start

# Enable auto-restart on reboot
pm2 startup
pm2 save
```

#### 2. **Docker Container**

Create `Dockerfile`:

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY . .

CMD ["npm", "start"]
```

Build and run:

```bash
docker build -t parimutuel-crank .
docker run -d --name crank --env-file .env parimutuel-crank
```

#### 3. **Kubernetes**

Deploy as a Kubernetes CronJob or Deployment for high availability.

### Monitoring

Add monitoring with:
- **Logs**: `pm2 logs parimutuel-crank`
- **Metrics**: Integrate with Prometheus/Grafana
- **Alerts**: Set up alerts for failed resolutions

## Troubleshooting

### Issue: "Unauthorized" Error

**Cause**: Oracle keypair doesn't match `oracle_authority` on market

**Solution**: Ensure the oracle keypair used by crank matches the one set during market initialization

### Issue: "StaleData" Error

**Cause**: API data timestamp is too old

**Solution**: Check API connectivity and response times

### Issue: "CannotResolveYet" Error

**Cause**: Neither target reached nor deadline passed

**Solution**: Wait for conditions to be met

### Issue: No Market Cap Data

**Cause**: Token not listed on DexScreener/Birdeye

**Solution**: 
- Verify token mint address
- Check if token has liquidity pools
- Try alternative API sources

## Example Output

```
================================================================================
PARIMUTUEL MARKET CAP CRANK
================================================================================
DEBUG: Crank initialized
DEBUG: Oracle Authority: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
DEBUG: Program ID: MemeMarket1111111111111111111111111111111111
DEBUG: Added market to monitor: pepe_1m_mcap_7days
DEBUG: Token: PEPETokenMintAddress...
DEBUG: Target: $1000000
DEBUG: Deadline: 2024-01-06T00:00:00.000Z

🚀 Starting market cap monitoring crank...

DEBUG: Checking market: pepe_1m_mcap_7days
DEBUG: Current time: 2024-01-05T12:00:00.000Z
DEBUG: Deadline: 2024-01-06T00:00:00.000Z
DEBUG: Deadline passed: false
DEBUG: DexScreener data for PEPETokenMintAddress...:
  Market Cap: $1,250,000
  Price: $0.00125
  24h Volume: $500,000
DEBUG: Current Market Cap: $1,250,000
DEBUG: Target Market Cap: $1,000,000
DEBUG: Target reached: true

🎯 RESOLVING MARKET: pepe_1m_mcap_7days
Reason: Target reached
DEBUG: Sending resolution transaction...
  Market PDA: 8xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
  Current Market Cap: $1250000
  Timestamp: 1704456000
✅ Market resolved successfully!
Transaction: 5xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
Explorer: https://solscan.io/tx/5xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU?cluster=devnet
DEBUG: Removed pepe_1m_mcap_7days from monitoring list
```

## API Rate Limits

### DexScreener
- **Free tier**: ~300 requests/minute
- **No API key required**

### Birdeye
- **Free tier**: 100 requests/day
- **Paid tiers**: Higher limits available
- **Requires API key**

## Best Practices

1. **Set Reasonable Check Intervals**: 60 seconds is usually sufficient
2. **Monitor Crank Health**: Use process managers like PM2
3. **Backup Oracle Keys**: Store securely with encryption
4. **Test on Devnet First**: Validate configuration before mainnet
5. **Add Redundancy**: Run multiple crank instances for critical markets
6. **Log Rotation**: Implement log rotation to prevent disk space issues

## Support

For issues or questions:
- Check logs: `pm2 logs parimutuel-crank`
- Review on-chain transactions on Solscan
- Verify market account state with `solana account <market_pda>`
