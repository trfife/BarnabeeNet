"""Secure secrets management with encryption.

Provides encrypted storage for API keys and sensitive configuration.
Uses Fernet symmetric encryption with a master key from environment.
All secrets are persisted to Redis with AOF for durability.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Redis keys
SECRETS_KEY = "barnabeenet:secrets"
SECRETS_METADATA_KEY = "barnabeenet:secrets:metadata"


class SecretMetadata(BaseModel):
    """Metadata about a stored secret."""

    key_name: str
    provider: str
    created_at: datetime
    updated_at: datetime
    masked_value: str  # First 4 chars + "****" for display


class SecretsService:
    """Encrypted secrets storage backed by Redis.

    Security model:
    - Master key is derived from BARNABEENET_MASTER_KEY env var
    - If not set, generates a random key (development mode - warns user)
    - All secrets encrypted with Fernet (AES-128-CBC)
    - Secrets persisted to Redis with AOF for durability
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client
        self._fernet: Fernet | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize encryption with master key."""
        if self._initialized:
            return

        master_key = os.environ.get("BARNABEENET_MASTER_KEY")

        if not master_key:
            logger.warning(
                "⚠️  BARNABEENET_MASTER_KEY not set! "
                "Using random key - secrets will NOT persist across restarts. "
                "Set BARNABEENET_MASTER_KEY for production use."
            )
            # Generate random key for development
            self._fernet = Fernet(Fernet.generate_key())
        else:
            # Derive Fernet key from master key using SHA256
            # Fernet requires exactly 32 url-safe base64-encoded bytes
            key_bytes = hashlib.sha256(master_key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            self._fernet = Fernet(fernet_key)
            logger.info("✓ Secrets encryption initialized with master key")

        self._initialized = True

    def _ensure_initialized(self) -> None:
        """Ensure the service is initialized."""
        if not self._initialized or not self._fernet:
            raise RuntimeError("SecretsService not initialized. Call initialize() first.")

    def _encrypt(self, value: str) -> str:
        """Encrypt a value."""
        self._ensure_initialized()
        assert self._fernet is not None
        encrypted = self._fernet.encrypt(value.encode())
        return encrypted.decode()

    def _decrypt(self, encrypted_value: str) -> str:
        """Decrypt a value."""
        self._ensure_initialized()
        assert self._fernet is not None
        try:
            decrypted = self._fernet.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except InvalidToken:
            raise ValueError(
                "Failed to decrypt secret. This may indicate the master key has changed."
            ) from None

    def _mask_value(self, value: str) -> str:
        """Create masked version of a secret for display."""
        if len(value) <= 8:
            return "****"
        return value[:4] + "****" + value[-4:]

    async def set_secret(
        self,
        key_name: str,
        value: str,
        provider: str,
    ) -> SecretMetadata:
        """Store an encrypted secret.

        Args:
            key_name: Unique identifier for the secret (e.g., "openrouter_api_key")
            value: The secret value to encrypt and store
            provider: Provider this secret belongs to (e.g., "openrouter")

        Returns:
            Metadata about the stored secret
        """
        self._ensure_initialized()

        encrypted = self._encrypt(value)
        now = datetime.now(UTC)

        # Check if updating existing
        existing = await self.redis.hget(SECRETS_METADATA_KEY, key_name)
        if existing:
            meta_dict = json.loads(existing)
            created_at = datetime.fromisoformat(meta_dict["created_at"])
        else:
            created_at = now

        metadata = SecretMetadata(
            key_name=key_name,
            provider=provider,
            created_at=created_at,
            updated_at=now,
            masked_value=self._mask_value(value),
        )

        # Store encrypted value and metadata
        await self.redis.hset(SECRETS_KEY, key_name, encrypted)
        await self.redis.hset(
            SECRETS_METADATA_KEY,
            key_name,
            metadata.model_dump_json(),
        )

        logger.info(f"Stored secret: {key_name} for provider: {provider}")
        return metadata

    async def get_secret(self, key_name: str) -> str | None:
        """Retrieve and decrypt a secret.

        Args:
            key_name: The secret identifier

        Returns:
            Decrypted secret value, or None if not found
        """
        self._ensure_initialized()

        encrypted = await self.redis.hget(SECRETS_KEY, key_name)
        if not encrypted:
            return None

        return self._decrypt(encrypted)

    async def delete_secret(self, key_name: str) -> bool:
        """Delete a secret.

        Args:
            key_name: The secret identifier

        Returns:
            True if deleted, False if not found
        """
        result = await self.redis.hdel(SECRETS_KEY, key_name)
        await self.redis.hdel(SECRETS_METADATA_KEY, key_name)

        if result:
            logger.info(f"Deleted secret: {key_name}")
            return True
        return False

    async def list_secrets(self) -> list[SecretMetadata]:
        """List all stored secrets (metadata only, not values).

        Returns:
            List of secret metadata
        """
        metadata_dict = await self.redis.hgetall(SECRETS_METADATA_KEY)
        secrets = []

        for _key, meta_json in metadata_dict.items():
            try:
                meta_dict = json.loads(meta_json)
                # Convert datetime strings back to datetime objects
                meta_dict["created_at"] = datetime.fromisoformat(meta_dict["created_at"])
                meta_dict["updated_at"] = datetime.fromisoformat(meta_dict["updated_at"])
                secrets.append(SecretMetadata(**meta_dict))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Invalid secret metadata: {e}")

        return sorted(secrets, key=lambda s: s.provider)

    async def get_secrets_for_provider(self, provider: str) -> dict[str, str]:
        """Get all decrypted secrets for a specific provider.

        Args:
            provider: Provider name (e.g., "openrouter")

        Returns:
            Dict of key_name -> decrypted_value for the provider
        """
        self._ensure_initialized()

        secrets = await self.list_secrets()
        provider_secrets = [s for s in secrets if s.provider == provider]

        result = {}
        for meta in provider_secrets:
            value = await self.get_secret(meta.key_name)
            if value:
                result[meta.key_name] = value

        return result

    async def has_secret(self, key_name: str) -> bool:
        """Check if a secret exists.

        Args:
            key_name: The secret identifier

        Returns:
            True if secret exists
        """
        return await self.redis.hexists(SECRETS_KEY, key_name)


# Global instance
_secrets_service: SecretsService | None = None


async def get_secrets_service(redis_client: redis.Redis) -> SecretsService:
    """Get or create the secrets service singleton."""
    global _secrets_service

    if _secrets_service is None:
        _secrets_service = SecretsService(redis_client)
        await _secrets_service.initialize()

    return _secrets_service
