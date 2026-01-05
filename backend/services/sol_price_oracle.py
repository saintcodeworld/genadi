"""
SOL Price Oracle Service
Fetches live SOL/USD price from multiple sources and calculates lamports per dollar.
Debug: Provides real-time SOL price for accurate $1 equivalent calculations.
"""

import asyncio
import aiohttp
import logging
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 1 SOL = 1,000,000,000 lamports
LAMPORTS_PER_SOL = 1_000_000_000

# Cache duration in seconds
CACHE_DURATION_SECONDS = 30

# Fallback price if all APIs fail (used only as last resort)
FALLBACK_SOL_PRICE_USD = 130.0


@dataclass
class SolPriceData:
    """Container for SOL price data"""
    price_usd: float
    one_dollar_lamports: int
    source: str
    timestamp: datetime
    is_stale: bool = False


class SolPriceOracle:
    """
    Fetches live SOL/USD price from multiple sources.
    Calculates the lamports equivalent of $1 USD.
    Debug: Uses Jupiter, CoinGecko, and Binance as price sources.
    """
    
    def __init__(self):
        self._cached_price: Optional[SolPriceData] = None
        self._cache_timestamp: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    def _calculate_one_dollar_lamports(self, sol_price_usd: float) -> int:
        """
        Calculate how many lamports equal $1 USD.
        Formula: lamports_per_dollar = LAMPORTS_PER_SOL / sol_price_usd
        
        Example at $130/SOL:
        - 1 SOL = 1,000,000,000 lamports
        - $1 = 1,000,000,000 / 130 = 7,692,307 lamports
        """
        if sol_price_usd <= 0:
            logger.error("DEBUG: Invalid SOL price, using fallback")
            sol_price_usd = FALLBACK_SOL_PRICE_USD
        
        one_dollar_lamports = int(LAMPORTS_PER_SOL / sol_price_usd)
        
        # Debug: Log calculation
        logger.info(f"DEBUG: SOL=${sol_price_usd:.2f}, $1={one_dollar_lamports:,} lamports")
        
        return one_dollar_lamports
    
    async def _fetch_from_coingecko(self, session: aiohttp.ClientSession) -> Optional[float]:
        """Fetch SOL price from CoinGecko API (free, no API key required)"""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get("solana", {}).get("usd")
                    if price:
                        logger.info(f"DEBUG: CoinGecko SOL price: ${price}")
                        return float(price)
        except Exception as e:
            logger.warning(f"DEBUG: CoinGecko fetch failed: {e}")
        return None
    
    async def _fetch_from_jupiter(self, session: aiohttp.ClientSession) -> Optional[float]:
        """Fetch SOL price from Jupiter API (Solana-native)"""
        try:
            # Jupiter price API for SOL
            url = "https://price.jup.ag/v4/price?ids=SOL"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get("data", {}).get("SOL", {}).get("price")
                    if price:
                        logger.info(f"DEBUG: Jupiter SOL price: ${price}")
                        return float(price)
        except Exception as e:
            logger.warning(f"DEBUG: Jupiter fetch failed: {e}")
        return None
    
    async def _fetch_from_binance(self, session: aiohttp.ClientSession) -> Optional[float]:
        """Fetch SOL price from Binance API"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get("price")
                    if price:
                        logger.info(f"DEBUG: Binance SOL price: ${price}")
                        return float(price)
        except Exception as e:
            logger.warning(f"DEBUG: Binance fetch failed: {e}")
        return None
    
    async def get_sol_price(self, force_refresh: bool = False) -> SolPriceData:
        """
        Get current SOL price with caching.
        Tries multiple sources in order of preference.
        Debug: Returns cached price if fresh, otherwise fetches new price.
        """
        async with self._lock:
            now = datetime.now()
            
            # Check cache validity
            if not force_refresh and self._cached_price and self._cache_timestamp:
                age = (now - self._cache_timestamp).total_seconds()
                if age < CACHE_DURATION_SECONDS:
                    logger.debug(f"DEBUG: Using cached SOL price (age: {age:.1f}s)")
                    return self._cached_price
            
            # Fetch fresh price from APIs
            async with aiohttp.ClientSession() as session:
                # Try sources in order of preference
                sources = [
                    ("Jupiter", self._fetch_from_jupiter),
                    ("CoinGecko", self._fetch_from_coingecko),
                    ("Binance", self._fetch_from_binance),
                ]
                
                for source_name, fetch_func in sources:
                    price = await fetch_func(session)
                    if price and price > 0:
                        price_data = SolPriceData(
                            price_usd=price,
                            one_dollar_lamports=self._calculate_one_dollar_lamports(price),
                            source=source_name,
                            timestamp=now,
                            is_stale=False
                        )
                        
                        # Update cache
                        self._cached_price = price_data
                        self._cache_timestamp = now
                        
                        logger.info(f"DEBUG: SOL price updated from {source_name}: ${price:.2f}")
                        return price_data
            
            # All sources failed - use cached price if available (mark as stale)
            if self._cached_price:
                logger.warning("DEBUG: All price sources failed, using stale cached price")
                self._cached_price.is_stale = True
                return self._cached_price
            
            # Last resort - use fallback
            logger.error("DEBUG: All price sources failed, using fallback price")
            return SolPriceData(
                price_usd=FALLBACK_SOL_PRICE_USD,
                one_dollar_lamports=self._calculate_one_dollar_lamports(FALLBACK_SOL_PRICE_USD),
                source="Fallback",
                timestamp=now,
                is_stale=True
            )
    
    async def get_one_dollar_lamports(self) -> int:
        """Convenience method to get just the lamports per dollar value"""
        price_data = await self.get_sol_price()
        return price_data.one_dollar_lamports
    
    async def start_background_refresh(self, interval_seconds: int = 30):
        """
        Start background task to keep price updated.
        Debug: Continuously refreshes SOL price in the background.
        """
        logger.info(f"DEBUG: Starting SOL price background refresh (interval: {interval_seconds}s)")
        while True:
            try:
                await self.get_sol_price(force_refresh=True)
            except Exception as e:
                logger.error(f"DEBUG: Background price refresh error: {e}")
            await asyncio.sleep(interval_seconds)


# Global singleton instance
sol_price_oracle = SolPriceOracle()


async def get_current_sol_price() -> SolPriceData:
    """Helper function to get current SOL price"""
    return await sol_price_oracle.get_sol_price()


async def get_one_dollar_in_lamports() -> int:
    """Helper function to get $1 equivalent in lamports"""
    return await sol_price_oracle.get_one_dollar_lamports()
