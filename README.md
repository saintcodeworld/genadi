# 🎰 MemeMarket Protocol

A high-performance **prediction market platform** for memecoins launching on **pump.fun**, built on **Solana** blockchain.

> Trade YES/NO shares on whether memecoins will hit target market caps. Powered by an on-chain order matching engine with real-time price feeds.

![Solana](https://img.shields.io/badge/Solana-9945FF?style=for-the-badge&logo=solana&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Smart Contracts](#-smart-contracts)
- [Backend API](#-backend-api)
- [Frontend](#-frontend)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference)
- [Contributing](#-contributing)

---

## 🎯 Overview

MemeMarket Protocol enables users to speculate on memecoin performance through binary prediction markets. Users can:

- **Trade YES/NO shares** on memecoin predictions
- **Earn profits** by correctly predicting market cap targets
- **Exit positions** anytime by merging shares back to SOL
- **Trade at market-determined probabilities**

### How YES and NO Shares Work (Polymarket-Style)

#### **The Core Rule: $1 = 1 YES share + 1 NO share**

Every market asks a simple yes/no question like **"Will PEPE reach $100M market cap?"**

#### **How Shares Are Created (Minting)**
When someone wants to buy YES at $0.70 and another person wants to buy NO at $0.30, and their prices add up to exactly **$1.00**, the system matches them. At that moment:
- **1 YES share** is created and given to the YES buyer
- **1 NO share** is created and given to the NO buyer
- Both buyers deposit their respective amounts in **SOL** (calculated using the live SOL/USD price)

#### **What the Price Means**
The price of a share equals the market's belief in that outcome happening:
- If YES is trading at **$0.70**, the market thinks there's a **70% chance** the event will happen
- If NO is at **$0.30**, that's a **30% chance** it won't happen
- These prices **always sum to $1.00** (100%)

#### **How You Make Money**
- Buy YES at $0.70 and the event happens → your share is worth **$1.00** → profit **$0.30**
- Buy YES at $0.70 and the event doesn't happen → your share is worth **$0.00** → lose **$0.70**
- Same logic applies to NO shares, just inverted

#### **How Shares Are Destroyed (Merging)**
If you hold both **1 YES and 1 NO share** for the same market, you can merge them back into **$1.00 worth of SOL** at any time. This is useful for traders who want to exit their position.

#### **Why It Works**
This design ensures the market is always balanced. Every dollar that goes in can only come out when someone wins or merges shares. There's no house edge or liquidity pool manipulation—prices are purely determined by what buyers are willing to pay.

**TL;DR**: Buy YES if you think it'll happen, buy NO if you think it won't. If you're right, you get $1 per share. If you're wrong, you get $0. The price you pay reflects the market's probability estimate.

### Market Flow

1. **Market Creation**: When a new memecoin launches on pump.fun, a prediction market is automatically created
2. **Question**: "Will $TOKEN reach $X market cap by [expiry date]?"
3. **Trading**: Users buy YES shares (bullish) or NO shares (bearish) at market-determined prices
4. **Resolution**: At expiry, the market resolves based on actual market cap
5. **Payout**: Winning shareholders claim $1.00 per share in SOL

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js 16)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ WalletConnect│  │ MarketCard  │  │ PriceChart  │  │ LiveActivityFeed   │ │
│  │   (Phantom)  │  │             │  │  (Recharts) │  │                    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ REST API / WebSocket
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Market API  │  │  WebSocket  │  │ Blockchain  │  │   Redis Cache       │ │
│  │  Endpoints  │  │   Server    │  │   Monitor   │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────────┐  │
│  │ DexScreener │  │  Pump.fun   │  │         Market Paginator            │  │
│  │     API     │  │     API     │  │                                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Solana RPC
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOLANA BLOCKCHAIN (Anchor)                          │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐   │
│  │     Conditional Token System    │  │      Order Matching Engine      │   │
│  │  • mint_shares()                │  │  • place_order()                │   │
│  │  • merge_shares()               │  │  • match_orders()               │   │
│  │  • resolve_market()             │  │  • cancel_order()               │   │
│  │  • claim_winnings()             │  │  • get_order_book()             │   │
│  └─────────────────────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠 Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| **Next.js 16** | React framework with App Router |
| **TypeScript** | Type-safe JavaScript |
| **Tailwind CSS 4** | Utility-first CSS |
| **Shadcn/UI** | Accessible component library |
| **Recharts** | Interactive price charts |
| **Framer Motion** | Smooth animations |
| **Lucide React** | Icon library |
| **@solana/web3.js** | Solana blockchain interaction |
| **@solana/wallet-adapter** | Phantom wallet integration |

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance Python API |
| **Uvicorn** | ASGI server |
| **WebSockets** | Real-time price feeds |
| **Redis** | Caching layer |
| **PostgreSQL** | Off-chain metadata storage |
| **SQLAlchemy** | ORM |
| **aiohttp** | Async HTTP client |
| **Celery** | Background task queue |

### Smart Contracts
| Technology | Purpose |
|------------|---------|
| **Rust** | Smart contract language |
| **Anchor** | Solana development framework |
| **SPL Token** | Token standard |

### External APIs
| Service | Purpose |
|---------|---------|
| **DexScreener** | Real-time token prices & market data |
| **Pump.fun** | New token launches & featured coins |
| **Helius RPC** | Reliable Solana RPC endpoint |

---

## 📁 Project Structure

```
polymarket/
├── backend/                          # FastAPI Backend Server
│   ├── api/                          # External API integrations
│   │   ├── __init__.py
│   │   ├── dexscreener.py           # DexScreener price API client
│   │   └── pumpfun.py               # Pump.fun token API client
│   ├── cache/                        # Caching layer
│   │   ├── __init__.py
│   │   └── redis_cache.py           # Redis cache manager
│   ├── monitoring/                   # Blockchain monitoring
│   │   ├── __init__.py
│   │   └── blockchain_monitor.py    # Real-time token monitoring
│   ├── pagination/                   # API pagination
│   │   ├── __init__.py
│   │   └── market_paginator.py      # Market list pagination
│   ├── websocket/                    # WebSocket handlers
│   │   └── __init__.py
│   ├── main.py                       # FastAPI application entry point
│   ├── requirements.txt              # Python dependencies
│   └── .env.example                  # Environment variables template
│
├── frontend/                         # Next.js Frontend Application
│   ├── public/                       # Static assets
│   │   ├── file.svg
│   │   ├── globe.svg
│   │   ├── next.svg
│   │   ├── vercel.svg
│   │   └── window.svg
│   ├── src/
│   │   ├── app/                      # Next.js App Router
│   │   │   ├── favicon.ico
│   │   │   ├── globals.css          # Global styles & Tailwind
│   │   │   ├── layout.tsx           # Root layout
│   │   │   ├── page.tsx             # Home page
│   │   │   └── price-chart-demo/    # Chart demo page
│   │   ├── components/               # React components
│   │   │   ├── ui/                   # Shadcn UI components
│   │   │   │   ├── badge.tsx
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── progress.tsx
│   │   │   │   ├── select.tsx
│   │   │   │   └── ...
│   │   │   ├── BondingCurveVisualizer.tsx  # Bonding curve display
│   │   │   ├── LiveActivityFeed.tsx        # Real-time trade feed
│   │   │   ├── MarketCard.tsx              # Market display card
│   │   │   ├── MarketDashboard.tsx         # Main dashboard
│   │   │   ├── MarketDetail.tsx            # Market detail view
│   │   │   ├── NotificationManager.tsx     # Toast notifications
│   │   │   ├── OnboardingTutorial.tsx      # User onboarding
│   │   │   ├── PriceChart.tsx              # SVG price chart
│   │   │   ├── PriceChartShadcn.tsx        # Recharts price chart
│   │   │   ├── QuickBet.tsx                # Quick betting interface
│   │   │   ├── TickerTape.tsx              # Price ticker tape
│   │   │   └── WalletConnect.tsx           # Phantom wallet integration
│   │   ├── contexts/                 # React contexts
│   │   │   └── WalletContext.tsx
│   │   ├── graphql/                  # GraphQL queries (if used)
│   │   ├── hooks/                    # Custom React hooks
│   │   │   └── usePriceChart.ts
│   │   ├── lib/                      # Utility libraries
│   │   │   └── utils.ts
│   │   ├── services/                 # API service layer
│   │   │   └── marketService.ts
│   │   └── types/                    # TypeScript type definitions
│   │       ├── chart.ts
│   │       └── market.ts
│   ├── package.json                  # Node.js dependencies
│   ├── tsconfig.json                 # TypeScript configuration
│   ├── tailwind.config.ts            # Tailwind CSS configuration
│   ├── next.config.ts                # Next.js configuration
│   └── components.json               # Shadcn UI configuration
│
├── contracts/                        # Solana Smart Contracts
│   ├── src/
│   │   ├── lib.rs                   # Main contract: Conditional tokens
│   │   ├── order_book.rs            # Order matching engine
│   │   ├── contract.ts              # TypeScript bindings
│   │   └── state.rs                 # Account state definitions
│   ├── Anchor.toml                  # Anchor configuration
│   └── Cargo.toml                   # Rust dependencies
│
├── docs/                            # Documentation
├── .venv/                           # Python virtual environment
└── README.md                        # This file
```

---

## 📜 Smart Contracts

### Conditional Token System (`lib.rs`)

The core prediction market logic implementing conditional tokens:

#### Instructions

| Instruction | Description | Parameters |
|-------------|-------------|------------|
| `initialize_market` | Create a new prediction market | `market_id`, `token_mint`, `target_market_cap`, `expiry_time`, `question` |
| `mint_shares` | Deposit SOL, receive YES + NO shares | `market_id`, `collateral_amount` |
| `merge_shares` | Burn YES + NO shares, reclaim SOL | `market_id`, `share_amount` |
| `resolve_market` | Set winning outcome (YES/NO) | `market_id`, `winning_outcome` |
| `claim_winnings` | Redeem winning shares for SOL | `market_id`, `share_amount` |

#### Account Structure

```rust
pub struct Market {
    pub authority: Pubkey,           // Market creator
    pub market_id: Pubkey,           // Unique identifier
    pub token_mint: Pubkey,          // Memecoin being tracked
    pub target_market_cap: u64,      // Target MC for YES outcome
    pub current_market_cap: u64,     // Current MC (updated by oracle)
    pub expiry_time: i64,            // Unix timestamp
    pub question: String,            // Human-readable question
    pub status: MarketStatus,        // Active, Resolved, Cancelled
    pub winning_outcome: MarketOutcome,
    pub yes_shares_supply: u64,
    pub no_shares_supply: u64,
    pub collateral_pool: u64,        // Total SOL locked
    pub created_at: i64,
    pub resolved_at: Option<i64>,
}
```

### Order Matching System (`order_book.rs`)

Order book matching engine for trading YES/NO shares:

#### Instructions

| Instruction | Description | Parameters |
|-------------|-------------|------------|
| `place_order` | Place a buy order for YES or NO shares | `market_id`, `outcome` (YES/NO), `price`, `amount` |
| `match_orders` | Match complementary orders (YES + NO = $1.00) | `market_id`, `yes_order_id`, `no_order_id` |
| `cancel_order` | Cancel an unfilled order | `order_id` |
| `get_order_book` | Retrieve all open orders for a market | `market_id` |

#### Matching Logic

```
Matching Rule: YES price + NO price = $1.00

Example:
- User A wants to buy YES at $0.70
- User B wants to buy NO at $0.30
- System matches them: creates 1 YES share + 1 NO share
- User A deposits $0.70 in SOL, receives 1 YES share
- User B deposits $0.30 in SOL, receives 1 NO share

No fees on matching (only network fees)
```

---

## 🔌 Backend API

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/markets` | List all active markets |
| `GET` | `/markets/{market_id}` | Get market details |
| `POST` | `/markets/initialize` | Initialize mock markets (dev) |

### WebSocket

Connect to `/ws/{connection_id}` for real-time updates:

```javascript
// Subscribe to market updates
ws.send(JSON.stringify({
  type: "subscribe",
  market_id: "abc123"
}));

// Receive price updates
{
  type: "price_update",
  market_id: "abc123",
  yes_price: 0.65,
  no_price: 0.35,
  timestamp: "2024-01-15T10:30:00Z"
}
```

### Data Models

```python
class Market(BaseModel):
    id: str
    token_symbol: str
    token_address: str
    target_market_cap: float
    current_market_cap: float
    expiry_time: str
    question: str
    yes_price: float
    no_price: float
    total_volume: float
    status: str  # "active", "resolved", "expired"
    winning_outcome: str = None
```

### External API Integrations

#### DexScreener API (`dexscreener.py`)
- `get_token_price(token_address)` - Current price & market data
- `get_pair_info(pair_address)` - Trading pair details
- `search_pairs(query)` - Search tokens
- `get_solana_trending()` - Trending Solana tokens
- `get_historical_prices(pair_address, timeframe)` - OHLCV data

#### Pump.fun API (`pumpfun.py`)
- `get_recent_tokens(limit)` - Recently launched tokens
- `get_token_info(mint_address)` - Token details
- `get_featured_tokens()` - Featured/trending tokens
- `search_tokens(query)` - Search tokens

---

## 💻 Frontend

### Key Components

#### `WalletConnect.tsx`
Phantom wallet integration with:
- Auto-connect for returning users
- Balance display & refresh
- Transaction signing
- Network status (mainnet/devnet)
- Mobile deep-link support

#### `MarketCard.tsx`
Market display card featuring:
- YES/NO price display with trend indicators
- Live trade activity feed
- Interactive price chart
- Quick bet interface
- Progress toward target market cap

#### `PriceChart.tsx` / `PriceChartShadcn.tsx`
Real-time price visualization:
- SVG-based custom chart
- Recharts integration
- Crosshair tooltip
- Volume bars
- Trend direction indicators

#### `LiveActivityFeed.tsx`
Real-time trade stream showing:
- Recent trades with wallet addresses
- Trade amounts in SOL
- YES/NO outcome indicators
- Animated entry/exit

#### `MarketDashboard.tsx`
Main dashboard with:
- Market grid/list views
- Filtering & sorting
- Search functionality
- Pagination

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** 18+ 
- **Python** 3.10+
- **Rust** (for smart contracts)
- **Solana CLI** (for deployment)
- **Redis** (optional, for caching)
- **PostgreSQL** (optional, for persistence)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/mememarket-protocol.git
cd mememarket-protocol
```

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your configuration

# Run the server
uvicorn main:app --reload --port 8001
```

### 3. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### 4. Smart Contract Setup (Optional)

```bash
# Navigate to contracts
cd contracts

# Build contracts
anchor build

# Deploy to devnet
anchor deploy --provider.cluster devnet

# Run tests
anchor test
```

### 5. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

---

## 🔐 Environment Variables

### Backend (`.env`)

```env
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/mememarket

# Redis Configuration
REDIS_URL=redis://localhost:6379

# API Keys
DEXSCREENER_API_KEY=your_dexscreener_api_key
BIRDEYE_API_KEY=your_birdeye_api_key

# Solana Configuration
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY=your_private_key

# Security
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Environment
ENVIRONMENT=development
```

### Frontend (`.env.local`)

```env
# Solana RPC
NEXT_PUBLIC_SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
NEXT_PUBLIC_SOLANA_NETWORK=mainnet-beta
NEXT_PUBLIC_SOLANA_API_KEY=your_api_key

# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001
```

---

## 📚 API Reference

### Market Endpoints

#### Get All Markets
```http
GET /markets
```

**Response:**
```json
[
  {
    "id": "uuid",
    "token_symbol": "PEPE",
    "token_address": "0x123...abc",
    "target_market_cap": 100000000,
    "current_market_cap": 45000000,
    "expiry_time": "2024-01-20T00:00:00Z",
    "question": "Will PEPE reach $100M market cap?",
    "yes_price": 0.45,
    "no_price": 0.55,
    "total_volume": 50000,
    "status": "active"
  }
]
```

#### Get Market by ID
```http
GET /markets/{market_id}
```

#### Initialize Markets (Dev)
```http
POST /markets/initialize
```

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm run test
```

### Smart Contract Tests
```bash
cd contracts
anchor test
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 Links

- **Documentation**: [docs/](./docs/)
- **DexScreener API**: https://docs.dexscreener.com/
- **Pump.fun**: https://pump.fun/
- **Solana**: https://solana.com/
- **Anchor**: https://www.anchor-lang.com/

---

## ⚠️ Disclaimer

This software is provided for educational and research purposes only. Trading prediction markets involves significant financial risk. Always do your own research and never invest more than you can afford to lose.
