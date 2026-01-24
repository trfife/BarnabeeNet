from __future__ import annotations

from typing import Any


class RedisNotAvailableError(RuntimeError):
    pass


class RedisStreamBus:
    """Minimal async wrapper for Redis Streams.

    This file provides a small, well-typed surface for the message bus.
    It intentionally keeps behavior simple so it can be safely imported
    in tests and expanded later.
    """

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self.url = url
        self._client: Any | None = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis  # type: ignore
        except Exception as exc:  # pragma: no cover - import safety
            raise RedisNotAvailableError("redis.asyncio not available") from exc

        self._client = aioredis.from_url(self.url)

    async def close(self) -> None:
        if self._client is None:
            return
        # redis.asyncio.Redis.close returns a coroutine
        await self._client.close()
        self._client = None

    async def publish(self, stream: str, message: dict[str, str]) -> str:
        """Append a message to a Redis stream using XADD.

        Returns the entry id string returned by Redis.
        """
        if self._client is None:
            raise RedisNotAvailableError("Redis client not connected")
        # type: ignore[attr-defined]
        entry_id = await self._client.xadd(stream, message)
        return entry_id

    async def read(
        self,
        streams: list[str],
        last_ids: dict[str, str] | None = None,
        block: int = 0,
    ) -> dict[str, Any]:
        """Read from one or more streams using XREAD.

        `last_ids` should map stream -> id (e.g. '0' or '$').
        Returns the raw result from `xread`.
        """
        if self._client is None:
            raise RedisNotAvailableError("Redis client not connected")

        # Build IDs list in the order of `streams`
        ids = [last_ids.get(s, "$") if last_ids else "$" for s in streams]
        # type: ignore[attr-defined]
        result = await self._client.xread(streams, ids, block=block)
        return result


__all__ = ["RedisStreamBus", "RedisNotAvailableError"]
