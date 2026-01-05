import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PumpFunToken:
    name: str
    symbol: str
    mint: str
    bonding_curve_key: str
    associated_bonding_curve: str
    token_uri: str
    image_uri: str
    metadata: Dict[str, Any]
    created: datetime
    market_cap: float
    current_price: float
    virtual_token_reserves: float
    virtual_sol_reserves: float

class PumpFunAPI:
    def __init__(self):
        self.base_url = "https://frontend-api.pump.fun"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_recent_tokens(self, limit: int = 50) -> List[PumpFunToken]:
        """Get recently created tokens from pump.fun"""
        if not self.session:
            raise RuntimeError("PumpFunAPI must be used as async context manager")

        url = f"{self.base_url}/coins/recent"
        params = {"limit": limit}
        
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                tokens = []
                for token_data in data:
                    token = self._parse_token_data(token_data)
                    if token:
                        tokens.append(token)
                
                return tokens
        except Exception as e:
            logger.error(f"Error fetching recent tokens: {e}")
            return []

    async def get_token_info(self, mint_address: str) -> Optional[PumpFunToken]:
        """Get detailed information about a specific token"""
        if not self.session:
            raise RuntimeError("PumpFunAPI must be used as async context manager")

        url = f"{self.base_url}/coin/{mint_address}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return self._parse_token_data(data)
        except Exception as e:
            logger.error(f"Error fetching token info for {mint_address}: {e}")
            return None

    async def get_featured_tokens(self) -> List[PumpFunToken]:
        """Get featured/trending tokens from pump.fun"""
        if not self.session:
            raise RuntimeError("PumpFunAPI must be used as async context manager")

        url = f"{self.base_url}/coins/featured"
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                
                tokens = []
                for token_data in data:
                    token = self._parse_token_data(token_data)
                    if token:
                        tokens.append(token)
                
                return tokens
        except Exception as e:
            logger.error(f"Error fetching featured tokens: {e}")
            return []

    def _parse_token_data(self, token_data: Dict[str, Any]) -> Optional[PumpFunToken]:
        """Parse raw token data from pump.fun API"""
        try:
            # Extract market cap and price data
            market_cap = float(token_data.get("usd_market_cap", 0))
            current_price = float(token_data.get("price", 0))
            
            # Parse timestamps
            created_str = token_data.get("created")
            if created_str:
                created = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            else:
                created = datetime.now()

            return PumpFunToken(
                name=token_data.get("name", ""),
                symbol=token_data.get("symbol", ""),
                mint=token_data.get("mint", ""),
                bonding_curve_key=token_data.get("bonding_curve_key", ""),
                associated_bonding_curve=token_data.get("associated_bonding_curve", ""),
                token_uri=token_data.get("token_uri", ""),
                image_uri=token_data.get("image_uri", ""),
                metadata=token_data.get("metadata", {}),
                created=created,
                market_cap=market_cap,
                current_price=current_price,
                virtual_token_reserves=float(token_data.get("virtual_token_reserves", 0)),
                virtual_sol_reserves=float(token_data.get("virtual_sol_reserves", 0))
            )
        except Exception as e:
            logger.error(f"Error parsing token data: {e}")
            return None

    async def search_tokens(self, query: str) -> List[PumpFunToken]:
        """Search for tokens by name or symbol"""
        if not self.session:
            raise RuntimeError("PumpFunAPI must be used as async context manager")

        url = f"{self.base_url}/search"
        params = {"q": query}
        
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                tokens = []
                for token_data in data:
                    token = self._parse_token_data(token_data)
                    if token:
                        tokens.append(token)
                
                return tokens
        except Exception as e:
            logger.error(f"Error searching tokens: {e}")
            return []
