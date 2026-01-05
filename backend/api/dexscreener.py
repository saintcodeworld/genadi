import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DexScreenerToken:
    chainId: str
    dexId: str
    url: str
    pairAddress: str
    baseToken: Dict[str, Any]
    quoteToken: Dict[str, Any]
    priceNative: str
    priceUsd: str
    txns: Dict[str, Any]
    volume: Dict[str, Any]
    priceChange: Dict[str, Any]
    liquidity: Dict[str, Any]
    fdv: float
    marketCap: float
    pairCreatedAt: datetime

class DexScreenerAPI:
    def __init__(self):
        self.base_url = "https://api.dexscreener.com/latest"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_token_price(self, token_address: str) -> Optional[DexScreenerToken]:
        """Get current price and market data for a token"""
        if not self.session:
            raise RuntimeError("DexScreenerAPI must be used as async context manager")

        url = f"{self.base_url}/dex/tokens/{token_address}"
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not data.get("pairs"):
                    return None
                
                # Return the first pair (most liquid)
                pair_data = data["pairs"][0]
                return self._parse_pair_data(pair_data)
                
        except Exception as e:
            logger.error(f"Error fetching token price for {token_address}: {e}")
            return None

    async def get_pair_info(self, pair_address: str) -> Optional[DexScreenerToken]:
        """Get detailed information about a trading pair"""
        if not self.session:
            raise RuntimeError("DexScreenerAPI must be used as async context manager")

        url = f"{self.base_url}/dex/pairs/{pair_address}"
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not data.get("pairs"):
                    return None
                
                pair_data = data["pairs"][0]
                return self._parse_pair_data(pair_data)
                
        except Exception as e:
            logger.error(f"Error fetching pair info for {pair_address}: {e}")
            return None

    async def search_pairs(self, query: str) -> List[DexScreenerToken]:
        """Search for trading pairs by token name or symbol"""
        if not self.session:
            raise RuntimeError("DexScreenerAPI must be used as async context manager")

        url = f"{self.base_url}/dex/search"
        params = {"q": query}
        
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                tokens = []
                for pair_data in data.get("pairs", []):
                    token = self._parse_pair_data(pair_data)
                    if token:
                        tokens.append(token)
                
                return tokens
        except Exception as e:
            logger.error(f"Error searching pairs: {e}")
            return []

    async def get_solana_trending(self) -> List[DexScreenerToken]:
        """Get trending tokens on Solana"""
        if not self.session:
            raise RuntimeError("DexScreenerAPI must be used as async context manager")

        url = f"{self.base_url}/dex/trending/solana"
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                
                tokens = []
                for pair_data in data.get("pairs", []):
                    token = self._parse_pair_data(pair_data)
                    if token:
                        tokens.append(token)
                
                return tokens
        except Exception as e:
            logger.error(f"Error fetching Solana trending tokens: {e}")
            return []

    def _parse_pair_data(self, pair_data: Dict[str, Any]) -> Optional[DexScreenerToken]:
        """Parse raw pair data from DexScreener API"""
        try:
            # Parse timestamps
            created_str = pair_data.get("pairCreatedAt")
            if created_str:
                pair_created_at = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            else:
                pair_created_at = datetime.now()

            return DexScreenerToken(
                chainId=pair_data.get("chainId", ""),
                dexId=pair_data.get("dexId", ""),
                url=pair_data.get("url", ""),
                pairAddress=pair_data.get("pairAddress", ""),
                baseToken=pair_data.get("baseToken", {}),
                quoteToken=pair_data.get("quoteToken", {}),
                priceNative=pair_data.get("priceNative", "0"),
                priceUsd=pair_data.get("priceUsd", "0"),
                txns=pair_data.get("txns", {}),
                volume=pair_data.get("volume", {}),
                priceChange=pair_data.get("priceChange", {}),
                liquidity=pair_data.get("liquidity", {}),
                fdv=float(pair_data.get("fdv", 0)),
                marketCap=float(pair_data.get("marketCap", 0)),
                pairCreatedAt=pair_created_at
            )
        except Exception as e:
            logger.error(f"Error parsing pair data: {e}")
            return None

    async def get_historical_prices(self, pair_address: str, timeframe: str = "1h") -> List[Dict[str, Any]]:
        """Get historical price data for a pair"""
        if not self.session:
            raise RuntimeError("DexScreenerAPI must be used as async context manager")

        url = f"{self.base_url}/dex/history"
        params = {
            "pairId": pair_address,
            "interval": timeframe
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("prices", [])
        except Exception as e:
            logger.error(f"Error fetching historical prices: {e}")
            return []
