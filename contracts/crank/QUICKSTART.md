# Crank Quick Start Guide

## What is the Crank?

The crank is an off-chain worker that:
- Monitors token market caps via DexScreener/Birdeye APIs
- Automatically resolves markets when conditions are met (target reached or deadline passed)
- Signs resolution transactions with the oracle keypair

## Setup (5 Minutes)

### 1. Generate Oracle Keypair

```bash
cd contracts/crank
node setup.js
```

This creates `oracle-keypair.json` and shows you the public key.

### 2. Fund Oracle Wallet

The oracle needs SOL for transaction fees:

```bash
# Get the oracle public key from setup.js output
solana airdrop 1 <ORACLE_PUBLIC_KEY> --url devnet
```

Or transfer SOL manually to the oracle address.

### 3. Configure Markets

Edit `markets-config.json`:

```json
{
  "markets": [
    {
      "marketSeed": "pepe_1m_24h",
      "tokenMint": "YOUR_TOKEN_MINT_ADDRESS",
      "targetMarketCap": 1000000000000,
      "deadline": 1704499200,
      "checkIntervalMs": 60000
    }
  ]
}
```

**Field Explanations:**
- `marketSeed`: Must match the seed used when creating the market on-chain
- `tokenMint`: Solana token mint address (e.g., SOL, BONK, PEPE)
- `targetMarketCap`: Target in USD with 6 decimals (1000000000000 = $1M)
- `deadline`: Unix timestamp (use https://www.unixtimestamp.com/)
- `checkIntervalMs`: How often to check (60000 = 1 minute)

### 4. Update Environment

Edit `.env` if needed:

```env
RPC_URL=https://api.devnet.solana.com
PROGRAM_ID=YOUR_DEPLOYED_PROGRAM_ID
ORACLE_KEYPAIR_PATH=./oracle-keypair.json
IDL_PATH=../target/idl/mememarket.json
MARKETS_CONFIG=./markets-config.json
```

### 5. Start the Crank

```bash
npm start
```

## How It Works

```
1. Crank loads markets from markets-config.json
2. Every 60 seconds (configurable):
   - Fetches token market cap from DexScreener
   - Checks if target reached OR deadline passed
   - If conditions met → calls parimutuel_resolve_market
3. Market resolves automatically
4. Users can claim rewards
```

## Example Output

```
================================================================================
PARIMUTUEL MARKET CAP CRANK
================================================================================
DEBUG: Crank initialized
DEBUG: Oracle Authority: 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
DEBUG: Program ID: MemeMarket1111111111111111111111111111111111
DEBUG: Added market to monitor: pepe_1m_24h
DEBUG: Token: PEPETokenMint...
DEBUG: Target: $1000000
DEBUG: Deadline: 2024-01-06T00:00:00.000Z

🚀 Starting market cap monitoring crank...

DEBUG: Checking market: pepe_1m_24h
DEBUG: DexScreener data for PEPETokenMint...:
  Market Cap: $1,250,000
  Price: $0.00125
  24h Volume: $500,000
DEBUG: Target reached: true

🎯 RESOLVING MARKET: pepe_1m_24h
Reason: Target reached
✅ Market resolved successfully!
Transaction: 5xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
```

## Testing Locally

### Test with SOL Token

```json
{
  "markets": [
    {
      "marketSeed": "test_sol_market",
      "tokenMint": "So11111111111111111111111111111111111111112",
      "targetMarketCap": 100000000000000,
      "deadline": 1735689600,
      "checkIntervalMs": 30000
    }
  ]
}
```

### Create Test Market On-Chain

```typescript
const oracleAuthority = new PublicKey("YOUR_ORACLE_PUBLIC_KEY");

await program.methods
  .parimutuelInitializeMarket(
    "test_sol_market",
    oracleAuthority,
    new PublicKey("So11111111111111111111111111111111111111112"),
    new anchor.BN(100000000000000),
    new anchor.BN(1735689600)
  )
  .accounts({
    market: marketPda,
    treasury: treasuryWallet,
    creator: userKeypair.publicKey,
    systemProgram: SystemProgram.programId,
  })
  .signers([userKeypair])
  .rpc();
```

## Troubleshooting

### "Unauthorized" Error
- Oracle keypair doesn't match the `oracle_authority` set when creating the market
- Solution: Use the same oracle public key from `setup.js` when creating markets

### "Insufficient funds" Error
- Oracle wallet has no SOL for transaction fees
- Solution: Airdrop or transfer SOL to oracle address

### "Market not found" Error
- Market seed in config doesn't match on-chain market
- Solution: Verify market seed matches exactly

### No Market Cap Data
- Token not listed on DexScreener
- Solution: Check token mint address, ensure token has liquidity

### "Cannot resolve yet" Error
- Target not reached AND deadline not passed
- Solution: Wait for conditions to be met

## Production Deployment

### Use PM2 for Production

```bash
npm install -g pm2
pm2 start npm --name "parimutuel-crank" -- start
pm2 startup
pm2 save
```

### Monitor Logs

```bash
pm2 logs parimutuel-crank
```

### Restart Crank

```bash
pm2 restart parimutuel-crank
```

## API Rate Limits

- **DexScreener**: ~300 requests/minute (free, no key)
- **Birdeye**: 100 requests/day free tier (requires API key)

Set `BIRDEYE_API_KEY` in `.env` for fallback support.

## Security Notes

🔒 **Keep oracle-keypair.json secure**
- Don't commit to git (already in .gitignore)
- Store backups securely
- Use different keys for dev/prod

🔒 **Oracle Authority**
- Only this oracle can resolve markets
- Users must trust the oracle
- Consider multi-sig for production

## Support

For issues:
1. Check logs: `npm start` output
2. Verify on-chain market state
3. Check Solscan for transaction details
4. Review `ORACLE_PARIMUTUEL_GUIDE.md` for full documentation
