# Install Docker for macOS

Docker is not currently installed on your system. Here's how to install it:

## Option 1: Download Docker Desktop (Recommended - GUI)

1. **Download Docker Desktop:**
   - Visit: https://www.docker.com/products/docker-desktop
   - Click "Download for Mac"
   - Choose the version for your Mac:
     - **Apple Silicon (M1/M2/M3)**: Download "Mac with Apple chip"
     - **Intel Mac**: Download "Mac with Intel chip"

2. **Install:**
   - Open the downloaded `.dmg` file
   - Drag Docker to Applications folder
   - Open Docker from Applications
   - Follow the setup wizard
   - Docker will ask for permissions - grant them

3. **Verify Installation:**
   ```bash
   docker --version
   docker run hello-world
   ```

4. **Build Your Program:**
   ```bash
   cd /Users/saintcodeworld/Desktop/polymarket/contracts
   rm -f Cargo.lock
   docker run --rm -v "$(pwd):/work" -w /work projectserum/build:v0.29.0 anchor build
   ```

**Time:** 5-10 minutes to download and install

---

## Option 2: Install via Homebrew (Command Line)

If you prefer command-line installation:

```bash
# Install Docker
brew install --cask docker

# Start Docker Desktop
open -a Docker

# Wait for Docker to start (you'll see the whale icon in menu bar)
# Then verify:
docker --version

# Build your program
cd /Users/saintcodeworld/Desktop/polymarket/contracts
rm -f Cargo.lock
docker run --rm -v "$(pwd):/work" -w /work projectserum/build:v0.29.0 anchor build
```

---

## After Docker is Installed

Once Docker is running, execute these commands:

```bash
cd /Users/saintcodeworld/Desktop/polymarket/contracts

# Clean old artifacts
rm -f Cargo.lock

# Build in Docker (this will download the image first time - ~2GB)
docker run --rm -v "$(pwd):/work" -w /work projectserum/build:v0.29.0 anchor build

# Verify binary was created
ls -lh target/deploy/mememarket.so

# Deploy to devnet
anchor deploy --provider.cluster devnet

# Verify deployment
solana program show 5rw87nNYE9Ep7zv6Yv8adK86fP8MSSYRAMq276C8Dbkq --url devnet

# Test the bot
cd crank
npm start
```

---

## What Docker Does

Docker creates a **containerized build environment** with:
- ✅ Correct Rust version (1.68.0)
- ✅ Correct Solana toolchain (1.16.x)
- ✅ Correct Anchor version (0.29.0)
- ✅ All dependencies pre-configured
- ✅ Compatible Cargo.lock generation

This completely bypasses your local Rust version conflicts.

---

## Troubleshooting

### "Docker daemon is not running"
- Make sure Docker Desktop is open and running
- Look for the whale icon in your menu bar
- Wait until it says "Docker Desktop is running"

### "Cannot connect to Docker daemon"
- Restart Docker Desktop
- Or run: `killall Docker && open -a Docker`

### "Permission denied"
- Docker Desktop needs permissions
- Go to System Preferences → Security & Privacy
- Grant permissions to Docker

### First build is slow
- Docker needs to download the build image (~2GB)
- Subsequent builds will be much faster
- The download happens only once

---

## Alternative: Use Homebrew to Install Docker

```bash
brew install --cask docker
```

Then open Docker Desktop from Applications.

---

## Next Steps

1. Install Docker Desktop (5-10 minutes)
2. Start Docker Desktop
3. Run the build command
4. Deploy to devnet
5. Test the bot

**Total time from Docker install to deployed program: ~15-20 minutes**
