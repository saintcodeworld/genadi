# Complete Deployment Guide - Parimutuel Betting System

## Overview

This guide walks you through deploying the entire parimutuel betting system to production, including the smart contract, resolution bot, and frontend integration.

---

## 📋 Pre-Deployment Checklist

### Required Tools
- [ ] Solana CLI installed (`solana --version`)
- [ ] Anchor CLI installed (`anchor --version`)
- [ ] Node.js 18+ installed (`node --version`)
- [ ] Git installed
- [ ] Sufficient SOL for deployment (~2-5 SOL for devnet, more for mainnet)

### Required Accounts
- [ ] Deployer wallet with SOL
- [ ] Treasury wallet address (for receiving fees)
- [ ] Oracle wallet (will be generated)

---

## 🚀 Step 1: Build and Deploy Smart Contract

### 1.1 Configure Anchor

```bash
cd contracts
```

Edit `Anchor.toml`:
```toml
[provider]
cluster = "devnet"  # or "mainnet-beta" for production
wallet = "~/.config/solana/id.json"

[programs.devnet]
mememarket = "YOUR_PROGRAM_ID"
```

### 1.2 Build Program

```bash
anchor build
```

This generates:
- `target/deploy/mememarket.so` - Compiled program
- `target/idl/mememarket.json` - Interface definition
- `target/types/mememarket.ts` - TypeScript types

### 1.3 Get Program ID

```bash
solana address -k target/deploy/mememarket-keypair.json
```

Copy this address and update:
- `Anchor.toml` → `[programs.devnet]`
- `src/lib.rs` → `declare_id!("YOUR_PROGRAM_ID")`

### 1.4 Rebuild with Correct ID

```bash
anchor build
```

### 1.5 Deploy to Devnet

```bash
# Check deployer balance
solana balance

# Airdrop if needed (devnet only)
solana airdrop 2

# Deploy
anchor deploy --provider.cluster devnet
```

**Expected Output:**
```
Program Id: MemeMarket1111111111111111111111111111111111

Deploy success
```

### 1.6 Verify Deployment

```bash
solana program show YOUR_PROGRAM_ID --url devnet
```

---

## 🤖 Step 2: Setup Resolution Bot

### 2.1 Navigate to Crank Directory

```bash
cd crank
```

### 2.2 Install Dependencies

```bash
npm install
```

### 2.3 Generate Oracle Keypair

```bash
npm run setup
```

**Output:**
```
🔧 Setting up Oracle Crank...

1. Generating oracle keypair...
✅ Oracle keypair generated!
   Public Key: EDBTCxVDzKMH177fjTaXqrc4twhpfzi6iyoifo2cAJcz
   Saved to: oracle-keypair.json
```

**⚠️ IMPORTANT**: Save this public key - you'll need it for creating markets!

### 2.4 Fund Oracle Wallet

```bash
# Devnet
solana airdrop 1 <ORACLE_PUBLIC_KEY> --url devnet

# Mainnet - transfer SOL manually
solana transfer <ORACLE_PUBLIC_KEY> 0.5 --url mainnet-beta
```

Verify balance:
```bash
solana balance <ORACLE_PUBLIC_KEY> --url devnet
```

### 2.5 Configure Environment

Edit `.env`:
```env
# Solana Configuration
RPC_URL=https://api.devnet.solana.com
PROGRAM_ID=YOUR_DEPLOYED_PROGRAM_ID

# Oracle Configuration
ORACLE_KEYPAIR_PATH=./oracle-keypair.json
IDL_PATH=../target/idl/mememarket.json

# Bot Settings
CHECK_INTERVAL_MS=60000      # Check every 60 seconds
MAX_RETRIES=3                # Retry failed API calls 3 times
RETRY_DELAY_MS=5000          # Wait 5 seconds between retries

# Optional: Birdeye API (fallback)
BIRDEYE_API_KEY=your_api_key_here
```

### 2.6 Test Bot Locally

```bash
npm start
```

**Expected Output:**
```
================================================================================
PARIMUTUEL MARKET RESOLUTION BOT
================================================================================
DEBUG: Bot initialized
DEBUG: Oracle Authority: EDBTCxVDzKMH177fjTaXqrc4twhpfzi6iyoifo2cAJcz
DEBUG: Program ID: MemeMarket1111111111111111111111111111111111
================================================================================

💰 Oracle Wallet Balance: 1.0000 SOL

🚀 Starting market resolution bot...

🔍 Fetching active markets...
DEBUG: Found 0 active market(s)

✅ No active markets to process

⏰ Waiting 60 seconds until next check...
```

---

## 🧪 Step 3: Test Market Creation

### 3.1 Create Test Script

Create `test-market.ts`:

```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program, AnchorProvider } from "@coral-xyz/anchor";
import { Connection, Keypair, PublicKey } from "@solana/web3.js";
import * as fs from "fs";

async function createTestMarket() {
  const connection = new Connection("https://api.devnet.solana.com", "confirmed");
  const wallet = new anchor.Wallet(
    Keypair.fromSecretKey(
      Uint8Array.from(JSON.parse(fs.readFileSync("./test-wallet.json", "utf-8")))
    )
  );
  const provider = new AnchorProvider(connection, wallet, { commitment: "confirmed" });
  
  const programId = new PublicKey("YOUR_PROGRAM_ID");
  const idl = JSON.parse(fs.readFileSync("../target/idl/mememarket.json", "utf-8"));
  const program = new Program(idl, programId, provider);

  // Configuration
  const treasuryWallet = new PublicKey("YOUR_TREASURY_ADDRESS");
  const oracleAuthority = new PublicKey("YOUR_ORACLE_PUBLIC_KEY");
  const tokenMint = new PublicKey("So11111111111111111111111111111111111111112"); // SOL
  const marketSeed = `test_sol_${Date.now()}`;
  const targetMarketCap = 100_000_000_000000; // $100B (will never hit - for testing NO)
  const deadline = Math.floor(Date.now() / 1000) + 300; // 5 minutes

  // Derive market PDA
  const [marketPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("market"), Buffer.from(marketSeed)],
    program.programId
  );

  console.log("Creating test market...");
  console.log("Market Seed:", marketSeed);
  console.log("Market PDA:", marketPda.toString());
  console.log("Target:", `$${targetMarketCap / 1_000_000}`);
  console.log("Deadline:", new Date(deadline * 1000).toISOString());

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
      creator: wallet.publicKey,
      systemProgram: anchor.web3.SystemProgram.programId,
    })
    .rpc();

  console.log("✅ Market created!");
  console.log("Transaction:", tx);
  console.log("Explorer:", `https://solscan.io/tx/${tx}?cluster=devnet`);
}

createTestMarket().catch(console.error);
```

### 3.2 Run Test

```bash
ts-node test-market.ts
```

### 3.3 Verify Bot Detects Market

Check bot logs - should show:
```
🔍 Fetching active markets...
DEBUG: Found 1 active market(s)

📊 Processing Market: abc12345...
   Token: So11111111111111111111111111111111111111112
   Target: $100,000,000
   Deadline: 2026-01-04T22:15:00.000Z
   Time Remaining: 4h 59m
```

---

## 🎯 Step 4: Production Deployment

### 4.1 Deploy to Mainnet

```bash
# Update Anchor.toml
[provider]
cluster = "mainnet-beta"

# Deploy
anchor deploy --provider.cluster mainnet-beta
```

### 4.2 Update Bot Configuration

```env
RPC_URL=https://api.mainnet-beta.solana.com
# Or use paid RPC for better performance:
# RPC_URL=https://rpc.helius.xyz/?api-key=YOUR_KEY
```

### 4.3 Run Bot with PM2

Install PM2:
```bash
npm install -g pm2
```

Start bot:
```bash
pm2 start npm --name "parimutuel-bot" -- start
pm2 save
pm2 startup
```

Monitor:
```bash
pm2 logs parimutuel-bot
pm2 monit
```

### 4.4 Setup Monitoring

Create `monitor.sh`:
```bash
#!/bin/bash

# Check bot is running
if ! pm2 list | grep -q "parimutuel-bot.*online"; then
    echo "⚠️  Bot is not running!"
    pm2 restart parimutuel-bot
fi

# Check oracle balance
BALANCE=$(solana balance YOUR_ORACLE_PUBLIC_KEY --url mainnet-beta | awk '{print $1}')
if (( $(echo "$BALANCE < 0.1" | bc -l) )); then
    echo "⚠️  Oracle balance low: $BALANCE SOL"
    # Send alert (email, Slack, etc.)
fi

# Check for errors in logs
ERRORS=$(pm2 logs parimutuel-bot --nostream --lines 100 | grep -c "ERROR")
if [ "$ERRORS" -gt 10 ]; then
    echo "⚠️  High error count: $ERRORS errors in last 100 lines"
fi
```

Add to crontab:
```bash
crontab -e
# Add: */5 * * * * /path/to/monitor.sh
```

---

## 🌐 Step 5: Frontend Integration

### 5.1 Install Dependencies

```bash
npm install @coral-xyz/anchor @solana/web3.js @solana/wallet-adapter-react
```

### 5.2 Initialize Program

```typescript
import { Program, AnchorProvider } from "@coral-xyz/anchor";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";

const programId = new PublicKey("YOUR_PROGRAM_ID");
const idl = await Program.fetchIdl(programId, provider);
const program = new Program(idl, programId, provider);
```

### 5.3 Create Market (Frontend)

```typescript
async function createMarket(
  tokenMint: string,
  targetMarketCap: number,
  deadline: number
) {
  const treasuryWallet = new PublicKey("YOUR_TREASURY");
  const oracleAuthority = new PublicKey("YOUR_ORACLE");
  const marketSeed = `${tokenMint.slice(0, 8)}_${Date.now()}`;

  const [marketPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("market"), Buffer.from(marketSeed)],
    program.programId
  );

  await program.methods
    .parimutuelInitializeMarket(
      marketSeed,
      oracleAuthority,
      new PublicKey(tokenMint),
      new anchor.BN(targetMarketCap * 1_000_000),
      new anchor.BN(deadline)
    )
    .accounts({
      market: marketPda,
      treasury: treasuryWallet,
      creator: wallet.publicKey,
      systemProgram: SystemProgram.programId,
    })
    .rpc();
}
```

### 5.4 Display Markets

See `FRONTEND_INTEGRATION.md` for complete implementation.

---

## 🔒 Step 6: Security Hardening

### 6.1 Secure Oracle Keypair

```bash
# Set proper permissions
chmod 600 oracle-keypair.json

# Backup securely
cp oracle-keypair.json ~/secure-backup/
```

### 6.2 Use Hardware Wallet for Treasury

For mainnet, use Ledger or multi-sig:
```bash
# Create multi-sig (recommended)
solana-keygen new --outfile treasury-key1.json
solana-keygen new --outfile treasury-key2.json
solana-keygen new --outfile treasury-key3.json

# Create 2-of-3 multi-sig
# (Use Squads Protocol or similar)
```

### 6.3 Rate Limiting

Add Cloudflare or similar in front of RPC:
```env
RPC_URL=https://your-protected-rpc.com
```

### 6.4 Monitoring Alerts

Setup alerts for:
- Bot downtime
- Oracle low balance
- High error rates
- Unusual transaction patterns

---

## 📊 Step 7: Analytics and Monitoring

### 7.1 Track Metrics

```typescript
// Track in database or analytics service
interface Metrics {
  totalMarkets: number;
  activeMarkets: number;
  resolvedMarkets: number;
  totalVolume: number;
  totalFees: number;
  resolutionSuccessRate: number;
}
```

### 7.2 Dashboard

Create admin dashboard showing:
- Active markets count
- Total volume (SOL)
- Fees collected
- Bot status
- Oracle balance
- Recent resolutions

### 7.3 Logs

Centralize logs:
```bash
# Send to logging service
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 30
```

---

## 🧪 Testing Checklist

### Smart Contract Tests

- [ ] Market creation with fee transfer
- [ ] Betting before deadline
- [ ] Betting after deadline (should fail)
- [ ] Resolution by authorized oracle
- [ ] Resolution by unauthorized user (should fail)
- [ ] Claiming rewards (winner)
- [ ] Claiming rewards (loser - should fail)
- [ ] Double claiming (should fail)
- [ ] Overflow scenarios

### Bot Tests

- [ ] Detects new markets
- [ ] Fetches market cap correctly
- [ ] Resolves when target reached
- [ ] Resolves when deadline passed
- [ ] Handles API failures gracefully
- [ ] Retries on network errors
- [ ] Skips markets with stale data
- [ ] Logs errors appropriately

### Integration Tests

- [ ] End-to-end: Create → Bet → Resolve → Claim
- [ ] Multiple users betting
- [ ] Large bet amounts (overflow protection)
- [ ] Concurrent operations
- [ ] Network interruptions

---

## 🚨 Emergency Procedures

### Bot Stopped

```bash
# Check status
pm2 status

# View logs
pm2 logs parimutuel-bot --lines 100

# Restart
pm2 restart parimutuel-bot

# If persistent issues
pm2 delete parimutuel-bot
pm2 start npm --name "parimutuel-bot" -- start
```

### Oracle Out of Funds

```bash
# Check balance
solana balance YOUR_ORACLE_PUBLIC_KEY

# Fund immediately
solana transfer YOUR_ORACLE_PUBLIC_KEY 1.0

# Setup auto-funding (optional)
# Create script to monitor and auto-fund
```

### Market Stuck (Won't Resolve)

```bash
# Check market state
solana account MARKET_PDA --output json

# Verify oracle authority matches
# Check deadline has passed or target reached
# Manually trigger resolution if needed
```

### Contract Upgrade Needed

```bash
# Deploy new version
anchor upgrade target/deploy/mememarket.so --program-id YOUR_PROGRAM_ID

# Verify upgrade
solana program show YOUR_PROGRAM_ID
```

---

## 📝 Post-Deployment Checklist

- [ ] Contract deployed and verified
- [ ] Oracle wallet funded (>0.5 SOL)
- [ ] Bot running with PM2
- [ ] Monitoring setup and tested
- [ ] Alerts configured
- [ ] Frontend integrated
- [ ] Test market created and resolved
- [ ] Documentation updated
- [ ] Team trained on operations
- [ ] Emergency procedures documented
- [ ] Backup procedures in place

---

## 🎯 Success Criteria

Your deployment is successful when:

✅ Bot runs continuously without errors  
✅ Markets resolve automatically within 5 minutes of conditions being met  
✅ Users can create markets and place bets  
✅ Winners can claim rewards  
✅ Fees are collected in treasury  
✅ No security vulnerabilities detected  
✅ Monitoring shows healthy metrics  

---

## 📚 Additional Resources

- **Security Audit**: `SECURITY_AUDIT.md`
- **Frontend Guide**: `FRONTEND_INTEGRATION.md`
- **Implementation Summary**: `IMPLEMENTATION_SUMMARY.md`
- **Oracle Guide**: `ORACLE_PARIMUTUEL_GUIDE.md`
- **Permissionless Markets**: `PERMISSIONLESS_MARKETS.md`

---

## 🆘 Support

If you encounter issues:

1. Check logs: `pm2 logs parimutuel-bot`
2. Verify configuration: `.env` file
3. Check balances: Oracle and treasury
4. Review security audit: `SECURITY_AUDIT.md`
5. Test on devnet first

---

**Deployment Guide Version**: 1.0  
**Last Updated**: January 4, 2026  
**Status**: Production Ready ✅
