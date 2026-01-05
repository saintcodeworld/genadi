# Price Chart Integration Guide

## Overview
This document explains how to integrate the price chart component into your prediction market platform.

## Components Created

### 1. PriceChart Component (`/components/PriceChart.tsx`)
- **Purpose**: Displays interactive price history charts with real-time updates
- **Features**:
  - SVG-based rendering for performance
  - Interactive crosshair with tooltips
  - Real-time WebSocket updates
  - Trend-based coloring (green/red)
  - Gradient area fills
  - Responsive design

### 2. usePriceChart Hook (`/hooks/usePriceChart.ts`)
- **Purpose**: Data fetching and state management for price charts
- **Features**:
  - GraphQL data fetching
  - WebSocket subscription management
  - Data transformation and normalization
  - Error handling and loading states
  - Real-time price updates

### 3. GraphQL Queries (`/graphql/queries.ts`)
- **Purpose**: GraphQL queries and subscriptions for price data
- **Features**:
  - Market price snapshot queries
  - Real-time trade subscriptions
  - Market information queries

### 4. Type Definitions (`/types/chart.ts`)
- **Purpose**: TypeScript interfaces for chart data
- **Features**:
  - MarketPriceSnapshot interface
  - Trade interface
  - Chart data point types
  - Component props types

## Data Flow Architecture

### 1. Event Listening (Backend/Subgraph)
```
Smart Contract Events → Subgraph → GraphQL API → Frontend
```

### 2. Data Normalization
- All prices stored as values between 0-1 (representing 0%-100%)
- Timestamp aggregation into configurable intervals (1m, 5m, 15m, 1h, 4h, 1d)
- OHLCV data structure for each time bucket

### 3. Current Price Calculation
```typescript
// Primary: Last executed trade price
currentPrice = lastTrade.price

// Fallback: Midpoint of order book
currentPrice = (highestBid + lowestAsk) / 2
```

## Usage Examples

### Basic Usage
```tsx
import { PriceChart } from '@/components/PriceChart';

<PriceChart
  marketId="market-doge-1"
  interval="1h"
  height={400}
  showVolume={true}
  showTooltip={true}
  realTime={true}
/>
```

### Advanced Usage with Market Detail
```tsx
import { MarketDetail } from '@/components/MarketDetail';

<MarketDetail market={marketData} />
```

## GraphQL Schema Requirements

### Market Entity
```graphql
type Market @entity {
  id: ID!
  question: String!
  outcomes: [String!]!
  trades: [Trade!]! @derivedFrom(field: "market")
  currentPrice: BigDecimal!
  totalVolume: BigDecimal!
}
```

### Trade Entity
```graphql
type Trade @entity {
  id: ID!
  market: Market!
  outcomeIndex: Int!
  price: BigDecimal!
  amount: BigDecimal!
  timestamp: BigInt!
  maker: Bytes!
}
```

### MarketPriceSnapshot Entity
```graphql
type MarketPriceSnapshot @entity {
  id: ID!
  market: Market!
  timestamp: BigInt!
  open: BigDecimal!
  high: BigDecimal!
  low: BigDecimal!
  close: BigDecimal!
  volume: BigDecimal!
}
```

## Integration Steps

### 1. Install Dependencies
```bash
npm install @apollo/client graphql
# or
yarn add @apollo/client graphql
```

### 2. Set Up Apollo Client
```tsx
// lib/apollo.ts
import { ApolloClient, InMemoryCache } from '@apollo/client';

const client = new ApolloClient({
  uri: 'https://api.thegraph.com/subgraphs/name/your-subgraph',
  cache: new InMemoryCache(),
});

export default client;
```

### 3. Configure WebSocket Subscriptions
```tsx
// lib/apollo.ts
import { split, HttpLink } from '@apollo/client';
import { getMainDefinition } from '@apollo/client/utilities';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions-ws';

const wsLink = new GraphQLWsLink(
  createClient({ url: 'wss://api.thegraph.com/subgraphs/name/your-subgraph' })
);

const splitLink = split(
  ({ query }) => {
    const definition = getMainDefinition(query);
    return (
      definition.kind === 'OperationDefinition' &&
      definition.operation === 'subscription'
    );
  },
  wsLink,
  httpLink
);
```

### 4. Update usePriceChart Hook
Replace the mock GraphQL client with actual Apollo Client calls in `/hooks/usePriceChart.ts`.

### 5. Add to Market Dashboard
```tsx
// components/MarketDashboard.tsx
import { PriceChart } from '@/components/PriceChart';

// Add to market detail view
{selectedMarket && (
  <PriceChart
    marketId={selectedMarket.id}
    interval="1h"
    height={400}
  />
)}
```

## Customization Options

### Chart Appearance
- **Colors**: Trend-based (green/red) or custom colors
- **Gradients**: Configurable area fill gradients
- **Grid**: Customizable grid lines and labels
- **Tooltips**: Custom tooltip content and styling

### Data Intervals
- **1m**: 1-minute candles (high frequency)
- **5m**: 5-minute candles (default)
- **15m**: 15-minute candles
- **1h**: 1-hour candles
- **4h**: 4-hour candles
- **1d**: Daily candles

### Features
- **Volume Bars**: Optional volume visualization
- **Crosshair**: Interactive price/time display
- **Real-time**: Live price updates via WebSocket
- **Responsive**: Mobile-friendly design

## Performance Considerations

### 1. Data Aggregation
- Use time buckets to reduce data points
- Implement client-side caching
- Paginate historical data

### 2. Rendering Optimization
- SVG for smooth animations
- Debounced mouse events
- Virtual scrolling for large datasets

### 3. WebSocket Management
- Automatic reconnection
- Subscription cleanup
- Error handling

## Testing

### Unit Tests
```tsx
// __tests__/PriceChart.test.tsx
import { render, screen } from '@testing-library/react';
import { PriceChart } from '@/components/PriceChart';

test('renders price chart', () => {
  render(<PriceChart marketId="test-market" />);
  expect(screen.getByText('Loading price data...')).toBeInTheDocument();
});
```

### Integration Tests
- Test GraphQL queries
- Test WebSocket subscriptions
- Test real-time updates

## Demo Page

Visit `/price-chart-demo` to see the chart in action with mock data.

## Troubleshooting

### Common Issues
1. **Apollo Client not found**: Install `@apollo/client`
2. **WebSocket connection failed**: Check WebSocket URL
3. **No data displayed**: Verify GraphQL schema
4. **Performance issues**: Reduce data points or intervals

### Debug Mode
Enable debug logging in the hook:
```tsx
const { data, loading, error } = usePriceChart(marketId, interval);
console.log('Chart data:', data);
console.log('Loading:', loading);
console.log('Error:', error);
```
