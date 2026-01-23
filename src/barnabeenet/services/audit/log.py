"""Audit Log Service - Immutable append-only log of all conversations.

This service provides an immutable record of all conversations for:
- Parental oversight and safety monitoring
- Compliance and accountability
- Debugging and analysis

Key features:
- Append-only: Entries cannot be modified or deleted
- "Deleted" entries are marked as deleted but remain searchable by super users
- Indexes for efficient searching by speaker, room, date, and content
- Alerts are flagged for quick identification of concerning conversations

The audit log is separate from regular memory storage - it's a complete
record even if a user says "forget this conversation".
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Redis key prefixes
AUDIT_LOG_PREFIX = "barnabeenet:audit:log:"
AUDIT_INDEX_PREFIX = "barnabeenet:audit:index:"
AUDIT_ALERTS_KEY = "barnabeenet:audit:alerts"


@dataclass
class AuditLogEntry:
    """A single entry in the audit log.

    Represents one conversation turn (user input + assistant response).
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    conversation_id: str = ""
    speaker: str | None = None
    room: str = "unknown"
    user_text: str = ""
    assistant_response: str = ""
    intent: str = "unknown"
    agent: str = "unknown"
    triggered_alert: bool = False
    alert_reason: str | None = None
    was_deleted: bool = False  # Marked as deleted but still in log
    deleted_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for Redis storage."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "conversation_id": self.conversation_id,
            "speaker": self.speaker,
            "room": self.room,
            "user_text": self.user_text,
            "assistant_response": self.assistant_response,
            "intent": self.intent,
            "agent": self.agent,
            "triggered_alert": self.triggered_alert,
            "alert_reason": self.alert_reason,
            "was_deleted": self.was_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditLogEntry":
        """Create from dict (for Redis deserialization)."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        else:
            timestamp = datetime.now(UTC)

        deleted_at = data.get("deleted_at")
        if isinstance(deleted_at, str):
            deleted_at = datetime.fromisoformat(deleted_at)

        return cls(
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            timestamp=timestamp,
            conversation_id=data.get("conversation_id", ""),
            speaker=data.get("speaker"),
            room=data.get("room", "unknown"),
            user_text=data.get("user_text", ""),
            assistant_response=data.get("assistant_response", ""),
            intent=data.get("intent", "unknown"),
            agent=data.get("agent", "unknown"),
            triggered_alert=data.get("triggered_alert", False),
            alert_reason=data.get("alert_reason"),
            was_deleted=data.get("was_deleted", False),
            deleted_at=deleted_at,
        )


class AuditLog:
    """Immutable append-only audit log for all conversations.

    This log is separate from memory storage and cannot be truly deleted -
    "delete" operations only mark entries as deleted for regular users,
    but super users (parents) can still see everything.

    Usage:
        audit_log = AuditLog(redis_client)
        await audit_log.log_conversation(entry)

        # Mark as "deleted" (still visible to super users)
        await audit_log.mark_as_deleted(entry_id)

        # Search (regular users don't see deleted entries)
        results = await audit_log.search("dinner", include_deleted=False)

        # Super user search (sees everything)
        results = await audit_log.search("dinner", include_deleted=True)
    """

    def __init__(self, redis_client: "redis.Redis | None" = None) -> None:
        """Initialize the audit log.

        Args:
            redis_client: Redis client for storage. If None, attempts to get from app_state.
        """
        self._redis_client = redis_client

    async def _get_redis(self) -> "redis.Redis | None":
        """Get Redis client, initializing from app_state if needed."""
        if self._redis_client is not None:
            return self._redis_client

        try:
            from barnabeenet.main import app_state
            if hasattr(app_state, "redis_client") and app_state.redis_client:
                self._redis_client = app_state.redis_client
                return self._redis_client
        except Exception:
            pass

        return None

    async def log_conversation(self, entry: AuditLogEntry) -> bool:
        """Log a conversation turn to the audit log.

        This is append-only - entries cannot be modified after creation.

        Args:
            entry: The audit log entry to store

        Returns:
            True if logged successfully, False otherwise
        """
        redis_client = await self._get_redis()
        if not redis_client:
            logger.warning("Cannot log to audit: Redis not available")
            return False

        try:
            # Store the entry
            entry_key = f"{AUDIT_LOG_PREFIX}{entry.entry_id}"
            entry_data = json.dumps(entry.to_dict())
            await redis_client.set(entry_key, entry_data)

            # Add to chronological index (sorted set by timestamp)
            timestamp_score = entry.timestamp.timestamp()
            await redis_client.zadd(
                f"{AUDIT_INDEX_PREFIX}chronological",
                {entry.entry_id: timestamp_score}
            )

            # Add to speaker index if known
            if entry.speaker:
                await redis_client.sadd(
                    f"{AUDIT_INDEX_PREFIX}speaker:{entry.speaker.lower()}",
                    entry.entry_id
                )

            # Add to room index
            await redis_client.sadd(
                f"{AUDIT_INDEX_PREFIX}room:{entry.room.lower()}",
                entry.entry_id
            )

            # Add to conversation index
            if entry.conversation_id:
                await redis_client.sadd(
                    f"{AUDIT_INDEX_PREFIX}conversation:{entry.conversation_id}",
                    entry.entry_id
                )

            # Add to alerts set if triggered
            if entry.triggered_alert:
                await redis_client.zadd(
                    AUDIT_ALERTS_KEY,
                    {entry.entry_id: timestamp_score}
                )

            # Index by date for daily browsing
            date_str = entry.timestamp.strftime("%Y-%m-%d")
            await redis_client.sadd(
                f"{AUDIT_INDEX_PREFIX}date:{date_str}",
                entry.entry_id
            )

            logger.debug(f"Logged audit entry: {entry.entry_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")
            return False

    async def mark_as_deleted(self, entry_id: str) -> bool:
        """Mark an entry as deleted (but don't actually delete it).

        The entry remains in the log but is hidden from regular searches.
        Super users can still see it.

        Args:
            entry_id: The entry ID to mark as deleted

        Returns:
            True if marked successfully, False otherwise
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return False

        try:
            entry_key = f"{AUDIT_LOG_PREFIX}{entry_id}"
            entry_data = await redis_client.get(entry_key)

            if not entry_data:
                logger.warning(f"Audit entry not found: {entry_id}")
                return False

            # Load, modify, and save
            entry_dict = json.loads(entry_data)
            entry_dict["was_deleted"] = True
            entry_dict["deleted_at"] = datetime.now(UTC).isoformat()

            await redis_client.set(entry_key, json.dumps(entry_dict))
            logger.info(f"Marked audit entry as deleted: {entry_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to mark entry as deleted: {e}")
            return False

    async def get_entry(self, entry_id: str) -> AuditLogEntry | None:
        """Get a specific audit log entry by ID.

        Args:
            entry_id: The entry ID to retrieve

        Returns:
            The audit log entry, or None if not found
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return None

        try:
            entry_key = f"{AUDIT_LOG_PREFIX}{entry_id}"
            entry_data = await redis_client.get(entry_key)

            if entry_data:
                return AuditLogEntry.from_dict(json.loads(entry_data))

        except Exception as e:
            logger.error(f"Failed to get audit entry: {e}")

        return None

    async def search(
        self,
        query: str | None = None,
        speaker: str | None = None,
        room: str | None = None,
        date: str | None = None,
        conversation_id: str | None = None,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """Search the audit log.

        Args:
            query: Text to search for in user_text/assistant_response
            speaker: Filter by speaker
            room: Filter by room
            date: Filter by date (YYYY-MM-DD format)
            conversation_id: Filter by conversation
            include_deleted: If True, include "deleted" entries (super user mode)
            limit: Maximum number of results

        Returns:
            List of matching audit log entries, newest first
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return []

        try:
            # Get candidate entry IDs based on filters
            entry_ids: set[str] = set()

            if speaker:
                ids = await redis_client.smembers(
                    f"{AUDIT_INDEX_PREFIX}speaker:{speaker.lower()}"
                )
                entry_ids = {id.decode() if isinstance(id, bytes) else id for id in ids}
            elif room:
                ids = await redis_client.smembers(
                    f"{AUDIT_INDEX_PREFIX}room:{room.lower()}"
                )
                entry_ids = {id.decode() if isinstance(id, bytes) else id for id in ids}
            elif date:
                ids = await redis_client.smembers(
                    f"{AUDIT_INDEX_PREFIX}date:{date}"
                )
                entry_ids = {id.decode() if isinstance(id, bytes) else id for id in ids}
            elif conversation_id:
                ids = await redis_client.smembers(
                    f"{AUDIT_INDEX_PREFIX}conversation:{conversation_id}"
                )
                entry_ids = {id.decode() if isinstance(id, bytes) else id for id in ids}
            else:
                # Get recent entries from chronological index
                ids = await redis_client.zrevrange(
                    f"{AUDIT_INDEX_PREFIX}chronological",
                    0,
                    limit * 2  # Get more to account for filtering
                )
                entry_ids = {id.decode() if isinstance(id, bytes) else id for id in ids}

            # Load entries and filter
            results: list[AuditLogEntry] = []
            for entry_id in entry_ids:
                entry = await self.get_entry(entry_id)
                if not entry:
                    continue

                # Skip deleted entries unless super user mode
                if entry.was_deleted and not include_deleted:
                    continue

                # Text search filter
                if query:
                    query_lower = query.lower()
                    if (
                        query_lower not in entry.user_text.lower()
                        and query_lower not in entry.assistant_response.lower()
                    ):
                        continue

                results.append(entry)

                if len(results) >= limit:
                    break

            # Sort by timestamp descending
            results.sort(key=lambda e: e.timestamp, reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to search audit log: {e}")
            return []

    async def get_alerts(
        self,
        limit: int = 50,
        include_deleted: bool = True,
    ) -> list[AuditLogEntry]:
        """Get entries that triggered parental alerts.

        Args:
            limit: Maximum number of results
            include_deleted: Include deleted entries (default True for alerts)

        Returns:
            List of alert entries, newest first
        """
        redis_client = await self._get_redis()
        if not redis_client:
            return []

        try:
            # Get alert entry IDs, newest first
            entry_ids = await redis_client.zrevrange(AUDIT_ALERTS_KEY, 0, limit - 1)

            results: list[AuditLogEntry] = []
            for entry_id in entry_ids:
                if isinstance(entry_id, bytes):
                    entry_id = entry_id.decode()
                entry = await self.get_entry(entry_id)
                if entry:
                    if entry.was_deleted and not include_deleted:
                        continue
                    results.append(entry)

            return results

        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []

    async def get_conversation_history(
        self,
        conversation_id: str,
        include_deleted: bool = False,
    ) -> list[AuditLogEntry]:
        """Get all entries for a specific conversation.

        Args:
            conversation_id: The conversation to retrieve
            include_deleted: Include deleted entries

        Returns:
            List of entries in chronological order
        """
        return await self.search(
            conversation_id=conversation_id,
            include_deleted=include_deleted,
            limit=1000,  # Conversations shouldn't be longer than this
        )


# Global audit log instance
_audit_log: AuditLog | None = None


def get_audit_log() -> AuditLog:
    """Get or create the global audit log instance."""
    global _audit_log
    if _audit_log is None:
        _audit_log = AuditLog()
    return _audit_log
