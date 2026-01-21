#!/usr/bin/env python3
"""Clear all BarnabeeNet data from Redis.

Run this on the VM where Redis is running.
Usage: python3 scripts/clear_redis_data.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import redis.asyncio as redis


async def clear_all_data():
    """Clear all BarnabeeNet data from Redis."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    print("🗑️  Clearing all BarnabeeNet data from Redis...")
    print(f"Redis URL: {redis_url}")
    print("")
    
    try:
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test connection
        await r.ping()
        print("✓ Connected to Redis")
        
        # Patterns to clear
        patterns = [
            "barnabeenet:*",
            "conversation:*",
            "working:*",
            "memory:*",
            "profile:*",
            "activity:*",
            "metrics:*",
            "pipeline:*",
            "self_improvement:*",
        ]
        
        total_deleted = 0
        
        for pattern in patterns:
            keys = []
            async for key in r.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                # Delete in batches of 100
                for i in range(0, len(keys), 100):
                    batch = keys[i : i + 100]
                    deleted = await r.delete(*batch)
                    total_deleted += deleted
                print(f"  Deleted {len(keys)} keys matching {pattern}")
        
        if total_deleted > 0:
            print(f"\n✅ Successfully deleted {total_deleted} total keys")
        else:
            print("\nℹ️  No keys found to delete")
        
        await r.aclose()
        
    except redis.ConnectionError as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print("   Make sure Redis is running and REDIS_URL is correct")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(clear_all_data())
