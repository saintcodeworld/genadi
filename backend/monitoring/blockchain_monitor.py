import asyncio
import aiohttp
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import logging
from solana.rpc.async_client import AsyncClient
from solana.rpc.websocket_api import connect
from solana.rpc.types import RPCResponse
import base58
from dataclasses import dataclass

from ..api.pumpfun import PumpFunAPI, PumpFunToken
from ..api.dexscreener import DexScreenerAPI, DexScreenerToken

logger = logging.getLogger(__name__)

@dataclass
class TokenPriceUpdate:
    mint_address: str
    symbol: str
    price_usd: float
    market_cap: float
    volume_24h: float
    price_change_24h: float
    timestamp: datetime

class BlockchainMonitor:
    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url
        self.rpc_client: Optional[AsyncClient] = None
        self.ws_connection = None
        self.pumpfun_api = PumpFunAPI()
        self.dexscreener_api = DexScreenerAPI()
        self.monitored_tokens: Set[str] = set()
        self.price_callbacks: List[callable] = []
        self.is_running = False

    async def __aenter__(self):
        self.rpc_client = AsyncClient(self.rpc_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.rpc_client:
            await self.rpc_client.close()
        if self.ws_connection:
            await self.ws_connection.close()

    def add_price_callback(self, callback: callable):
        """Add callback function for price updates"""
        self.price_callbacks.append(callback)

    async def start_monitoring(self):
        """Start real-time monitoring"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting blockchain monitoring...")

        # Start multiple monitoring tasks
        tasks = [
            self._monitor_pumpfun_tokens(),
            self._monitor_dexscreener_prices(),
            self._monitor_solana_transactions()
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in monitoring: {e}")
        finally:
            self.is_running = False

    async def stop_monitoring(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info("Stopping blockchain monitoring...")

    async def add_token_monitor(self, mint_address: str):
        """Add a token to monitor"""
        self.monitored_tokens.add(mint_address)
        logger.info(f"Added token {mint_address} to monitoring")

    async def remove_token_monitor(self, mint_address: str):
        """Remove a token from monitoring"""
        self.monitored_tokens.discard(mint_address)
        logger.info(f"Removed token {mint_address} from monitoring")

    async def _monitor_pumpfun_tokens(self):
        """Monitor new tokens on pump.fun"""
        while self.is_running:
            try:
                async with self.pumpfun_api:
                    # Get featured tokens
                    featured_tokens = await self.pumpfun_api.get_featured_tokens()
                    
                    for token in featured_tokens:
                        if token.mint not in self.monitored_tokens:
                            await self.add_token_monitor(token.mint)
                            
                            # Create price update
                            price_update = TokenPriceUpdate(
                                mint_address=token.mint,
                                symbol=token.symbol,
                                price_usd=token.current_price,
                                market_cap=token.market_cap,
                                volume_24h=0,  # Not available from pump.fun API
                                price_change_24h=0,  # Not available from pump.fun API
                                timestamp=datetime.now()
                            )
                            
                            # Notify callbacks
                            await self._notify_price_update(price_update)

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error monitoring pump.fun tokens: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _monitor_dexscreener_prices(self):
        """Monitor price updates from DexScreener"""
        while self.is_running:
            try:
                async with self.dexscreener_api:
                    for mint_address in list(self.monitored_tokens):
                        # Get current price data
                        token_data = await self.dexscreener_api.get_token_price(mint_address)
                        
                        if token_data:
                            price_update = TokenPriceUpdate(
                                mint_address=mint_address,
                                symbol=token_data.baseToken.get("symbol", ""),
                                price_usd=float(token_data.priceUsd),
                                market_cap=token_data.marketCap,
                                volume_24h=float(token_data.volume.get("h24", 0)),
                                price_change_24h=float(token_data.priceChange.get("h24", 0)),
                                timestamp=datetime.now()
                            )
                            
                            # Notify callbacks
                            await self._notify_price_update(price_update)

                await asyncio.sleep(10)  # Update every 10 seconds

            except Exception as e:
                logger.error(f"Error monitoring DexScreener prices: {e}")
                await asyncio.sleep(30)

    async def _monitor_solana_transactions(self):
        """Monitor Solana blockchain for relevant transactions"""
        while self.is_running:
            try:
                if not self.rpc_client:
                    continue

                # Get recent signatures for monitored tokens
                for mint_address in list(self.monitored_tokens):
                    try:
                        signatures = await self.rpc_client.get_signatures_for_address(
                            mint_address,
                            limit=5
                        )
                        
                        # Process new transactions
                        for sig_info in signatures.value:
                            if sig_info.confirmation_status == "confirmed":
                                # Get transaction details
                                tx = await self.rpc_client.get_transaction(
                                    sig_info.signature,
                                    encoding="json",
                                    commitment="confirmed"
                                )
                                
                                # Analyze transaction for price impact
                                await self._analyze_transaction(mint_address, tx)

                    except Exception as e:
                        logger.error(f"Error monitoring transactions for {mint_address}: {e}")

                await asyncio.sleep(15)  # Check every 15 seconds

            except Exception as e:
                logger.error(f"Error monitoring Solana transactions: {e}")
                await asyncio.sleep(30)

    async def _analyze_transaction(self, mint_address: str, transaction: RPCResponse):
        """Analyze a transaction for price impact"""
        try:
            # Extract transaction details
            tx_data = transaction.value
            
            # Look for DEX interactions (Raydium, Orca, etc.)
            # This is simplified - in production you'd want to parse specific instructions
            if "meta" in tx_data and tx_data["meta"]:
                pre_balances = tx_data["meta"].get("preBalances", [])
                post_balances = tx_data["meta"].get("postBalances", [])
                
                # Calculate token movement
                # This is a placeholder for actual DEX transaction parsing
                logger.info(f"Transaction detected for {mint_address}")

        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")

    async def _notify_price_update(self, price_update: TokenPriceUpdate):
        """Notify all callbacks of price update"""
        for callback in self.price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(price_update)
                else:
                    callback(price_update)
            except Exception as e:
                logger.error(f"Error in price callback: {e}")

    async def get_token_metrics(self, mint_address: str) -> Optional[Dict]:
        """Get comprehensive metrics for a token"""
        try:
            # Get data from both APIs
            async with self.pumpfun_api, self.dexscreener_api:
                pumpfun_data = await self.pumpfun_api.get_token_info(mint_address)
                dexscreener_data = await self.dexscreener_api.get_token_price(mint_address)

                metrics = {
                    "mint_address": mint_address,
                    "pumpfun_data": pumpfun_data.__dict__ if pumpfun_data else None,
                    "dexscreener_data": dexscreener_data.__dict__ if dexscreener_data else None,
                    "last_updated": datetime.now()
                }

                return metrics

        except Exception as e:
            logger.error(f"Error getting token metrics: {e}")
            return None
