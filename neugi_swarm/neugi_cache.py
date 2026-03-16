#!/usr/bin/env python3
"""
🤖 NEUGI CACHE LAYER
======================

Redis-style in-memory cache:
- Key-value store
- TTL support
- Pub/Sub
- Rate limiting

Version: 1.0
Date: March 16, 2026
"""

import os
import time
import json
import threading
from typing import Dict, List, Optional, Any
from collections import OrderedDict

NEUGI_DIR = os.path.expanduser("~/neugi")
CACHE_DIR = os.path.join(NEUGI_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class CacheEntry:
    """Cache entry with TTL"""

    def __init__(self, value: Any, ttl: int = None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_access = self.created_at

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def access(self):
        self.access_count += 1
        self.last_access = time.time()


class InMemoryCache:
    """In-memory cache with LRU eviction"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]

            if entry.is_expired():
                del self.cache[key]
                return None

            entry.access()
            self.cache.move_to_end(key)
            return entry.value

    def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache"""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
            elif len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)

            self.cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        with self._lock:
            if key not in self.cache:
                return False
            if self.cache[key].is_expired():
                del self.cache[key]
                return False
            return True

    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for key"""
        with self._lock:
            if key in self.cache:
                self.cache[key].ttl = ttl
                return True
            return False

    def ttl(self, key: str) -> int:
        """Get remaining TTL"""
        with self._lock:
            if key not in self.cache:
                return -2

            entry = self.cache[key]
            if entry.ttl is None:
                return -1

            remaining = entry.ttl - (time.time() - entry.created_at)
            return int(remaining)

    def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern"""
        with self._lock:
            import fnmatch

            return [k for k in self.cache.keys() if fnmatch.fnmatch(k, pattern)]

    def flush(self):
        """Clear all cache"""
        with self._lock:
            self.cache.clear()

    def stats(self) -> Dict:
        """Get cache statistics"""
        with self._lock:
            total_accesses = sum(e.access_count for e in self.cache.values())
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "total_accesses": total_accesses,
                "keys": list(self.cache.keys())[:10],
            }


class RateLimiter:
    """Rate limiter"""

    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
        self._lock = threading.RLock()

    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """Check if request is allowed"""
        with self._lock:
            now = time.time()

            if key not in self.requests:
                self.requests[key] = []

            self.requests[key] = [t for t in self.requests[key] if now - t < window]

            if len(self.requests[key]) < limit:
                self.requests[key].append(now)
                return True

            return False

    def reset(self, key: str):
        """Reset rate limit for key"""
        with self._lock:
            if key in self.requests:
                del self.requests[key]


class PubSub:
    """Pub/Sub messaging"""

    def __init__(self):
        self.channels: Dict[str, List[callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, channel: str, callback: callable):
        """Subscribe to channel"""
        with self._lock:
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels[channel].append(callback)

    def unsubscribe(self, channel: str, callback: callable):
        """Unsubscribe from channel"""
        with self._lock:
            if channel in self.channels and callback in self.channels[channel]:
                self.channels[channel].remove(callback)

    def publish(self, channel: str, message: Any):
        """Publish to channel"""
        with self._lock:
            if channel in self.channels:
                for callback in self.channels[channel]:
                    try:
                        callback(message)
                    except:
                        pass

    def channels_list(self) -> List[str]:
        """List channels"""
        with self._lock:
            return list(self.channels.keys())


class DistributedCache:
    """Persistent cache with disk backup"""

    def __init__(self, max_size: int = 1000):
        self.memory = InMemoryCache(max_size)
        self.persist_file = os.path.join(CACHE_DIR, "cache_data.json")
        self._load_from_disk()

    def _load_from_disk(self):
        """Load cache from disk"""
        if os.path.exists(self.persist_file):
            try:
                with open(self.persist_file) as f:
                    data = json.load(f)
                    for key, entry in data.items():
                        self.memory.set(key, entry["value"], entry.get("ttl"))
            except:
                pass

    def _save_to_disk(self):
        """Save cache to disk"""
        data = {}
        for key in self.memory.cache.keys():
            entry = self.memory.cache[key]
            data[key] = {"value": entry.value, "ttl": entry.ttl}

        with open(self.persist_file, "w") as f:
            json.dump(data, f)


class CacheManager:
    """Cache manager with multiple backends"""

    def __init__(self):
        self.cache = InMemoryCache()
        self.rate_limiter = RateLimiter()
        self.pubsub = PubSub()
        self.persistent = DistributedCache()

    def get(self, key: str, persistent: bool = False) -> Optional[Any]:
        """Get value"""
        if persistent:
            return self.persistent.get(key)
        return self.cache.get(key)

    def set(self, key: str, value: Any, ttl: int = None, persistent: bool = False):
        """Set value"""
        if persistent:
            self.persistent.set(key, value, ttl)
            self.persistent._save_to_disk()
        else:
            self.cache.set(key, value, ttl)

    def delete(self, key: str):
        """Delete key"""
        self.cache.delete(key)
        self.persistent.cache.delete(key)

    def rate_limit(self, key: str, limit: int = 100, window: int = 60) -> bool:
        """Check rate limit"""
        return self.rate_limiter.is_allowed(key, limit, window)

    def subscribe(self, channel: str, callback: callable):
        """Subscribe to channel"""
        self.pubsub.subscribe(channel, callback)

    def publish(self, channel: str, message: Any):
        """Publish message"""
        self.pubsub.publish(channel, message)


cache_manager = CacheManager()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Cache Layer")
    parser.add_argument("--get", type=str, help="Get value")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set value")
    parser.add_argument("--delete", type=str, help="Delete key")
    parser.add_argument(
        "--rate-limit",
        type=int,
        nargs=3,
        metavar=("KEY", "LIMIT", "WINDOW"),
        help="Check rate limit",
    )
    parser.add_argument("--stats", action="store_true", help="Show stats")
    parser.add_argument("--flush", action="store_true", help="Flush cache")

    args = parser.parse_args()

    cache = cache_manager.cache

    if args.get:
        value = cache.get(args.get)
        if value is not None:
            print(f"{args.get}: {value}")
        else:
            print("Key not found or expired")

    elif args.set:
        key, value = args.set
        cache.set(key, value)
        print(f"Set: {key} = {value}")

    elif args.delete:
        cache.delete(args.delete)
        print(f"Deleted: {args.delete}")

    elif args.rate_limit:
        key, limit, window = args.rate_limit
        allowed = cache_manager.rate_limit(key, int(limit), int(window))
        print(f"Allowed: {allowed}")

    elif args.stats:
        stats = cache.stats()
        print("\n📊 Cache Stats:")
        print(f"   Size: {stats['size']}/{stats['max_size']}")
        print(f"   Total Accesses: {stats['total_accesses']}")
        print(f"   Keys: {stats['keys']}")

    elif args.flush:
        cache.flush()
        print("Cache flushed")

    else:
        print("NEUGI Cache Layer")
        print(
            "Usage: python -m neugi_cache [--get KEY] [--set KEY VALUE] [--delete KEY] [--rate-limit KEY LIMIT WINDOW] [--stats] [--flush]"
        )


if __name__ == "__main__":
    main()
