# Frontend Integration Guide - Dynamic Market Display

## Overview

This guide shows how to fetch, display, and manage user-created parimutuel markets dynamically on your frontend.

---

## 🎯 Core Concepts

### Market Discovery

Since markets are created permissionlessly, you need to:
1. **Fetch all market accounts** from the program
2. **Filter and sort** based on user preferences
3. **Display with real-time data** (pools, odds, time remaining)
4. **Update dynamically** as new markets are created

---

## 📦 Setup

### Install Dependencies

```bash
npm install @coral-xyz/anchor @solana/web3.js axios
```

### Initialize Anchor Program

```typescript
import * as anchor from "@coral-xyz/anchor";
import { Program, AnchorProvider } from "@coral-xyz/anchor";
import { Connection, PublicKey } from "@solana/web3.js";

const connection = new Connection("https://api.devnet.solana.com", "confirmed");
const programId = new PublicKey("YOUR_PROGRAM_ID");

// Load IDL
const idl = await Program.fetchIdl(programId, provider);
const program = new Program(idl, programId, provider);
```

---

## 🔍 Fetching All Markets

### Method 1: Fetch All Market Accounts

```typescript
interface MarketData {
  publicKey: PublicKey;
  account: {
    creator: PublicKey;
    oracleAuthority: PublicKey;
    tokenMint: PublicKey;
    totalYesPool: anchor.BN;
    totalNoPool: anchor.BN;
    targetMarketCap: anchor.BN;
    deadline: anchor.BN;
    isResolved: boolean;
    winner: boolean | null;
    targetReached: boolean;
    resolvedAt: anchor.BN;
    bump: number;
  };
}

async function fetchAllMarkets(): Promise<MarketData[]> {
  try {
    // Fetch all market accounts
    const markets = await program.account.market.all();
    
    console.log(`Found ${markets.length} markets`);
    return markets;
  } catch (error) {
    console.error("Error fetching markets:", error);
    return [];
  }
}
```

### Method 2: Fetch with Filters

```typescript
async function fetchActiveMarkets(): Promise<MarketData[]> {
  try {
    // Fetch only unresolved markets
    const markets = await program.account.market.all([
      {
        memcmp: {
          offset: 8 + 32 + 32 + 32 + 8 + 8 + 8 + 8, // Offset to is_resolved field
          bytes: anchor.utils.bytes.bs58.encode(Buffer.from([0])), // false
        },
      },
    ]);
    
    return markets;
  } catch (error) {
    console.error("Error fetching active markets:", error);
    return [];
  }
}
```

### Method 3: Fetch by Creator

```typescript
async function fetchMarketsByCreator(creator: PublicKey): Promise<MarketData[]> {
  try {
    const markets = await program.account.market.all([
      {
        memcmp: {
          offset: 8, // Offset to creator field
          bytes: creator.toBase58(),
        },
      },
    ]);
    
    return markets;
  } catch (error) {
    console.error("Error fetching markets by creator:", error);
    return [];
  }
}
```

---

## 🎨 Market Display Component

### React Component Example

```typescript
import React, { useState, useEffect } from 'react';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { PublicKey } from '@solana/web3.js';
import axios from 'axios';

interface Market {
  publicKey: string;
  creator: string;
  tokenMint: string;
  tokenSymbol: string;
  tokenName: string;
  totalYesPool: number;
  totalNoPool: number;
  targetMarketCap: number;
  currentMarketCap: number;
  deadline: number;
  isResolved: boolean;
  winner: boolean | null;
  yesOdds: number;
  noOdds: number;
  timeRemaining: string;
  volume: number;
}

export const MarketsList: React.FC = () => {
  const { connection } = useConnection();
  const { publicKey } = useWallet();
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'resolved'>('active');
  const [sortBy, setSortBy] = useState<'volume' | 'deadline' | 'created'>('volume');

  useEffect(() => {
    loadMarkets();
    
    // Refresh every 30 seconds
    const interval = setInterval(loadMarkets, 30000);
    return () => clearInterval(interval);
  }, [filter, sortBy]);

  async function loadMarkets() {
    try {
      setLoading(true);
      
      // Fetch raw market data
      const rawMarkets = await fetchAllMarkets();
      
      // Enrich with token data and calculations
      const enrichedMarkets = await Promise.all(
        rawMarkets.map(async (market) => await enrichMarketData(market))
      );
      
      // Filter
      let filtered = enrichedMarkets;
      if (filter === 'active') {
        filtered = enrichedMarkets.filter(m => !m.isResolved);
      } else if (filter === 'resolved') {
        filtered = enrichedMarkets.filter(m => m.isResolved);
      }
      
      // Sort
      filtered.sort((a, b) => {
        if (sortBy === 'volume') {
          return b.volume - a.volume;
        } else if (sortBy === 'deadline') {
          return a.deadline - b.deadline;
        } else {
          return 0; // created (already in order)
        }
      });
      
      setMarkets(filtered);
    } catch (error) {
      console.error('Error loading markets:', error);
    } finally {
      setLoading(false);
    }
  }

  async function enrichMarketData(rawMarket: MarketData): Promise<Market> {
    const account = rawMarket.account;
    
    // Fetch token metadata
    const tokenData = await fetchTokenMetadata(account.tokenMint.toString());
    
    // Fetch current market cap
    const currentMarketCap = await fetchCurrentMarketCap(account.tokenMint.toString());
    
    // Calculate pools in SOL
    const totalYesPool = account.totalYesPool.toNumber() / 1e9;
    const totalNoPool = account.totalNoPool.toNumber() / 1e9;
    const totalPool = totalYesPool + totalNoPool;
    
    // Calculate odds
    const yesOdds = totalYesPool > 0 ? totalPool / totalYesPool : 1;
    const noOdds = totalNoPool > 0 ? totalPool / totalNoPool : 1;
    
    // Calculate time remaining
    const deadline = account.deadline.toNumber();
    const now = Math.floor(Date.now() / 1000);
    const timeRemaining = formatTimeRemaining(deadline - now);
    
    return {
      publicKey: rawMarket.publicKey.toString(),
      creator: account.creator.toString(),
      tokenMint: account.tokenMint.toString(),
      tokenSymbol: tokenData.symbol,
      tokenName: tokenData.name,
      totalYesPool,
      totalNoPool,
      targetMarketCap: account.targetMarketCap.toNumber() / 1_000_000,
      currentMarketCap,
      deadline,
      isResolved: account.isResolved,
      winner: account.winner,
      yesOdds,
      noOdds,
      timeRemaining,
      volume: totalPool,
    };
  }

  return (
    <div className="markets-container">
      {/* Filters */}
      <div className="filters">
        <div className="filter-buttons">
          <button 
            className={filter === 'all' ? 'active' : ''}
            onClick={() => setFilter('all')}
          >
            All Markets
          </button>
          <button 
            className={filter === 'active' ? 'active' : ''}
            onClick={() => setFilter('active')}
          >
            Active
          </button>
          <button 
            className={filter === 'resolved' ? 'active' : ''}
            onClick={() => setFilter('resolved')}
          >
            Resolved
          </button>
        </div>
        
        <select 
          value={sortBy} 
          onChange={(e) => setSortBy(e.target.value as any)}
        >
          <option value="volume">Sort by Volume</option>
          <option value="deadline">Sort by Deadline</option>
          <option value="created">Sort by Created</option>
        </select>
      </div>

      {/* Loading State */}
      {loading && <div className="loading">Loading markets...</div>}

      {/* Markets Grid */}
      <div className="markets-grid">
        {markets.map((market) => (
          <MarketCard key={market.publicKey} market={market} />
        ))}
      </div>

      {/* Empty State */}
      {!loading && markets.length === 0 && (
        <div className="empty-state">
          <p>No markets found</p>
          <button onClick={() => window.location.href = '/create'}>
            Create First Market
          </button>
        </div>
      )}
    </div>
  );
};
```

---

## 🃏 Market Card Component

```typescript
interface MarketCardProps {
  market: Market;
}

export const MarketCard: React.FC<MarketCardProps> = ({ market }) => {
  const navigate = useNavigate();
  
  const progressPercentage = Math.min(
    (market.currentMarketCap / market.targetMarketCap) * 100,
    100
  );

  return (
    <div 
      className="market-card"
      onClick={() => navigate(`/market/${market.publicKey}`)}
    >
      {/* Header */}
      <div className="market-header">
        <div className="token-info">
          <img 
            src={`https://logo-api.com/${market.tokenMint}`} 
            alt={market.tokenSymbol}
            className="token-logo"
          />
          <div>
            <h3>{market.tokenSymbol}</h3>
            <p className="token-name">{market.tokenName}</p>
          </div>
        </div>
        
        {market.isResolved && (
          <span className={`badge ${market.winner ? 'yes' : 'no'}`}>
            {market.winner ? 'YES Won' : 'NO Won'}
          </span>
        )}
      </div>

      {/* Question */}
      <div className="market-question">
        Will {market.tokenSymbol} reach ${market.targetMarketCap.toLocaleString()} 
        market cap?
      </div>

      {/* Progress Bar */}
      <div className="progress-section">
        <div className="progress-labels">
          <span>Current: ${market.currentMarketCap.toLocaleString()}</span>
          <span>Target: ${market.targetMarketCap.toLocaleString()}</span>
        </div>
        <div className="progress-bar">
          <div 
            className="progress-fill"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
        <div className="progress-percentage">
          {progressPercentage.toFixed(1)}% of target
        </div>
      </div>

      {/* Odds */}
      <div className="odds-section">
        <div className="odd-item yes">
          <span className="label">YES</span>
          <span className="value">{market.yesOdds.toFixed(2)}x</span>
          <span className="pool">{market.totalYesPool.toFixed(2)} SOL</span>
        </div>
        <div className="odd-item no">
          <span className="label">NO</span>
          <span className="value">{market.noOdds.toFixed(2)}x</span>
          <span className="pool">{market.totalNoPool.toFixed(2)} SOL</span>
        </div>
      </div>

      {/* Footer */}
      <div className="market-footer">
        <div className="time-remaining">
          <ClockIcon />
          {market.isResolved ? 'Resolved' : market.timeRemaining}
        </div>
        <div className="volume">
          Volume: {market.volume.toFixed(2)} SOL
        </div>
      </div>
    </div>
  );
};
```

---

## 🔄 Real-Time Updates

### WebSocket Subscription

```typescript
import { Connection } from '@solana/web3.js';

function subscribeToMarketUpdates(
  connection: Connection,
  programId: PublicKey,
  onUpdate: (markets: MarketData[]) => void
) {
  // Subscribe to program account changes
  const subscriptionId = connection.onProgramAccountChange(
    programId,
    async (accountInfo) => {
      console.log('Market account updated');
      
      // Refresh all markets
      const markets = await fetchAllMarkets();
      onUpdate(markets);
    },
    'confirmed',
    [
      {
        dataSize: 151, // Market account size
      },
    ]
  );

  // Return cleanup function
  return () => {
    connection.removeProgramAccountChangeListener(subscriptionId);
  };
}

// Usage in React
useEffect(() => {
  const unsubscribe = subscribeToMarketUpdates(
    connection,
    programId,
    (markets) => {
      setMarkets(markets);
    }
  );

  return unsubscribe;
}, []);
```

### Polling Strategy

```typescript
function useMarketPolling(intervalMs: number = 30000) {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [lastUpdate, setLastUpdate] = useState<number>(Date.now());

  useEffect(() => {
    async function poll() {
      const markets = await fetchAllMarkets();
      setMarkets(markets);
      setLastUpdate(Date.now());
    }

    poll(); // Initial fetch
    const interval = setInterval(poll, intervalMs);

    return () => clearInterval(interval);
  }, [intervalMs]);

  return { markets, lastUpdate };
}
```

---

## 🔍 Search and Filter

### Search Component

```typescript
export const MarketSearch: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [markets, setMarkets] = useState<Market[]>([]);
  const [filteredMarkets, setFilteredMarkets] = useState<Market[]>([]);

  useEffect(() => {
    // Filter markets based on search term
    const filtered = markets.filter((market) => {
      const term = searchTerm.toLowerCase();
      return (
        market.tokenSymbol.toLowerCase().includes(term) ||
        market.tokenName.toLowerCase().includes(term) ||
        market.publicKey.toLowerCase().includes(term)
      );
    });
    
    setFilteredMarkets(filtered);
  }, [searchTerm, markets]);

  return (
    <div className="search-container">
      <input
        type="text"
        placeholder="Search markets by token symbol, name, or address..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="search-input"
      />
      
      <div className="search-results">
        {filteredMarkets.map((market) => (
          <MarketCard key={market.publicKey} market={market} />
        ))}
      </div>
    </div>
  );
};
```

### Advanced Filters

```typescript
interface FilterOptions {
  status: 'all' | 'active' | 'resolved';
  minVolume: number;
  maxVolume: number;
  timeframe: 'all' | '24h' | '7d' | '30d';
  sortBy: 'volume' | 'deadline' | 'odds' | 'created';
  sortOrder: 'asc' | 'desc';
}

function applyFilters(markets: Market[], filters: FilterOptions): Market[] {
  let filtered = [...markets];

  // Status filter
  if (filters.status === 'active') {
    filtered = filtered.filter(m => !m.isResolved);
  } else if (filters.status === 'resolved') {
    filtered = filtered.filter(m => m.isResolved);
  }

  // Volume filter
  filtered = filtered.filter(m => 
    m.volume >= filters.minVolume && m.volume <= filters.maxVolume
  );

  // Timeframe filter
  const now = Math.floor(Date.now() / 1000);
  if (filters.timeframe !== 'all') {
    const timeframes = {
      '24h': 86400,
      '7d': 604800,
      '30d': 2592000,
    };
    const cutoff = now + timeframes[filters.timeframe];
    filtered = filtered.filter(m => m.deadline <= cutoff);
  }

  // Sort
  filtered.sort((a, b) => {
    let comparison = 0;
    
    switch (filters.sortBy) {
      case 'volume':
        comparison = a.volume - b.volume;
        break;
      case 'deadline':
        comparison = a.deadline - b.deadline;
        break;
      case 'odds':
        comparison = a.yesOdds - b.yesOdds;
        break;
      default:
        comparison = 0;
    }
    
    return filters.sortOrder === 'asc' ? comparison : -comparison;
  });

  return filtered;
}
```

---

## 📊 Market Statistics Dashboard

```typescript
export const MarketStats: React.FC = () => {
  const [stats, setStats] = useState({
    totalMarkets: 0,
    activeMarkets: 0,
    resolvedMarkets: 0,
    totalVolume: 0,
    totalFees: 0,
    averageVolume: 0,
  });

  useEffect(() => {
    async function calculateStats() {
      const markets = await fetchAllMarkets();
      
      const totalMarkets = markets.length;
      const activeMarkets = markets.filter(m => !m.account.isResolved).length;
      const resolvedMarkets = markets.filter(m => m.account.isResolved).length;
      
      const totalVolume = markets.reduce((sum, m) => {
        const yes = m.account.totalYesPool.toNumber() / 1e9;
        const no = m.account.totalNoPool.toNumber() / 1e9;
        return sum + yes + no;
      }, 0);
      
      const totalFees = totalMarkets * 0.015; // Creation fees
      const averageVolume = totalVolume / totalMarkets || 0;
      
      setStats({
        totalMarkets,
        activeMarkets,
        resolvedMarkets,
        totalVolume,
        totalFees,
        averageVolume,
      });
    }
    
    calculateStats();
  }, []);

  return (
    <div className="stats-dashboard">
      <StatCard 
        title="Total Markets" 
        value={stats.totalMarkets} 
        icon="📊"
      />
      <StatCard 
        title="Active Markets" 
        value={stats.activeMarkets} 
        icon="🟢"
      />
      <StatCard 
        title="Resolved Markets" 
        value={stats.resolvedMarkets} 
        icon="✅"
      />
      <StatCard 
        title="Total Volume" 
        value={`${stats.totalVolume.toFixed(2)} SOL`} 
        icon="💰"
      />
      <StatCard 
        title="Platform Fees" 
        value={`${stats.totalFees.toFixed(3)} SOL`} 
        icon="💵"
      />
      <StatCard 
        title="Avg Volume" 
        value={`${stats.averageVolume.toFixed(2)} SOL`} 
        icon="📈"
      />
    </div>
  );
};
```

---

## 🌐 Fetching Token Metadata

### DexScreener API

```typescript
async function fetchTokenMetadata(tokenMint: string) {
  try {
    const response = await axios.get(
      `https://api.dexscreener.com/latest/dex/tokens/${tokenMint}`
    );
    
    if (response.data?.pairs && response.data.pairs.length > 0) {
      const pair = response.data.pairs[0];
      return {
        symbol: pair.baseToken.symbol,
        name: pair.baseToken.name,
        logo: pair.info?.imageUrl || '',
      };
    }
    
    return {
      symbol: 'UNKNOWN',
      name: 'Unknown Token',
      logo: '',
    };
  } catch (error) {
    console.error('Error fetching token metadata:', error);
    return {
      symbol: 'UNKNOWN',
      name: 'Unknown Token',
      logo: '',
    };
  }
}
```

### Current Market Cap

```typescript
async function fetchCurrentMarketCap(tokenMint: string): Promise<number> {
  try {
    const response = await axios.get(
      `https://api.dexscreener.com/latest/dex/tokens/${tokenMint}`
    );
    
    if (response.data?.pairs && response.data.pairs.length > 0) {
      const pair = response.data.pairs[0];
      return parseFloat(pair.fdv || pair.marketCap || '0');
    }
    
    return 0;
  } catch (error) {
    console.error('Error fetching market cap:', error);
    return 0;
  }
}
```

---

## 🎨 Styling Example (CSS)

```css
.markets-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.filters {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  gap: 1rem;
}

.filter-buttons {
  display: flex;
  gap: 0.5rem;
}

.filter-buttons button {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  background: white;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-buttons button.active {
  background: #4F46E5;
  color: white;
  border-color: #4F46E5;
}

.markets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.market-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.market-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.market-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.token-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.token-logo {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.market-question {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: #1f2937;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin: 0.5rem 0;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4F46E5, #7C3AED);
  transition: width 0.3s;
}

.odds-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin: 1rem 0;
}

.odd-item {
  padding: 1rem;
  border-radius: 8px;
  text-align: center;
}

.odd-item.yes {
  background: #dcfce7;
  border: 1px solid #86efac;
}

.odd-item.no {
  background: #fee2e2;
  border: 1px solid #fca5a5;
}

.market-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 1rem;
  border-top: 1px solid #e5e7eb;
  font-size: 0.875rem;
  color: #6b7280;
}

.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge.yes {
  background: #dcfce7;
  color: #166534;
}

.badge.no {
  background: #fee2e2;
  color: #991b1b;
}
```

---

## 🚀 Performance Optimization

### Pagination

```typescript
function usePaginatedMarkets(pageSize: number = 20) {
  const [allMarkets, setAllMarkets] = useState<Market[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  
  const totalPages = Math.ceil(allMarkets.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const currentMarkets = allMarkets.slice(startIndex, endIndex);
  
  return {
    markets: currentMarkets,
    currentPage,
    totalPages,
    nextPage: () => setCurrentPage(p => Math.min(p + 1, totalPages)),
    prevPage: () => setCurrentPage(p => Math.max(p - 1, 1)),
    goToPage: (page: number) => setCurrentPage(page),
  };
}
```

### Caching

```typescript
const marketCache = new Map<string, { data: Market; timestamp: number }>();
const CACHE_DURATION = 30000; // 30 seconds

async function fetchMarketWithCache(publicKey: string): Promise<Market> {
  const cached = marketCache.get(publicKey);
  const now = Date.now();
  
  if (cached && now - cached.timestamp < CACHE_DURATION) {
    return cached.data;
  }
  
  const market = await fetchMarket(publicKey);
  marketCache.set(publicKey, { data: market, timestamp: now });
  
  return market;
}
```

---

## 📱 Mobile Responsive

```css
@media (max-width: 768px) {
  .markets-grid {
    grid-template-columns: 1fr;
  }
  
  .filters {
    flex-direction: column;
    align-items: stretch;
  }
  
  .filter-buttons {
    width: 100%;
    justify-content: space-between;
  }
  
  .odds-section {
    grid-template-columns: 1fr;
  }
}
```

---

## 🔔 Notifications

### New Market Alerts

```typescript
function useNewMarketNotifications() {
  const [lastMarketCount, setLastMarketCount] = useState(0);
  
  useEffect(() => {
    async function checkNewMarkets() {
      const markets = await fetchAllMarkets();
      
      if (lastMarketCount > 0 && markets.length > lastMarketCount) {
        const newCount = markets.length - lastMarketCount;
        showNotification(`${newCount} new market(s) created!`);
      }
      
      setLastMarketCount(markets.length);
    }
    
    const interval = setInterval(checkNewMarkets, 60000);
    return () => clearInterval(interval);
  }, [lastMarketCount]);
}

function showNotification(message: string) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('Polymarket', { body: message });
  }
}
```

---

## 📊 Analytics Integration

```typescript
// Track market views
function trackMarketView(marketId: string) {
  // Send to analytics
  analytics.track('Market Viewed', {
    marketId,
    timestamp: Date.now(),
  });
}

// Track bet placements
function trackBetPlaced(marketId: string, amount: number, side: boolean) {
  analytics.track('Bet Placed', {
    marketId,
    amount,
    side: side ? 'YES' : 'NO',
    timestamp: Date.now(),
  });
}
```

---

## 🎯 Summary

### Key Points

1. **Fetch all markets** using `program.account.market.all()`
2. **Enrich with token data** from DexScreener/Birdeye
3. **Calculate odds dynamically** from pool sizes
4. **Filter and sort** based on user preferences
5. **Update in real-time** with WebSocket or polling
6. **Cache aggressively** to reduce RPC calls
7. **Paginate** for performance with many markets
8. **Make responsive** for mobile devices

### Performance Tips

- Cache token metadata (rarely changes)
- Use pagination for large market lists
- Implement virtual scrolling for infinite lists
- Debounce search inputs
- Use WebSocket for real-time updates
- Batch RPC calls when possible

### User Experience

- Show loading states
- Display empty states
- Add search and filters
- Show real-time odds updates
- Highlight trending markets
- Enable notifications for new markets

This frontend integration enables a fully dynamic, user-friendly interface for displaying all user-created markets! 🚀
