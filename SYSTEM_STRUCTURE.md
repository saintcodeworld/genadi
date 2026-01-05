# MemeMarket System Structure

## Complete File Structure

```
polymarket/
│
├── docker-compose.yml              ← Main orchestration file
├── START_SYSTEM.sh                 ← Quick start script
├── DOCKER_SETUP.md                 ← Complete documentation
├── SYSTEM_STRUCTURE.md             ← This file
│
├── backend/                        ← Python FastAPI Backend
│   ├── Dockerfile                  ← Backend container
│   ├── .dockerignore              
│   ├── .env                        ← Backend config (CREATED)
│   ├── .env.example               
│   ├── requirements.txt           
│   ├── main.py                     ← FastAPI application
│   ├── api/
│   │   ├── dexscreener.py
│   │   └── pumpfun.py
│   ├── cache/
│   │   └── redis_cache.py
│   ├── monitoring/
│   │   └── blockchain_monitor.py
│   └── pagination/
│       └── market_paginator.py
│
├── contracts/
│   ├── Anchor.toml                 ← Program ID updated ✓
│   ├── target/
│   │   └── idl/
│   │       └── mememarket.json     ← Needed by Crank
│   └── crank/                      ← TypeScript Oracle
│       ├── Dockerfile              ← Crank container
│       ├── .dockerignore          
│       ├── .env                    ← Crank config (UPDATED)
│       ├── package.json           
│       ├── tsconfig.json          
│       └── resolution-bot.ts       ← Oracle bot
│
└── frontend/                       ← Next.js Frontend (separate)
    └── ...
```

## Services Overview

### 1. Redis (Cache & Message Broker)
- **Image**: redis:7-alpine
- **Port**: 6379
- **Purpose**: Caching and inter-service communication
- **Data**: Persisted in Docker volume

### 2. Backend (Python FastAPI)
- **Build**: `./backend/Dockerfile`
- **Port**: 8001
- **Purpose**: REST API for markets, orders, and trading
- **Dependencies**: Redis
- **Config**: `/backend/.env`

### 3. Crank (TypeScript Oracle)
- **Build**: `./contracts/crank/Dockerfile`
- **Port**: None (background service)
- **Purpose**: Monitor markets and resolve outcomes
- **Dependencies**: Redis, Backend
- **Config**: `/contracts/crank/.env`
- **Keypair**: Mounted from `~/.config/solana/id.json`

## Configuration Summary

### Program ID (All Files Updated)
```
CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7
```

### Updated Files
1. ✅ `/contracts/Anchor.toml` - Program ID updated
2. ✅ `/contracts/crank/.env` - Program ID updated
3. ✅ `/backend/.env` - Created with Program ID

### Network Configuration
- **Network Name**: mememarket-network
- **Type**: Bridge
- **Redis Hostname**: `redis` (used by Backend)

### Volume Mounts
- **Backend**: `./backend:/app` (live reload)
- **Crank**: `./contracts/crank:/app` (live reload)
- **Crank IDL**: `./contracts/target:/app/../target:ro` (read-only)
- **Keypair**: `~/.config/solana/id.json:/root/.config/solana/id.json:ro`
- **Redis Data**: `redis-data` (persistent volume)

## Environment Variables

### Backend Environment
```env
REDIS_URL=redis://redis:6379
SOLANA_RPC_URL=https://api.devnet.solana.com
PROGRAM_ID=CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8001
```

### Crank Environment
```env
RPC_URL=https://api.devnet.solana.com
PROGRAM_ID=CbDHViyDGxLz4Xc11wZmdAoqAKWUmwgXLrtzJ6sSZHT7
ORACLE_KEYPAIR_PATH=/root/.config/solana/id.json
IDL_PATH=../target/idl/mememarket.json
CHECK_INTERVAL_MS=60000
MAX_RETRIES=3
RETRY_DELAY_MS=5000
```

## Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│                  (mememarket-network)                    │
│                                                          │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐     │
│  │  Redis   │◄─────┤ Backend  │      │  Crank   │     │
│  │  :6379   │      │  :8001   │      │ (Oracle) │     │
│  └──────────┘      └─────┬────┘      └────┬─────┘     │
│                          │                  │           │
└──────────────────────────┼──────────────────┼──────────┘
                           │                  │
                    ┌──────▼──────────────────▼──────┐
                    │   Solana Devnet RPC            │
                    │   Program: CbDHViyD...         │
                    └────────────────────────────────┘
```

## Startup Sequence

1. **Redis** starts first (healthcheck: ping)
2. **Backend** waits for Redis to be healthy
3. **Crank** starts after Backend is running
4. All services restart automatically on failure

## Production Readiness

### Current Setup (Development)
- ✅ Hot reload enabled
- ✅ Volume mounts for code
- ✅ Devnet configuration
- ✅ Local keypair mount
- ✅ Health checks configured

### For Production (VPS)
- [ ] Remove `--reload` from Backend
- [ ] Use production RPC endpoint
- [ ] Configure secrets management
- [ ] Set up SSL/TLS reverse proxy
- [ ] Add monitoring (Prometheus/Grafana)
- [ ] Configure log rotation
- [ ] Set up automated backups
- [ ] Use mainnet Program ID
- [ ] Implement rate limiting
- [ ] Add firewall rules
