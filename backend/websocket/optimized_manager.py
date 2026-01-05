import asyncio
import json
import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import weakref
from dataclasses import dataclass, asdict

from fastapi import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from ..main import PriceUpdate
from ..cache.redis_cache import cache_manager

logger = logging.getLogger(__name__)

@dataclass
class WebSocketMessage:
    type: str
    data: Dict[str, Any]
    timestamp: datetime
    message_id: str

class OptimizedConnectionManager:
    def __init__(self):
        # Active connections with metadata
        self.connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Subscription management
        self.market_subscriptions: Dict[str, Set[str]] = defaultdict(set)  # market_id -> connection_ids
        self.connection_subscriptions: Dict[str, Set[str]] = defaultdict(set)  # connection_id -> market_ids
        
        # Message batching and rate limiting
        self.message_queue: deque = deque()
        self.batch_size = 100
        self.batch_interval = 0.1  # 100ms
        self.rate_limits: Dict[str, deque] = defaultdict(deque)  # connection_id -> timestamps
        self.max_messages_per_second = 10
        
        # Performance monitoring
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_queued': 0,
            'errors': 0,
            'last_cleanup': datetime.now()
        }
        
        # Background tasks
        self.batch_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Start background processors
        self.start_background_processors()

    def start_background_processors(self):
        """Start background tasks for message processing and cleanup"""
        self.batch_task = asyncio.create_task(self.message_batch_processor())
        self.cleanup_task = asyncio.create_task(self.connection_cleanup())

    async def stop_background_processors(self):
        """Stop background tasks"""
        if self.batch_task:
            self.batch_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()

    async def connect(self, websocket: WebSocket, connection_id: str) -> bool:
        """Connect a new WebSocket with optimized handling"""
        try:
            await websocket.accept()
            
            # Store connection with metadata
            self.connections[connection_id] = websocket
            self.connection_metadata[connection_id] = {
                'connected_at': datetime.now(),
                'last_activity': datetime.now(),
                'ip_address': websocket.client.host if websocket.client else 'unknown',
                'user_agent': websocket.headers.get('user-agent', 'unknown'),
                'subscribed_markets': set(),
                'message_count': 0,
                'last_message_sent': None
            }
            
            # Update stats
            self.stats['total_connections'] += 1
            self.stats['active_connections'] = len(self.connections)
            
            # Cache connection count
            await cache_manager.cache_websocket_connections(self.stats['active_connections'])
            
            logger.info(f"WebSocket connected: {connection_id} (total: {self.stats['active_connections']})")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket {connection_id}: {e}")
            self.stats['errors'] += 1
            return False

    async def disconnect(self, connection_id: str):
        """Disconnect a WebSocket with cleanup"""
        if connection_id in self.connections:
            try:
                # Remove from all subscriptions
                await self.unsubscribe_from_all(connection_id)
                
                # Remove connection
                del self.connections[connection_id]
                del self.connection_metadata[connection_id]
                del self.rate_limits[connection_id]
                
                # Update stats
                self.stats['active_connections'] = len(self.connections)
                
                # Cache connection count
                await cache_manager.cache_websocket_connections(self.stats['active_connections'])
                
                logger.info(f"WebSocket disconnected: {connection_id} (total: {self.stats['active_connections']})")
                
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket {connection_id}: {e}")
                self.stats['errors'] += 1

    async def subscribe_to_market(self, connection_id: str, market_id: str):
        """Subscribe a connection to market updates"""
        if connection_id in self.connections and market_id:
            self.market_subscriptions[market_id].add(connection_id)
            self.connection_subscriptions[connection_id].add(market_id)
            
            # Update metadata
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]['subscribed_markets'].add(market_id)
                self.connection_metadata[connection_id]['last_activity'] = datetime.now()

    async def unsubscribe_from_market(self, connection_id: str, market_id: str):
        """Unsubscribe a connection from market updates"""
        if connection_id in self.connections:
            self.market_subscriptions[market_id].discard(connection_id)
            self.connection_subscriptions[connection_id].discard(market_id)
            
            # Clean up empty subscription sets
            if not self.market_subscriptions[market_id]:
                del self.market_subscriptions[market_id]
            
            # Update metadata
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]['subscribed_markets'].discard(market_id)
                self.connection_metadata[connection_id]['last_activity'] = datetime.now()

    async def unsubscribe_from_all(self, connection_id: str):
        """Unsubscribe connection from all markets"""
        if connection_id in self.connection_subscriptions:
            for market_id in self.connection_subscriptions[connection_id].copy():
                await self.unsubscribe_from_market(connection_id, market_id)

    async def send_personal_message(self, message: str, connection_id: str) -> bool:
        """Send a message to a specific connection with rate limiting"""
        if connection_id not in self.connections:
            return False
        
        # Check rate limit
        if not await self.check_rate_limit(connection_id):
            logger.warning(f"Rate limit exceeded for connection {connection_id}")
            return False
        
        try:
            websocket = self.connections[connection_id]
            await websocket.send_text(message)
            
            # Update metadata
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]['message_count'] += 1
                self.connection_metadata[connection_id]['last_message_sent'] = datetime.now()
                self.connection_metadata[connection_id]['last_activity'] = datetime.now()
            
            self.stats['messages_sent'] += 1
            return True
            
        except (WebSocketDisconnect, ConnectionClosed, RuntimeError) as e:
            logger.warning(f"Connection {connection_id} disconnected during send: {e}")
            await self.disconnect(connection_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            self.stats['errors'] += 1
            return False

    async def broadcast_to_market(self, market_id: str, message: str):
        """Broadcast message to all connections subscribed to a market"""
        if market_id not in self.market_subscriptions:
            return
        
        # Get all subscribed connections
        connection_ids = self.market_subscriptions[market_id].copy()
        
        # Queue for batch processing
        for connection_id in connection_ids:
            await self.queue_message(connection_id, message)

    async def broadcast_to_all(self, message: str):
        """Broadcast message to all active connections"""
        connection_ids = list(self.connections.keys())
        
        # Queue for batch processing
        for connection_id in connection_ids:
            await self.queue_message(connection_id, message)

    async def queue_message(self, connection_id: str, message: str):
        """Queue a message for batch processing"""
        self.message_queue.append({
            'connection_id': connection_id,
            'message': message,
            'timestamp': datetime.now()
        })
        self.stats['messages_queued'] += 1

    async def message_batch_processor(self):
        """Background task to process messages in batches"""
        while True:
            try:
                await asyncio.sleep(self.batch_interval)
                
                if not self.message_queue:
                    continue
                
                # Process batch
                batch = []
                while self.message_queue and len(batch) < self.batch_size:
                    batch.append(self.message_queue.popleft())
                
                if batch:
                    await self.process_message_batch(batch)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message batch processor: {e}")
                self.stats['errors'] += 1

    async def process_message_batch(self, batch: List[Dict[str, Any]]):
        """Process a batch of messages efficiently"""
        # Group by connection for efficient sending
        messages_by_connection = defaultdict(list)
        for item in batch:
            messages_by_connection[item['connection_id']].append(item['message'])
        
        # Send messages concurrently
        tasks = []
        for connection_id, messages in messages_by_connection.items():
            if connection_id in self.connections:
                # Send only the latest message for each connection to avoid spam
                latest_message = messages[-1]
                task = asyncio.create_task(
                    self.send_personal_message(latest_message, connection_id)
                )
                tasks.append(task)
        
        # Wait for all sends to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def check_rate_limit(self, connection_id: str) -> bool:
        """Check if connection is within rate limits"""
        now = datetime.now()
        rate_limit_queue = self.rate_limits[connection_id]
        
        # Remove old entries (older than 1 second)
        cutoff = now - timedelta(seconds=1)
        while rate_limit_queue and rate_limit_queue[0] < cutoff:
            rate_limit_queue.popleft()
        
        # Check if under limit
        if len(rate_limit_queue) < self.max_messages_per_second:
            rate_limit_queue.append(now)
            return True
        
        return False

    async def connection_cleanup(self):
        """Background task to clean up dead connections"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                now = datetime.now()
                dead_connections = []
                
                # Check for inactive connections
                for connection_id, metadata in self.connection_metadata.items():
                    last_activity = metadata['last_activity']
                    
                    # Remove connections inactive for more than 5 minutes
                    if now - last_activity > timedelta(minutes=5):
                        dead_connections.append(connection_id)
                
                # Clean up dead connections
                for connection_id in dead_connections:
                    logger.info(f"Cleaning up inactive connection: {connection_id}")
                    await self.disconnect(connection_id)
                
                self.stats['last_cleanup'] = now
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")
                self.stats['errors'] += 1

    async def broadcast_price_update(self, price_update: PriceUpdate):
        """Optimized price update broadcasting"""
        message = json.dumps({
            "type": "price_update",
            "data": asdict(price_update)
        })
        
        # Broadcast to market subscribers
        await self.broadcast_to_market(price_update.market_id, message)
        
        # Cache the price update
        await cache_manager.cache_price_update(price_update)

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get detailed connection statistics"""
        active_connections = len(self.connections)
        total_subscriptions = sum(len(subs) for subs in self.market_subscriptions.values())
        
        return {
            **self.stats,
            'active_connections': active_connections,
            'total_subscriptions': total_subscriptions,
            'average_subscriptions_per_connection': total_subscriptions / active_connections if active_connections > 0 else 0,
            'queue_size': len(self.message_queue),
            'memory_usage': len(self.connections) + len(self.market_subscriptions) + len(self.message_queue)
        }

    async def get_market_stats(self) -> Dict[str, Any]:
        """Get market subscription statistics"""
        market_stats = {}
        for market_id, subscribers in self.market_subscriptions.items():
            market_stats[market_id] = {
                'subscriber_count': len(subscribers),
                'subscriber_ids': list(subscribers)
            }
        
        return market_stats

# Singleton instance
optimized_manager = OptimizedConnectionManager()
