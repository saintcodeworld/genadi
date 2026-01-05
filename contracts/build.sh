#!/bin/bash
set -e

echo "🔧 Building Solana Program with Compatibility Fixes"
echo "=================================================="

# Set PATH to use Solana toolchain
export PATH="$HOME/solana-release/bin:$PATH"

# Clean old artifacts
echo "🧹 Cleaning old build artifacts..."
rm -rf target/deploy/*.so
rm -f Cargo.lock

# Generate lockfile with Rust 1.77.0 (compatible with both)
echo "📦 Generating compatible Cargo.lock..."
cargo +1.77.0 update --workspace 2>/dev/null || cargo update --workspace

# Force lockfile to version 3
if [ -f Cargo.lock ]; then
    echo "🔄 Converting Cargo.lock to version 3..."
    python3 << 'EOF'
with open('Cargo.lock', 'r') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if line.strip() == 'version = 4':
        lines[i] = 'version = 3\n'
        break
with open('Cargo.lock', 'w') as f:
    f.writelines(lines)
EOF
fi

# Build with Solana toolchain
echo "🔨 Building program..."
cd programs/mememarket
cargo-build-sbf

# Check if build succeeded
if [ -f "../../target/deploy/mememarket.so" ]; then
    echo "✅ Build successful!"
    ls -lh ../../target/deploy/mememarket.so
    echo ""
    echo "📦 Next step: Deploy with:"
    echo "   cd /Users/saintcodeworld/Desktop/polymarket/contracts"
    echo "   anchor deploy --provider.cluster devnet"
else
    echo "❌ Build failed - binary not found"
    exit 1
fi
