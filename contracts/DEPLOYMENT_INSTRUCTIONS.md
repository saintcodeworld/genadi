# Deployment Instructions - Parimutuel Betting System

## Current Status

✅ **COMPLETED:**
1. lib.rs cleaned - removed all CLOB/orderbook code
2. Only parimutuel module remains (pool-based betting with 0.015 SOL fee)
3. Program compiles successfully with `anchor build`
4. IDL generated correctly

❌ **BLOCKER:**
The Solana BPF toolchain (`cargo-build-sbf`) is not installed, which prevents Anchor from building the `.so` binary file needed for deployment.

## Solution: Install Solana BPF Toolchain

### Option 1: Install Full Solana Toolchain (Recommended)

Run these commands:

```bash
# Download and install Solana toolchain
sh -c "$(curl -sSfL https://release.solana.com/v1.18.20/install)"

# Add to PATH
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"

# Verify installation
cargo-build-sbf --version
```

### Option 2: Use Docker (If network issues persist)

```bash
# Pull Solana build image
docker pull projectserum/build:v0.27.0

# Build in Docker
docker run --rm -v $(pwd):/workspace -w /workspace projectserum/build:v0.27.0 anchor build
```

### Option 3: Use Anchor Verifiable Build

```bash
# This uses Docker internally
anchor build --verifiable
```

## After Toolchain Installation

### Step 1: Build the Program

```bash
cd /Users/saintcodeworld/Desktop/polymarket/contracts
source $HOME/.cargo/env
anchor build
```

**Expected output:**
```
Compiling mememarket v0.1.0
    Finished release [optimized] target(s) in X.XXs
```

**Verify binary created:**
```bash
ls -lh target/deploy/mememarket.so
```

You should see a file around 200-500KB.

### Step 2: Deploy to Devnet

```bash
anchor deploy --provider.cluster devnet
```

**Expected output:**
```
Deploying cluster: https://api.devnet.solana.com
Upgrade authority: /Users/saintcodeworld/.config/solana/id.json
Deploying program "mememarket"...
Program path: /Users/saintcodeworld/Desktop/polymarket/contracts/target/deploy/mememarket.so
Program Id: 5rw87nNYE9Ep7zv6Yv8adK86fP8MSSYRAMq276C8Dbkq

Deploy success
```

### Step 3: Verify Deployment

```bash
solana program show 5rw87nNYE9Ep7zv6Yv8adK86fP8MSSYRAMq276C8Dbkq --url devnet
```

**Expected output:**
```
Program Id: 5rw87nNYE9Ep7zv6Yv8adK86fP8MSSYRAMq276C8Dbkq
Owner: BPFLoaderUpgradeab1e11111111111111111111111
ProgramData Address: <address>
Authority: <your wallet>
Last Deployed In Slot: <slot number>
Data Length: <size> bytes
Balance: <SOL amount>
```

### Step 4: Test the Bot

```bash
cd crank
npx ts-node simple-test.ts
```

This should now show:
```
✅ Program found on-chain
   Executable: true
   Owner: BPFLoaderUpgradeab1e11111111111111111111111
```

Then start the resolution bot:
```bash
npm start
```

## What's Been Cleaned

### Removed from lib.rs:
- ❌ CLOB order book system
- ❌ `initialize_market` (CLOB version)
- ❌ `update_sol_price`
- ❌ `place_order`
- ❌ `match_orders`
- ❌ `place_sell_order`
- ❌ `match_sell_orders`
- ❌ `cancel_order`
- ❌ `resolve_market` (CLOB version)
- ❌ `redeem_shares`
- ❌ All CLOB account structures (Market, Order, UserShares)
- ❌ All CLOB enums (MarketStatus, OrderSide, OrderStatus, etc.)
- ❌ All CLOB context structs
- ❌ All CLOB events

### Kept in lib.rs:
- ✅ `parimutuel_initialize_market` - Create market with 0.015 SOL fee
- ✅ `parimutuel_place_bet` - Bet on YES or NO
- ✅ `parimutuel_resolve_market` - Oracle resolution
- ✅ `parimutuel_claim_reward` - Claim winnings

### Parimutuel Module (src/parimutuel.rs):
- ✅ Market creation fee: 0.015 SOL to treasury
- ✅ Pool-based betting (YES pool + NO pool)
- ✅ Oracle authority verification
- ✅ Automatic resolution based on market cap
- ✅ Proportional reward distribution
- ✅ Overflow protection with checked math
- ✅ Double-claim prevention
- ✅ Secure PDA escrow

## Current File Structure

```
contracts/
├── src/
│   ├── lib.rs (CLEAN - only parimutuel)
│   └── parimutuel.rs (complete betting logic)
├── programs/
│   └── mememarket/
│       ├── src/
│       │   ├── lib.rs
│       │   └── parimutuel.rs
│       └── Cargo.toml
├── crank/
│   ├── resolution-bot.ts (ready)
│   ├── simple-test.ts (working)
│   ├── .env (configured)
│   ├── oracle-keypair.json (funded with 5 SOL)
│   └── package.json
├── Anchor.toml
├── Cargo.toml (workspace)
└── target/
    ├── idl/
    │   └── mememarket.json (generated)
    └── deploy/
        └── mememarket-keypair.json
```

## Quick Commands Reference

```bash
# Build
anchor build

# Deploy
anchor deploy --provider.cluster devnet

# Verify
solana program show 5rw87nNYE9Ep7zv6Yv8adK86fP8MSSYRAMq276C8Dbkq --url devnet

# Test connection
cd crank && npx ts-node simple-test.ts

# Start bot
cd crank && npm start
```

## Troubleshooting

### "cargo-build-sbf: command not found"
Install Solana toolchain (see Option 1 above)

### "Program not found on-chain"
The program hasn't been deployed yet. Complete the build and deploy steps.

### "IDL parsing error" in bot
This will be fixed once the program is deployed and Anchor generates the correct IDL.

### Network/SSL errors during Solana install
Try using a VPN or different network, or use Docker (Option 2)

---

**Next Step**: Install Solana BPF toolchain using one of the options above, then run the deployment commands.
