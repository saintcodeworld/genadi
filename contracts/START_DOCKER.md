# Start Docker Desktop

Docker has been installed, but the Docker daemon is not running yet.

## Steps to Start Docker:

1. **Look for Docker in your Applications folder** or use Spotlight (Cmd+Space, type "Docker")

2. **Open Docker Desktop** - You may see a welcome screen or terms of service

3. **Accept Terms** - If prompted, accept the Docker Desktop Service Agreement

4. **Wait for Docker to start** - Look for the whale icon in your menu bar at the top of the screen
   - The whale icon will appear when Docker is starting
   - Wait until the icon is steady (not animated)
   - This usually takes 30-60 seconds

5. **Verify Docker is running:**
   ```bash
   docker --version
   docker ps
   ```

## Once Docker is Running

Run these commands to build your program:

```bash
cd /Users/saintcodeworld/Desktop/polymarket/contracts

# Clean old artifacts
rm -f Cargo.lock

# Build in Docker (first time will download ~2GB image)
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

## Troubleshooting

### "Cannot connect to Docker daemon"
- Make sure Docker Desktop app is open and running
- Look for the whale icon in your menu bar
- If not there, open Docker from Applications

### "Docker Desktop is starting"
- Wait 30-60 seconds for it to fully start
- The whale icon will stop animating when ready

### Need to grant permissions
- Docker may ask for system permissions
- Go to System Preferences → Privacy & Security
- Grant permissions to Docker

---

**Please open Docker Desktop from your Applications folder and wait for it to start, then let me know!**
