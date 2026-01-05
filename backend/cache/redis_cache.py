import redis
import json
import asyncio
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import logging
from dataclasses import asdict
import pickle

from ..main import Market, RealMarket, PriceUpdate

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.default_ttl = 300  # 5 minutes
        self.market_ttl = 60   # 1 minute for market data
        self.price_ttl = 30    # 30 seconds for price data

    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # Handle binary data
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis cache connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

    async def is_available(self) -> bool:
        """Check if Redis is available"""
        if not self.redis_client:
            return False
        try:
            await self.redis_client.ping()
            return True
        except:
            return False

    # Market Caching
    async def cache_market(self, market: Union[Market, RealMarket], ttl: Optional[int] = None):
        """Cache a single market"""
        if not await self.is_available():
            return

        try:
            key = f"market:{market.id}"
            data = json.dumps(market.dict(), default=str)
            await self.redis_client.setex(
                key, 
                ttl or self.market_ttl, 
                data
            )
        except Exception as e:
            logger.error(f"Error caching market {market.id}: {e}")

    async def cache_markets(self, markets: List[Union[Market, RealMarket]], ttl: Optional[int] = None):
        """Cache multiple markets using pipeline"""
        if not await self.is_available():
            return

        try:
            pipe = self.redis_client.pipeline()
            for market in markets:
                key = f"market:{market.id}"
                data = json.dumps(market.dict(), default=str)
                pipe.setex(key, ttl or self.market_ttl, data)
            
            await pipe.execute()
            logger.info(f"Cached {len(markets)} markets")
        except Exception as e:
            logger.error(f"Error caching markets: {e}")

    async def get_market(self, market_id: str) -> Optional[Union[Market, RealMarket]]:
        """Get a single market from cache"""
        if not await self.is_available():
            return None

        try:
            key = f"market:{market_id}"
            data = await self.redis_client.get(key)
            if data:
                market_dict = json.loads(data)
                # Determine if it's a RealMarket or Market based on fields
                if "volume_24h" in market_dict:
                    return RealMarket(**market_dict)
                else:
                    return Market(**market_dict)
        except Exception as e:
            logger.error(f"Error getting market {market_id}: {e}")
        return None

    async def get_markets(self, market_ids: List[str]) -> List[Union[Market, RealMarket]]:
        """Get multiple markets from cache using pipeline"""
        if not await self.is_available():
            return []

        try:
            pipe = self.redis_client.pipeline()
            keys = [f"market:{mid}" for mid in market_ids]
            pipe.mget(keys)
            results = await pipe.execute()
            
            markets = []
            for data in results:
                if data:
                    market_dict = json.loads(data)
                    if "volume_24h" in market_dict:
                        markets.append(RealMarket(**market_dict))
                    else:
                        markets.append(Market(**market_dict))
            
            return markets
        except Exception as e:
            logger.error(f"Error getting markets: {e}")
            return []

    async def delete_market(self, market_id: str):
        """Delete a market from cache"""
        if not await self.is_available():
            return

        try:
            key = f"market:{market_id}"
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error deleting market {market_id}: {e}")

    # Price Update Caching
    async def cache_price_update(self, price_update: PriceUpdate, ttl: Optional[int] = None):
        """Cache a price update"""
        if not await self.is_available():
            return

        try:
            key = f"price_update:{price_update.market_id}"
            data = json.dumps(price_update.dict(), default=str)
            await self.redis_client.setex(
                key, 
                ttl or self.price_ttl, 
                data
            )
        except Exception as e:
            logger.error(f"Error caching price update: {e}")

    async def get_price_update(self, market_id: str) -> Optional[PriceUpdate]:
        """Get a price update from cache"""
        if not await self.is_available():
            return None

        try:
            key = f"price_update:{market_id}"
            data = await self.redis_client.get(key)
            if data:
                price_dict = json.loads(data)
                return PriceUpdate(**price_dict)
        except Exception as e:
            logger.error(f"Error getting price update: {e}")
        return None

    # Market List Caching (for pagination)
    async def cache_market_list(self, market_type: str, markets: List[str], ttl: Optional[int] = None):
        """Cache a list of market IDs by type"""
        if not await self.is_available():
            return

        try:
            key = f"market_list:{market_type}"
            data = json.dumps(markets)
            await self.redis_client.setex(
                key, 
                ttl or self.default_ttl, 
                data
            )
        except Exception as e:
            logger.error(f"Error caching market list: {e}")

    async def get_market_list(self, market_type: str) -> List[str]:
        """Get a list of market IDs by type"""
        if not await self.is_available():
            return []

        try:
            key = f"market_list:{market_type}"
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error getting market list: {e}")
        return []

    # Pagination Support
    async def cache_paginated_markets(self, cache_key: str, markets: List[Dict], total_count: int, ttl: Optional[int] = None):
        """Cache paginated market results"""
        if not await self.is_available():
            return

        try:
            data = {
                "markets": markets,
                "total_count": total_count,
                "cached_at": datetime.now().isoformat()
            }
            await self.redis_client.setex(
                cache_key, 
                ttl or self.default_ttl, 
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.error(f"Error caching paginated markets: {e}")

    async def get_paginated_markets(self, cache_key: str) -> Optional[Dict]:
        """Get cached paginated market results"""
        if not await self.is_available():
            return None

        try:
            data = await self.redis_client.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error getting paginated markets: {e}")
        return None

    # WebSocket Connection Caching
    async def cache_websocket_connections(self, connection_count: int, ttl: Optional[int] = None):
        """Cache WebSocket connection count for monitoring"""
        if not await self.is_available():
            return

        try:
            key = "websocket_connections"
            await self.redis_client.setex(
                key, 
                ttl or 60,  # 1 minute
                connection_count
            )
        except Exception as e:
            logger.error(f"Error caching WebSocket connections: {e}")

    async def get_websocket_connections(self) -> int:
        """Get cached WebSocket connection count"""
        if not await self.is_available():
            return 0

        try:
            key = "websocket_connections"
            count = await self.redis_client.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"Error getting WebSocket connections: {e}")
            return 0

    # Cache Invalidation
    async def invalidate_market_cache(self, market_id: str):
        """Invalidate all cache entries for a specific market"""
        if not await self.is_available():
            return

        try:
            pipe = self.redis_client.pipeline()
            pipe.delete(f"market:{market_id}")
            pipe.delete(f"price_update:{market_id}")
            await pipe.execute()
        except Exception as e:
            logger.error(f"Error invalidating market cache: {e}")

    async def invalidate_all_markets(self):
        """Invalidate all market-related cache entries"""
        if not await self.is_available():
            return

        try:
            pattern = "market:*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
            
            pattern = "price_update:*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
            
            pattern = "market_list:*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)
                
            logger.info("Invalidated all market cache entries")
        except Exception as e:
            logger.error(f"Error invalidating all markets: {e}")

    # Cache Statistics
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        if not await self.is_available():
            return {"error": "Redis not available"}

        try:
            info = await self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}

# Singleton instance
cache_manager = CacheManager()
