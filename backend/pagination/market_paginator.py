from fastapi import Query, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import math
from datetime import datetime

from ..main import Market, RealMarket
from ..cache.redis_cache import cache_manager

class PaginationParams(BaseModel):
    page: int = Field(ge=1, default=1)
    size: int = Field(ge=1, le=100, default=20)
    sort_by: Optional[str] = Field(default="created_at")
    sort_order: Optional[str] = Field(default="desc", regex="^(asc|desc)$")
    status: Optional[str] = Field(default=None, regex="^(active|resolved|expired)$")
    search: Optional[str] = Field(default=None, max_length=100)

class PaginatedResponse(BaseModel):
    items: List[Dict[str, Any]]
    total_count: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int] = None
    prev_page: Optional[int] = None

class MarketPaginator:
    def __init__(self):
        self.default_size = 20
        self.max_size = 100

    def validate_pagination_params(self, page: int, size: int, sort_by: str, sort_order: str) -> tuple:
        """Validate and normalize pagination parameters"""
        # Validate page
        if page < 1:
            page = 1
        
        # Validate size
        if size < 1:
            size = self.default_size
        elif size > self.max_size:
            size = self.max_size
        
        # Validate sort fields
        valid_sort_fields = {
            "created_at", "current_market_cap", "yes_price", "no_price", 
            "total_volume", "expiry_time", "token_symbol"
        }
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"
        
        # Validate sort order
        if sort_order not in ["asc", "desc"]:
            sort_order = "desc"
        
        return page, size, sort_by, sort_order

    def generate_cache_key(self, params: PaginationParams, market_type: str = "all") -> str:
        """Generate cache key for paginated results"""
        key_parts = [
            "paginated_markets",
            market_type,
            str(params.page),
            str(params.size),
            params.sort_by or "created_at",
            params.sort_order or "desc",
            params.status or "all",
            params.search or ""
        ]
        return ":".join(key_parts)

    async def get_paginated_markets(
        self, 
        markets: List[Union[Market, RealMarket]], 
        params: PaginationParams,
        market_type: str = "all"
    ) -> PaginatedResponse:
        """Get paginated markets with caching"""
        
        # Validate parameters
        page, size, sort_by, sort_order = self.validate_pagination_params(
            params.page, params.size, params.sort_by, params.sort_order
        )
        
        # Check cache first
        cache_key = self.generate_cache_key(params, market_type)
        cached_result = await cache_manager.get_paginated_markets(cache_key)
        
        if cached_result:
            return PaginatedResponse(**cached_result)
        
        # Filter markets
        filtered_markets = self.filter_markets(markets, params.status, params.search)
        
        # Sort markets
        sorted_markets = self.sort_markets(filtered_markets, sort_by, sort_order)
        
        # Calculate pagination
        total_count = len(sorted_markets)
        total_pages = math.ceil(total_count / size) if total_count > 0 else 1
        
        # Adjust page if it's beyond total pages
        if page > total_pages and total_pages > 0:
            page = total_pages
        
        # Get slice for current page
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        page_items = sorted_markets[start_idx:end_idx]
        
        # Convert to dict for JSON serialization
        items = [market.dict() for market in page_items]
        
        # Build response
        response = PaginatedResponse(
            items=items,
            total_count=total_count,
            page=page,
            size=size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
            next_page=page + 1 if page < total_pages else None,
            prev_page=page - 1 if page > 1 else None
        )
        
        # Cache the result
        await cache_manager.cache_paginated_markets(
            cache_key, 
            items, 
            total_count, 
            ttl=60  # 1 minute cache
        )
        
        return response

    def filter_markets(
        self, 
        markets: List[Union[Market, RealMarket]], 
        status: Optional[str], 
        search: Optional[str]
    ) -> List[Union[Market, RealMarket]]:
        """Filter markets by status and search term"""
        filtered = markets
        
        # Filter by status
        if status:
            filtered = [m for m in filtered if m.status == status]
        
        # Filter by search term
        if search:
            search_lower = search.lower()
            filtered = [
                m for m in filtered 
                if search_lower in m.token_symbol.lower() 
                or search_lower in m.question.lower()
            ]
        
        return filtered

    def sort_markets(
        self, 
        markets: List[Union[Market, RealMarket]], 
        sort_by: str, 
        sort_order: str
    ) -> List[Union[Market, RealMarket]]:
        """Sort markets by specified field"""
        reverse = sort_order == "desc"
        
        try:
            if sort_by == "created_at":
                # Handle both Market and RealMarket
                return sorted(
                    markets, 
                    key=lambda m: getattr(m, 'created_at', datetime.now()), 
                    reverse=reverse
                )
            elif sort_by == "current_market_cap":
                return sorted(markets, key=lambda m: m.current_market_cap, reverse=reverse)
            elif sort_by == "yes_price":
                return sorted(markets, key=lambda m: m.yes_price, reverse=reverse)
            elif sort_by == "no_price":
                return sorted(markets, key=lambda m: m.no_price, reverse=reverse)
            elif sort_by == "total_volume":
                return sorted(markets, key=lambda m: m.total_volume, reverse=reverse)
            elif sort_by == "expiry_time":
                return sorted(markets, key=lambda m: m.expiry_time, reverse=reverse)
            elif sort_by == "token_symbol":
                return sorted(markets, key=lambda m: m.token_symbol.lower(), reverse=reverse)
            else:
                # Default sort by created_at
                return sorted(
                    markets, 
                    key=lambda m: getattr(m, 'created_at', datetime.now()), 
                    reverse=reverse
                )
        except Exception as e:
            # If sorting fails, return original order
            return markets

    async def invalidate_cache(self, market_type: str = "all"):
        """Invalidate pagination cache for a specific market type"""
        # This is a simplified cache invalidation
        # In production, you might want to track all cache keys
        await cache_manager.invalidate_all_markets()

# Singleton instance
market_paginator = MarketPaginator()
