# MemeMarket - Quick Start Guide

## ⚡ Start the System

```bash
cd /Users/saintcodeworld/Desktop/polymarket
./START_SYSTEM.sh
```

Or manually:
```bash
docker-compose up -d
```

## 🔍 Check Status

```bash
docker-compose ps
```

## 📊 View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f crank
docker-compose logs -f redis
```

## 🛑 Stop the System

```bash
docker-compose down
```

## 🧪 Test the Backend

```bash
# Health check
curl http://localhost:8001/

# Get markets
curl http://localhost:8001/markets

# Get SOL price
curl http://localhost:8001/sol-price
```

## 📝 Configuration

**Program ID**: `CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7`

**Network**: Devnet

**Services**:
- Backend: http://localhost:8001
- Redis: localhost:6379
- Crank: Background service

## 🔧 Common Commands

```bash
# Rebuild and restart
docker-compose up --build -d

# Restart a service
docker-compose restart backend

# View service logs (last 100 lines)
docker-compose logs --tail=100 crank

# Execute command in container
docker-compose exec backend bash
docker-compose exec crank sh

# Remove everything (including volumes)
docker-compose down -v
```

## 📚 Documentation

- **Full Setup Guide**: `DOCKER_SETUP.md`
- **System Structure**: `SYSTEM_STRUCTURE.md`
- **This File**: `QUICK_START.md`

## ⚠️ Prerequisites

- Docker Desktop running
- Solana keypair at `~/.config/solana/id.json`
- Keypair must have SOL on Devnet

## 🚀 Deploy to VPS

1. Copy files to VPS:
```bash
rsync -avz --exclude 'node_modules' --exclude '__pycache__' \
  /Users/saintcodeworld/Desktop/polymarket/ user@vps:/opt/mememarket/
```

2. Copy keypair:
```bash
scp ~/.config/solana/id.json user@vps:/root/.config/solana/id.json
```

3. Start on VPS:
```bash
ssh user@vps
cd /opt/mememarket
docker-compose up -d
```

## 🐛 Troubleshooting

**Port 8001 already in use?**
```bash
# Change port in docker-compose.yml
ports:
  - "8002:8001"
```

**Can't connect to Redis?**
```bash
docker-compose restart redis
docker-compose logs redis
```

**Crank not signing transactions?**
```bash
# Check keypair is mounted
docker-compose exec crank ls -la /root/.config/solana/

# Verify keypair has SOL
solana balance ~/.config/solana/id.json --url devnet
```

**Need to rebuild?**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```
