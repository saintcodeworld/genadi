# Install Solana BPF Toolchain - Solutions

## Problem
The command `cargo-build-sbf` is not found, which prevents Anchor from building Solana programs.

## Current Status
- ❌ Solana BPF toolchain not installed
- ✅ IDL fixed (changed `publicKey` to `pubkey`)
- ✅ Program code compiles
- ⏳ Homebrew reinstall running (slow)

## Quick Solutions

### Solution 1: Use Docker (FASTEST - Recommended)

This bypasses all installation issues:

```bash
# Install Docker Desktop if not installed
# Download from: https://www.docker.com/products/docker-desktop

# Once Docker is running, build with Anchor's Docker image
cd /Users/saintcodeworld/Desktop/polymarket/contracts
docker run --rm -v "$(pwd)":/workspace -w /workspace projectserum/build:v0.29.0 anchor build

# Then deploy
anchor deploy --provider.cluster devnet
```

### Solution 2: Manual Solana Install (Alternative Network)

Try downloading directly with different SSL settings:

```bash
# Try with insecure flag (only for devnet testing)
curl -k -sSfL https://release.solana.com/v1.18.20/install | sh

# Or try older version
curl -sSfL https://release.solana.com/v1.17.0/install | sh

# Add to PATH
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"

# Verify
cargo-build-sbf --version
```

### Solution 3: Use VPN or Different Network

The SSL error suggests network restrictions. Try:
1. Connect to a VPN
2. Use mobile hotspot
3. Try from a different location

Then retry:
```bash
sh -c "$(curl -sSfL https://release.solana.com/v1.18.20/install)"
```

### Solution 4: Wait for Homebrew (Currently Running)

The `brew reinstall solana --build-from-source` is running. This will take 30-60 minutes but should include all build tools.

Check status:
```bash
ps aux | grep brew
```

### Solution 5: Use Pre-built Binary (Manual)

Download and extract manually:

```bash
cd ~
# Download for macOS ARM (M1/M2)
curl -LO https://github.com/solana-labs/solana/releases/download/v1.18.20/solana-release-aarch64-apple-darwin.tar.bz2

# Extract
tar -xjf solana-release-aarch64-apple-darwin.tar.bz2

# Add to PATH
export PATH="$HOME/solana-release/bin:$PATH"

# Verify
cargo-build-sbf --version
```

## After Installation

Once `cargo-build-sbf` is available, run:

```bash
cd /Users/saintcodeworld/Desktop/polymarket/contracts

# Build
anchor build

# Verify binary created
ls -lh target/deploy/mememarket.so

# Deploy
anchor deploy --provider.cluster devnet

# Verify on-chain
solana program show 5rw87nNYE9Ep7zv6Yv8adK86fP8MSSYRAMq276C8Dbkq --url devnet

# Test bot
cd crank
npm start
```

## Verification Commands

Check if toolchain is installed:
```bash
# Should show version number
cargo-build-sbf --version

# Should show solana tools
which solana
which cargo-build-sbf

# Should show in cargo list
cargo --list | grep build-sbf
```

## Current Error Explained

```
error: no such command: `build-sbf`
```

This means Rust's cargo doesn't have the Solana BPF compiler plugin installed. This plugin is part of the Solana toolchain, not Rust itself.

The Homebrew Solana package (currently installed) only includes CLI tools, not the build toolchain.

## Recommended Next Steps

1. **If you have Docker**: Use Solution 1 (fastest, 5 minutes)
2. **If no Docker**: Try Solution 5 (manual download, 10 minutes)
3. **If neither works**: Wait for Homebrew build (30-60 minutes)

## Test Without Deployment

You can test the bot's connection logic without deploying:

```bash
cd /Users/saintcodeworld/Desktop/polymarket/contracts/crank
npx ts-node simple-test.ts
```

This will show that everything else is configured correctly, just waiting for program deployment.

---

**Bottom Line**: The code is ready. We just need the Solana build tools installed to create the `.so` binary file for deployment.
