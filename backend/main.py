from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from enum import Enum
import json
import asyncio
import random
import logging
import os
from datetime import datetime, timedelta
import uuid
from collections import defaultdict

# Import SOL price oracle for live price fetching
from services.sol_price_oracle import sol_price_oracle, SolPriceData

app = FastAPI(title="MemeMarket API - Polymarket Style CLOB")

# Price precision: 1_000_000 = $1.00
PRICE_PRECISION = 1_000_000

# 1 SOL = 1,000,000,000 lamports
LAMPORTS_PER_SOL = 1_000_000_000

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Enums for order types
class OrderSide(str, Enum):
    YES = "YES"
    NO = "NO"

class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

class MarketStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"

# Data models - Polymarket CLOB style
class Market(BaseModel):
    id: str
    token_symbol: str
    token_address: str
    target_market_cap: float
    current_market_cap: float
    expiry_time: str
    question: str
    yes_price: float  # Price in dollars (0.00 - 1.00)
    no_price: float   # Price in dollars (0.00 - 1.00)
    total_volume: float  # Volume in SOL
    total_volume_usd: float  # Volume in USD
    yes_shares_supply: int  # Total YES shares minted
    no_shares_supply: int   # Total NO shares minted
    one_dollar_lamports: int  # SOL equivalent of $1
    status: str
    winning_outcome: Optional[str] = None
    created_at: str
    last_updated: str

class Order(BaseModel):
    id: str
    market_id: str
    owner: str  # Wallet address
    side: OrderSide
    price: float  # Price in dollars (0.00 - 1.00)
    quantity: int  # Number of shares
    filled_quantity: int
    remaining_quantity: int
    lamports_deposited: int
    status: OrderStatus
    is_sell: bool
    created_at: str

class OrderBookLevel(BaseModel):
    price: float
    quantity: int
    num_orders: int

class OrderBook(BaseModel):
    market_id: str
    yes_bids: List[OrderBookLevel]  # Buy orders for YES
    yes_asks: List[OrderBookLevel]  # Sell orders for YES
    no_bids: List[OrderBookLevel]   # Buy orders for NO
    no_asks: List[OrderBookLevel]   # Sell orders for NO
    best_yes_bid: Optional[float]
    best_yes_ask: Optional[float]
    best_no_bid: Optional[float]
    best_no_ask: Optional[float]
    spread: Optional[float]
    last_updated: str

class PlaceOrderRequest(BaseModel):
    market_id: str
    wallet_address: str
    side: OrderSide
    price: float  # Price in dollars (0.00 - 1.00)
    quantity: int  # Number of shares
    is_sell: bool = False

class TradeExecuted(BaseModel):
    id: str
    market_id: str
    yes_order_id: str
    no_order_id: str
    yes_owner: str
    no_owner: str
    yes_price: float
    no_price: float
    quantity: int
    timestamp: str

class UserShares(BaseModel):
    owner: str
    market_id: str
    yes_shares: int
    no_shares: int
    yes_shares_locked: int
    no_shares_locked: int

class PriceUpdate(BaseModel):
    market_id: str
    yes_price: float
    no_price: float
    timestamp: str
    last_trade_quantity: Optional[int] = None

# Storage for markets, orders, and shares
active_markets: Dict[str, Market] = {}
order_books: Dict[str, Dict[str, List[Order]]] = {}  # market_id -> {"yes_bids": [], "yes_asks": [], "no_bids": [], "no_asks": []}
all_orders: Dict[str, Order] = {}  # order_id -> Order
user_shares: Dict[str, Dict[str, UserShares]] = {}  # wallet -> market_id -> UserShares
trades: List[TradeExecuted] = []

async def generate_mock_markets():
    """
    Generate mock prediction markets with CLOB order book - Polymarket style.
    Debug: Fetches live SOL price to calculate one_dollar_lamports.
    """
    mock_tokens = [
        {"symbol": "PEPE", "address": "0x123...abc", "target_mc": 100000000},
        {"symbol": "WIF", "address": "0x456...def", "target_mc": 50000000},
        {"symbol": "BONK", "address": "0x789...ghi", "target_mc": 75000000},
        {"symbol": "DOGE", "address": "0x321...jkl", "target_mc": 200000000},
        {"symbol": "SHIB", "address": "0x654...mno", "target_mc": 150000000},
    ]
    
    now = datetime.now()
    
    # Fetch live SOL price for accurate $1 equivalent
    sol_price_data = await sol_price_oracle.get_sol_price()
    one_dollar_lamports = sol_price_data.one_dollar_lamports
    
    logger.info(f"DEBUG: Using live SOL price: ${sol_price_data.price_usd:.2f}, $1={one_dollar_lamports:,} lamports (source: {sol_price_data.source})")
    
    for token in mock_tokens:
        market_id = str(uuid.uuid4())
        expiry_time = now + timedelta(hours=24)
        
        # Initial prices start at 50/50 (Polymarket style)
        yes_price = 0.50
        no_price = 0.50
        
        market = Market(
            id=market_id,
            token_symbol=token["symbol"],
            token_address=token["address"],
            target_market_cap=token["target_mc"],
            current_market_cap=token["target_mc"] * 0.5,
            expiry_time=expiry_time.isoformat(),
            question=f"Will {token['symbol']} reach ${token['target_mc']:,.0f} market cap?",
            yes_price=yes_price,
            no_price=no_price,
            total_volume=0.0,
            total_volume_usd=0.0,
            yes_shares_supply=0,
            no_shares_supply=0,
            one_dollar_lamports=one_dollar_lamports,  # Live SOL price!
            status="active",
            winning_outcome=None,
            created_at=now.isoformat(),
            last_updated=now.isoformat()
        )
        
        active_markets[market_id] = market
        
        # Initialize order book for this market
        order_books[market_id] = {
            "yes_bids": [],
            "yes_asks": [],
            "no_bids": [],
            "no_asks": []
        }
        
        # Debug: Log market creation
        logger.info(f"DEBUG: Created market {market_id} for {token['symbol']}")
    
    return list(active_markets.values())


def try_match_orders(market_id: str) -> List[TradeExecuted]:
    """
    Core Polymarket matching logic:
    When YES price + NO price = $1.00, match orders and mint shares.
    Debug: Attempts to match complementary orders in the order book.
    """
    if market_id not in order_books:
        return []
    
    executed_trades = []
    book = order_books[market_id]
    market = active_markets.get(market_id)
    
    if not market:
        return []
    
    # Sort bids (buy orders) by price descending (highest first)
    # Sort asks (sell orders) by price ascending (lowest first)
    yes_bids = sorted([o for o in book["yes_bids"] if o.status == OrderStatus.OPEN], 
                      key=lambda x: x.price, reverse=True)
    no_bids = sorted([o for o in book["no_bids"] if o.status == OrderStatus.OPEN], 
                     key=lambda x: x.price, reverse=True)
    
    # Try to match YES bid with NO bid where prices sum to $1
    for yes_order in yes_bids:
        for no_order in no_bids:
            # Core rule: YES price + NO price must equal $1.00
            if abs(yes_order.price + no_order.price - 1.0) < 0.001:
                # Calculate match quantity
                match_qty = min(yes_order.remaining_quantity, no_order.remaining_quantity)
                
                if match_qty > 0:
                    # Debug: Log match
                    logger.info(f"DEBUG: Matching YES@{yes_order.price} with NO@{no_order.price}, qty={match_qty}")
                    
                    # Update orders
                    yes_order.filled_quantity += match_qty
                    yes_order.remaining_quantity -= match_qty
                    if yes_order.remaining_quantity == 0:
                        yes_order.status = OrderStatus.FILLED
                    else:
                        yes_order.status = OrderStatus.PARTIALLY_FILLED
                    
                    no_order.filled_quantity += match_qty
                    no_order.remaining_quantity -= match_qty
                    if no_order.remaining_quantity == 0:
                        no_order.status = OrderStatus.FILLED
                    else:
                        no_order.status = OrderStatus.PARTIALLY_FILLED
                    
                    # Update user shares (mint shares to buyers)
                    _update_user_shares(yes_order.owner, market_id, match_qty, 0)
                    _update_user_shares(no_order.owner, market_id, 0, match_qty)
                    
                    # Update market state
                    market.yes_shares_supply += match_qty
                    market.no_shares_supply += match_qty
                    market.yes_price = yes_order.price
                    market.no_price = no_order.price
                    market.last_updated = datetime.now().isoformat()
                    
                    # Calculate volume
                    volume_lamports = match_qty * market.one_dollar_lamports
                    market.total_volume += volume_lamports / 1e9  # Convert to SOL
                    market.total_volume_usd += match_qty  # Each share pair = $1
                    
                    # Record trade
                    trade = TradeExecuted(
                        id=str(uuid.uuid4()),
                        market_id=market_id,
                        yes_order_id=yes_order.id,
                        no_order_id=no_order.id,
                        yes_owner=yes_order.owner,
                        no_owner=no_order.owner,
                        yes_price=yes_order.price,
                        no_price=no_order.price,
                        quantity=match_qty,
                        timestamp=datetime.now().isoformat()
                    )
                    trades.append(trade)
                    executed_trades.append(trade)
    
    return executed_trades


def _update_user_shares(wallet: str, market_id: str, yes_delta: int, no_delta: int):
    """Helper to update user share balances"""
    if wallet not in user_shares:
        user_shares[wallet] = {}
    
    if market_id not in user_shares[wallet]:
        user_shares[wallet][market_id] = UserShares(
            owner=wallet,
            market_id=market_id,
            yes_shares=0,
            no_shares=0,
            yes_shares_locked=0,
            no_shares_locked=0
        )
    
    shares = user_shares[wallet][market_id]
    shares.yes_shares += yes_delta
    shares.no_shares += no_delta

async def simulate_market_activity():
    """
    Simulate market makers placing orders to create liquidity.
    In production, real users would place these orders.
    Debug: Generates mock orders for testing.
    """
    await asyncio.sleep(3)  # Wait for markets to initialize
    
    while True:
        for market_id, market in active_markets.items():
            if market.status == "active":
                # Simulate a market maker placing complementary orders
                if random.random() < 0.3:  # 30% chance each cycle
                    # Random price between 0.20 and 0.80
                    yes_price = round(random.uniform(0.20, 0.80), 2)
                    no_price = round(1.0 - yes_price, 2)
                    quantity = random.randint(10, 100)
                    
                    # Create matching YES and NO orders
                    yes_order = Order(
                        id=str(uuid.uuid4()),
                        market_id=market_id,
                        owner=f"MM_{random.randint(1,5)}",  # Mock market maker
                        side=OrderSide.YES,
                        price=yes_price,
                        quantity=quantity,
                        filled_quantity=0,
                        remaining_quantity=quantity,
                        lamports_deposited=int(yes_price * quantity * market.one_dollar_lamports),
                        status=OrderStatus.OPEN,
                        is_sell=False,
                        created_at=datetime.now().isoformat()
                    )
                    
                    no_order = Order(
                        id=str(uuid.uuid4()),
                        market_id=market_id,
                        owner=f"MM_{random.randint(1,5)}",
                        side=OrderSide.NO,
                        price=no_price,
                        quantity=quantity,
                        filled_quantity=0,
                        remaining_quantity=quantity,
                        lamports_deposited=int(no_price * quantity * market.one_dollar_lamports),
                        status=OrderStatus.OPEN,
                        is_sell=False,
                        created_at=datetime.now().isoformat()
                    )
                    
                    # Add to order book
                    order_books[market_id]["yes_bids"].append(yes_order)
                    order_books[market_id]["no_bids"].append(no_order)
                    all_orders[yes_order.id] = yes_order
                    all_orders[no_order.id] = no_order
                    
                    # Try to match
                    executed = try_match_orders(market_id)
                    if executed:
                        logger.info(f"DEBUG: Executed {len(executed)} trades for {market.token_symbol}")
        
        await asyncio.sleep(5)  # Simulate activity every 5 seconds

# API Routes
@app.get("/")
async def root():
    return {"message": "MemeMarket Protocol API", "status": "running"}

@app.get("/markets", response_model=List[Market])
async def get_markets():
    """Get all active markets"""
    return list(active_markets.values())

@app.get("/markets/{market_id}", response_model=Market)
async def get_market(market_id: str):
    """Get specific market details"""
    if market_id not in active_markets:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return active_markets[market_id]

@app.post("/markets/initialize")
async def initialize_markets():
    """Initialize mock markets with CLOB order books using live SOL price"""
    markets = await generate_mock_markets()
    return {"message": f"Created {len(markets)} mock markets", "markets": markets}


# ============================================================================
# SOL Price Oracle API - Live Price Fetching
# ============================================================================

@app.get("/sol-price")
async def get_sol_price():
    """
    Get current live SOL/USD price and $1 equivalent in lamports.
    Debug: Returns live price from Jupiter, CoinGecko, or Binance.
    """
    price_data = await sol_price_oracle.get_sol_price()
    return {
        "sol_price_usd": price_data.price_usd,
        "one_dollar_lamports": price_data.one_dollar_lamports,
        "lamports_per_sol": LAMPORTS_PER_SOL,
        "source": price_data.source,
        "timestamp": price_data.timestamp.isoformat(),
        "is_stale": price_data.is_stale
    }


@app.post("/sol-price/refresh")
async def refresh_sol_price():
    """Force refresh SOL price from external APIs"""
    price_data = await sol_price_oracle.get_sol_price(force_refresh=True)
    return {
        "sol_price_usd": price_data.price_usd,
        "one_dollar_lamports": price_data.one_dollar_lamports,
        "source": price_data.source,
        "timestamp": price_data.timestamp.isoformat(),
        "message": "Price refreshed successfully"
    }


# ============================================================================
# Order Book API Endpoints - Polymarket Style CLOB
# ============================================================================

@app.get("/orderbook/{market_id}", response_model=OrderBook)
async def get_orderbook(market_id: str):
    """
    Get the order book for a market.
    Shows all open buy/sell orders for YES and NO shares.
    """
    if market_id not in active_markets:
        raise HTTPException(status_code=404, detail="Market not found")
    
    if market_id not in order_books:
        order_books[market_id] = {"yes_bids": [], "yes_asks": [], "no_bids": [], "no_asks": []}
    
    book = order_books[market_id]
    
    # Aggregate orders by price level
    def aggregate_levels(orders: List[Order], descending: bool = True) -> List[OrderBookLevel]:
        price_levels = defaultdict(lambda: {"quantity": 0, "count": 0})
        for order in orders:
            if order.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
                price_levels[order.price]["quantity"] += order.remaining_quantity
                price_levels[order.price]["count"] += 1
        
        levels = [
            OrderBookLevel(price=p, quantity=d["quantity"], num_orders=d["count"])
            for p, d in price_levels.items()
        ]
        return sorted(levels, key=lambda x: x.price, reverse=descending)
    
    yes_bids = aggregate_levels(book["yes_bids"], descending=True)
    yes_asks = aggregate_levels(book["yes_asks"], descending=False)
    no_bids = aggregate_levels(book["no_bids"], descending=True)
    no_asks = aggregate_levels(book["no_asks"], descending=False)
    
    return OrderBook(
        market_id=market_id,
        yes_bids=yes_bids,
        yes_asks=yes_asks,
        no_bids=no_bids,
        no_asks=no_asks,
        best_yes_bid=yes_bids[0].price if yes_bids else None,
        best_yes_ask=yes_asks[0].price if yes_asks else None,
        best_no_bid=no_bids[0].price if no_bids else None,
        best_no_ask=no_asks[0].price if no_asks else None,
        spread=abs(yes_bids[0].price - yes_asks[0].price) if yes_bids and yes_asks else None,
        last_updated=datetime.now().isoformat()
    )


@app.post("/orders/place")
async def place_order(request: PlaceOrderRequest):
    """
    Place a limit order to buy or sell YES/NO shares.
    Core Polymarket rule: Orders match when YES price + NO price = $1.00
    """
    if request.market_id not in active_markets:
        raise HTTPException(status_code=404, detail="Market not found")
    
    market = active_markets[request.market_id]
    
    # Validate price (must be between 0 and 1)
    if request.price <= 0 or request.price >= 1.0:
        raise HTTPException(status_code=400, detail="Price must be between $0.01 and $0.99")
    
    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    
    # Calculate cost in lamports
    cost_lamports = int(request.price * request.quantity * market.one_dollar_lamports)
    
    # Create order
    order = Order(
        id=str(uuid.uuid4()),
        market_id=request.market_id,
        owner=request.wallet_address,
        side=request.side,
        price=request.price,
        quantity=request.quantity,
        filled_quantity=0,
        remaining_quantity=request.quantity,
        lamports_deposited=cost_lamports,
        status=OrderStatus.OPEN,
        is_sell=request.is_sell,
        created_at=datetime.now().isoformat()
    )
    
    # Add to order book
    if request.market_id not in order_books:
        order_books[request.market_id] = {"yes_bids": [], "yes_asks": [], "no_bids": [], "no_asks": []}
    
    book_key = f"{request.side.value.lower()}_{'asks' if request.is_sell else 'bids'}"
    order_books[request.market_id][book_key].append(order)
    all_orders[order.id] = order
    
    # Debug: Log order placement
    logger.info(f"DEBUG: Order placed - {request.side.value} @ ${request.price} x {request.quantity}")
    
    # Try to match orders
    executed_trades = try_match_orders(request.market_id)
    
    return {
        "order": order,
        "trades_executed": len(executed_trades),
        "message": f"Order placed. {len(executed_trades)} trades executed."
    }


@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str, wallet_address: str):
    """Cancel an open order and refund SOL"""
    if order_id not in all_orders:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = all_orders[order_id]
    
    if order.owner != wallet_address:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order")
    
    if order.status not in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")
    
    order.status = OrderStatus.CANCELLED
    
    # Calculate refund
    refund_ratio = order.remaining_quantity / order.quantity if order.quantity > 0 else 0
    refund_lamports = int(order.lamports_deposited * refund_ratio)
    
    logger.info(f"DEBUG: Order {order_id} cancelled, refund: {refund_lamports} lamports")
    
    return {
        "order_id": order_id,
        "status": "cancelled",
        "refund_lamports": refund_lamports
    }


@app.get("/shares/{wallet_address}/{market_id}")
async def get_user_shares(wallet_address: str, market_id: str):
    """Get user's share holdings for a market"""
    if wallet_address not in user_shares:
        return UserShares(
            owner=wallet_address,
            market_id=market_id,
            yes_shares=0,
            no_shares=0,
            yes_shares_locked=0,
            no_shares_locked=0
        )
    
    if market_id not in user_shares[wallet_address]:
        return UserShares(
            owner=wallet_address,
            market_id=market_id,
            yes_shares=0,
            no_shares=0,
            yes_shares_locked=0,
            no_shares_locked=0
        )
    
    return user_shares[wallet_address][market_id]


@app.get("/trades/{market_id}")
async def get_trades(market_id: str, limit: int = 50):
    """Get recent trades for a market"""
    market_trades = [t for t in trades if t.market_id == market_id]
    return sorted(market_trades, key=lambda x: x.timestamp, reverse=True)[:limit]


@app.get("/orders/{wallet_address}")
async def get_user_orders(wallet_address: str, market_id: Optional[str] = None):
    """Get all orders for a user, optionally filtered by market"""
    user_orders = [o for o in all_orders.values() if o.owner == wallet_address]
    
    if market_id:
        user_orders = [o for o in user_orders if o.market_id == market_id]
    
    return sorted(user_orders, key=lambda x: x.created_at, reverse=True)

@app.websocket("/ws/{connection_id}")
async def websocket_endpoint(websocket: WebSocket, connection_id: str):
    """Simple WebSocket endpoint"""
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle subscription messages
                if message.get("type") == "subscribe":
                    market_id = message.get("market_id")
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "market_id": market_id
                    }))
                
                # Echo back other messages
                else:
                    await websocket.send_text(json.dumps({
                        "type": "echo",
                        "message": f"Received: {data}"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        await websocket.close()

# Background tasks
@app.on_event("startup")
async def startup_event():
    logger.info("Starting MemeMarket Protocol API - Polymarket Style CLOB...")
    
    # Start background SOL price refresh (updates every 30 seconds)
    asyncio.create_task(sol_price_oracle.start_background_refresh(interval_seconds=30))
    logger.info("DEBUG: Started SOL price oracle background refresh")
    
    # Fetch initial SOL price
    initial_price = await sol_price_oracle.get_sol_price()
    logger.info(f"DEBUG: Initial SOL price: ${initial_price.price_usd:.2f} from {initial_price.source}")
    
    # Initialize mock markets with order books (uses live SOL price)
    await generate_mock_markets()
    logger.info(f"DEBUG: Initialized {len(active_markets)} markets with live SOL price")
    
    # Start market activity simulation
    asyncio.create_task(simulate_market_activity())
    logger.info("DEBUG: Started market activity simulation")
    
    logger.info("API startup complete - CLOB ready with live SOL pricing")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down MemeMarket Protocol API...")
    logger.info("API shutdown complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
