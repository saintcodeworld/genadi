# MemeMarket Docker Setup Guide

## Overview
This Docker setup runs the complete MemeMarket system with three services:
- **Redis**: Cache and message broker
- **Backend**: Python FastAPI server
- **Crank**: TypeScript Oracle for market resolution

## Program ID
All services are configured to use the deployed Devnet Program ID:
```
CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7
```

## Prerequisites
- Docker and Docker Compose installed
- Solana keypair at `~/.config/solana/id.json` (for Crank to sign transactions)
- The Solana program deployed on Devnet

## File Structure
```
polymarket/
├── docker-compose.yml          # Main orchestration file
├── backend/
│   ├── Dockerfile              # Backend container definition
│   ├── .dockerignore           # Files to exclude from build
│   ├── .env                    # Backend environment variables
│   ├── requirements.txt        # Python dependencies
│   └── main.py                 # FastAPI application
├── contracts/
│   ├── Anchor.toml             # Program ID configuration
│   ├── target/
│   │   └── idl/
│   │       └── mememarket.json # Program IDL (needed by Crank)
│   └── crank/
│       ├── Dockerfile          # Crank container definition
│       ├── .dockerignore       # Files to exclude from build
│       ├── .env                # Crank environment variables
│       ├── package.json        # Node dependencies
│       └── resolution-bot.ts   # Oracle bot script
└── DOCKER_SETUP.md             # This file
```

## Configuration Files Updated

### 1. `/backend/.env`
```env
REDIS_URL=redis://redis:6379
SOLANA_RPC_URL=https://api.devnet.solana.com
PROGRAM_ID=CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7
```

### 2. `/contracts/crank/.env`
```env
RPC_URL=https://api.devnet.solana.com
PROGRAM_ID=CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7
ORACLE_KEYPAIR_PATH=/root/.config/solana/id.json
```

### 3. `/contracts/Anchor.toml`
```toml
[programs.devnet]
mememarket = "CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7"
```

## Starting the System

### Option 1: Start All Services
```bash
cd /Users/saintcodeworld/Desktop/polymarket
docker-compose up -d
```

### Option 2: Start with Logs
```bash
docker-compose up
```

### Option 3: Rebuild and Start
```bash
docker-compose up --build
```

## Service Access

- **Backend API**: http://localhost:8001
- **Redis**: localhost:6379
- **Crank**: Runs in background (no exposed port)

### API Endpoints
- `GET http://localhost:8001/` - Health check
- `GET http://localhost:8001/markets` - List all markets
- `GET http://localhost:8001/sol-price` - Get current SOL price
- `GET http://localhost:8001/orderbook/{market_id}` - Get order book
- `POST http://localhost:8001/orders/place` - Place an order

## Managing Services

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f crank
docker-compose logs -f redis
```

### Stop Services
```bash
docker-compose down
```

### Stop and Remove Volumes
```bash
docker-compose down -v
```

### Restart a Service
```bash
docker-compose restart backend
docker-compose restart crank
```

### Check Service Status
```bash
docker-compose ps
```

## Wallet Configuration

The Crank service needs access to your Solana keypair to sign transactions. The docker-compose.yml mounts your local keypair:

```yaml
volumes:
  - ~/.config/solana/id.json:/root/.config/solana/id.json:ro
```

**Important**: Ensure your keypair has SOL on Devnet for transaction fees.

## Networking

All services communicate via the `mememarket-network` bridge network:
- Backend connects to Redis using hostname `redis`
- Services can reference each other by service name
- Only Backend port (8001) is exposed to host

## Production Deployment (VPS)

### 1. Copy Files to VPS
```bash
rsync -avz --exclude 'node_modules' --exclude '__pycache__' \
  /Users/saintcodeworld/Desktop/polymarket/ user@your-vps:/opt/mememarket/
```

### 2. Copy Solana Keypair
```bash
scp ~/.config/solana/id.json user@your-vps:/root/.config/solana/id.json
```

### 3. Update docker-compose.yml for Production
- Change `restart: unless-stopped` to `restart: always`
- Remove `--reload` from backend command
- Add proper secrets management
- Configure firewall rules
- Set up SSL/TLS with reverse proxy (nginx/traefik)

### 4. Start on VPS
```bash
cd /opt/mememarket
docker-compose up -d
```

## Troubleshooting

### Backend Can't Connect to Redis
```bash
# Check Redis is running
docker-compose ps redis

# Check Redis logs
docker-compose logs redis

# Verify network
docker network inspect polymarket_mememarket-network
```

### Crank Can't Find Keypair
```bash
# Verify keypair is mounted
docker-compose exec crank ls -la /root/.config/solana/

# Check Crank logs
docker-compose logs crank
```

### Crank Can't Find IDL
```bash
# Verify IDL exists
ls -la contracts/target/idl/mememarket.json

# Rebuild if needed
cd contracts
anchor build
```

### Port Already in Use
```bash
# Change port in docker-compose.yml
ports:
  - "8002:8001"  # Use 8002 instead of 8001
```

## Health Checks

All services have health checks configured:

- **Redis**: Pings every 10s
- **Backend**: HTTP check every 30s
- **Crank**: Process check every 30s

View health status:
```bash
docker-compose ps
```

## Development vs Production

### Development (Current Setup)
- Hot reload enabled for Backend
- Volume mounts for live code updates
- Verbose logging
- Devnet RPC

### Production Recommendations
- Remove volume mounts for code
- Use production RPC (private RPC recommended)
- Configure log rotation
- Set up monitoring (Prometheus/Grafana)
- Use secrets management (Docker secrets, Vault)
- Add rate limiting
- Configure backup for Redis data
- Use mainnet Program ID

## Next Steps

1. **Test the setup**: `docker-compose up`
2. **Verify Backend**: `curl http://localhost:8001/`
3. **Check markets**: `curl http://localhost:8001/markets`
4. **Monitor logs**: `docker-compose logs -f`
5. **Deploy to VPS** when ready

## Environment Variables Reference

### Backend (.env)
- `REDIS_URL`: Redis connection string
- `SOLANA_RPC_URL`: Solana RPC endpoint
- `PROGRAM_ID`: Deployed program address
- `HOST`: Server host (0.0.0.0 for Docker)
- `PORT`: Server port (8001)

### Crank (.env)
- `RPC_URL`: Solana RPC endpoint
- `PROGRAM_ID`: Deployed program address
- `ORACLE_KEYPAIR_PATH`: Path to keypair in container
- `IDL_PATH`: Path to program IDL
- `CHECK_INTERVAL_MS`: Market check interval (60000 = 1 min)
- `MAX_RETRIES`: Max retry attempts (3)
- `RETRY_DELAY_MS`: Delay between retries (5000 = 5s)
