#!/usr/bin/env python3
"""
Smart Cache System for ABCDBET Bot
"""

import time
import asyncio
from collections import OrderedDict
from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class SmartCache:
    """Smart cache with TTL and LRU eviction"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict = OrderedDict()
        self.expiry_times: Dict[str, float] = {}
        self._cleanup_running = False
        
    async def start_tasks(self):
        """Start background cleanup tasks"""
        if not self._cleanup_running:
            self._cleanup_running = True
            asyncio.create_task(self._cleanup_task())
    
    async def _cleanup_task(self):
        """Background task to clean up expired items"""
        while self._cleanup_running:
            try:
                current_time = time.time()
                expired_keys = []
                
                # Find expired keys
                for key, expiry_time in self.expiry_times.items():
                    if current_time > expiry_time:
                        expired_keys.append(key)
                
                # Remove expired keys
                for key in expired_keys:
                    self.delete(key)
                
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired cache items")
                
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                logger.error(f"Error in cache cleanup task: {e}")
                await asyncio.sleep(60)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cache item with TTL"""
        ttl = ttl or self.default_ttl
        
        # Remove if key already exists
        if key in self.cache:
            self.delete(key)
        
        # Check if cache is full
        if len(self.cache) >= self.max_size:
            # Remove oldest item (LRU)
            oldest_key = next(iter(self.cache))
            self.delete(oldest_key)
        
        # Add new item
        self.cache[key] = value
        self.expiry_times[key] = time.time() + ttl
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache item if not expired"""
        if key not in self.cache:
            return None
        
        # Check if expired
        if time.time() > self.expiry_times[key]:
            self.delete(key)
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def delete(self, key: str) -> bool:
        """Delete cache item"""
        if key in self.cache:
            del self.cache[key]
            del self.expiry_times[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache items"""
        self.cache.clear()
        self.expiry_times.clear()
    
    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)
    
    def keys(self) -> list:
        """Get all cache keys"""
        return list(self.cache.keys())
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        current_time = time.time()
        expired_count = sum(1 for expiry in self.expiry_times.values() if current_time > expiry)
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'expired_items': expired_count,
            'utilization': len(self.cache) / self.max_size * 100
        }


class FunctionCache:
    """Decorator for caching function results"""
    
    def __init__(self, cache: SmartCache, ttl: Optional[int] = None):
        self.cache = cache
        self.ttl = ttl
    
    def __call__(self, func: Callable):
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = self.cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            self.cache.set(key, result, self.ttl)
            return result
        
        return wrapper


class CacheManager:
    """Manager for multiple cache instances"""
    
    def __init__(self):
        self.caches: Dict[str, SmartCache] = {}
        self._tasks_started = False
    
    def create_cache(self, name: str, max_size: int = 1000, default_ttl: int = 300) -> SmartCache:
        """Create a new cache instance"""
        if name in self.caches:
            raise ValueError(f"Cache '{name}' already exists")
        
        cache = SmartCache(max_size, default_ttl)
        self.caches[name] = cache
        return cache
    
    def get_cache(self, name: str) -> Optional[SmartCache]:
        """Get existing cache instance"""
        return self.caches.get(name)
    
    def delete_cache(self, name: str) -> bool:
        """Delete cache instance"""
        if name in self.caches:
            cache = self.caches[name]
            cache._cleanup_running = False
            cache.clear()
            del self.caches[name]
            return True
        return False
    
    async def start_all_tasks(self):
        """Start background tasks for all caches"""
        if not self._tasks_started:
            for cache in self.caches.values():
                await cache.start_tasks()
            self._tasks_started = True
    
    def get_all_stats(self) -> Dict:
        """Get statistics for all caches"""
        return {
            name: cache.get_stats() for name, cache in self.caches.items()
        }


# Khởi tạo instances
cache_manager = CacheManager()
default_cache = cache_manager.create_cache('default', max_size=1000, default_ttl=300)
user_cache = cache_manager.create_cache('users', max_size=500, default_ttl=1800)
session_cache = cache_manager.create_cache('sessions', max_size=200, default_ttl=3600)
