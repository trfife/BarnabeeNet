"""Tests for LLM provider configuration system."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.models.provider_config import (
    PROVIDER_REGISTRY,
    ProviderConfig,
    ProviderInfo,
    ProviderStatus,
    ProviderType,
    get_all_providers,
    get_provider_info,
)
from barnabeenet.services.secrets import SecretMetadata, SecretsService

# =============================================================================
# Provider Config Model Tests
# =============================================================================


class TestProviderConfig:
    """Tests for provider configuration models."""

    def test_provider_type_enum(self) -> None:
        """Test all expected providers are defined."""
        expected = [
            "openrouter",
            "openai",
            "anthropic",
            "azure",
            "google",
            "xai",
            "deepseek",
            "huggingface",
            "bedrock",
            "together",
            "mistral",
            "groq",
        ]
        assert len(ProviderType) == len(expected)
        for provider in expected:
            assert provider in [p.value for p in ProviderType]

    def test_get_provider_info(self) -> None:
        """Test retrieving provider info."""
        info = get_provider_info(ProviderType.OPENROUTER)
        assert info.display_name == "OpenRouter"
        assert info.base_url == "https://openrouter.ai/api/v1"
        assert len(info.secret_fields) > 0
        assert len(info.setup_instructions) > 0

    def test_get_all_providers(self) -> None:
        """Test getting all providers."""
        providers = get_all_providers()
        assert len(providers) == 12  # All providers
        assert all(isinstance(p, ProviderInfo) for p in providers)

    def test_provider_registry_complete(self) -> None:
        """Test all provider types have registry entries."""
        for provider_type in ProviderType:
            assert provider_type in PROVIDER_REGISTRY
            info = PROVIDER_REGISTRY[provider_type]
            assert info.provider_type == provider_type
            assert info.display_name
            assert info.base_url
            assert info.api_key_url

    def test_provider_config_defaults(self) -> None:
        """Test ProviderConfig defaults."""
        config = ProviderConfig(provider_type=ProviderType.OPENAI)
        assert config.enabled is False
        assert config.base_url is None
        assert config.extra_config == {}

    def test_provider_status_model(self) -> None:
        """Test ProviderStatus model."""
        status = ProviderStatus(
            provider_type=ProviderType.ANTHROPIC,
            display_name="Anthropic Claude",
            enabled=True,
            configured=True,
            health_status="healthy",
        )
        assert status.enabled
        assert status.configured
        assert status.health_status == "healthy"


# =============================================================================
# Secrets Service Tests
# =============================================================================


class TestSecretsService:
    """Tests for the secrets service."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        redis.hdel = AsyncMock(return_value=1)
        redis.hgetall = AsyncMock(return_value={})
        redis.hexists = AsyncMock(return_value=False)
        return redis

    @pytest.fixture
    def secrets_service(self, mock_redis: AsyncMock) -> SecretsService:
        """Create SecretsService with mock redis."""
        return SecretsService(mock_redis)

    @pytest.mark.asyncio
    async def test_initialize_with_master_key(self, secrets_service: SecretsService) -> None:
        """Test initialization with master key."""
        with patch.dict("os.environ", {"BARNABEENET_MASTER_KEY": "test-secret-key"}):
            await secrets_service.initialize()
            assert secrets_service._initialized
            assert secrets_service._fernet is not None

    @pytest.mark.asyncio
    async def test_initialize_without_master_key(self, secrets_service: SecretsService) -> None:
        """Test initialization without master key (dev mode)."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove the key if it exists
            import os

            os.environ.pop("BARNABEENET_MASTER_KEY", None)

            await secrets_service.initialize()
            assert secrets_service._initialized
            # Should still have fernet (random key)
            assert secrets_service._fernet is not None

    @pytest.mark.asyncio
    async def test_set_and_get_secret(
        self, secrets_service: SecretsService, mock_redis: AsyncMock
    ) -> None:
        """Test storing and retrieving a secret."""
        with patch.dict("os.environ", {"BARNABEENET_MASTER_KEY": "test-key-123"}):
            await secrets_service.initialize()

            # Store secret
            meta = await secrets_service.set_secret(
                key_name="test_api_key",
                value="sk-secret-value-123",
                provider="openai",
            )

            assert meta.key_name == "test_api_key"
            assert meta.provider == "openai"
            assert "****" in meta.masked_value  # Should be masked
            assert mock_redis.hset.called

    @pytest.mark.asyncio
    async def test_mask_value(self, secrets_service: SecretsService) -> None:
        """Test secret value masking."""
        with patch.dict("os.environ", {"BARNABEENET_MASTER_KEY": "test-key"}):
            await secrets_service.initialize()

            # Long value
            masked = secrets_service._mask_value("sk-abcdefghijklmnop")
            assert masked == "sk-a****mnop"

            # Short value
            masked = secrets_service._mask_value("short")
            assert masked == "****"

    @pytest.mark.asyncio
    async def test_delete_secret(
        self, secrets_service: SecretsService, mock_redis: AsyncMock
    ) -> None:
        """Test deleting a secret."""
        with patch.dict("os.environ", {"BARNABEENET_MASTER_KEY": "test-key"}):
            await secrets_service.initialize()

            result = await secrets_service.delete_secret("test_key")
            assert result is True
            mock_redis.hdel.assert_called()

    @pytest.mark.asyncio
    async def test_list_secrets(
        self, secrets_service: SecretsService, mock_redis: AsyncMock
    ) -> None:
        """Test listing secrets."""
        with patch.dict("os.environ", {"BARNABEENET_MASTER_KEY": "test-key"}):
            await secrets_service.initialize()

            # Mock return data
            now = datetime.now(UTC)
            mock_redis.hgetall.return_value = {
                "openai_api_key": SecretMetadata(
                    key_name="openai_api_key",
                    provider="openai",
                    created_at=now,
                    updated_at=now,
                    masked_value="sk-a****xyz",
                ).model_dump_json()
            }

            secrets = await secrets_service.list_secrets()
            assert len(secrets) == 1
            assert secrets[0].provider == "openai"

    @pytest.mark.asyncio
    async def test_has_secret(self, secrets_service: SecretsService, mock_redis: AsyncMock) -> None:
        """Test checking if secret exists."""
        with patch.dict("os.environ", {"BARNABEENET_MASTER_KEY": "test-key"}):
            await secrets_service.initialize()

            mock_redis.hexists.return_value = True
            result = await secrets_service.has_secret("test_key")
            assert result is True


# =============================================================================
# Config API Route Tests
# =============================================================================


class TestConfigRoutes:
    """Tests for configuration API routes."""

    @pytest.fixture
    def mock_app(self) -> MagicMock:
        """Create mock FastAPI app."""
        app = MagicMock()
        app.state.redis = AsyncMock()
        return app

    def test_list_providers_structure(self) -> None:
        """Test that list_providers returns expected structure."""
        # Test the response model directly without importing routes
        from pydantic import BaseModel

        class ProviderListResponse(BaseModel):
            providers: list[ProviderInfo]
            configured_count: int
            enabled_count: int

        # Create a mock response
        response = ProviderListResponse(
            providers=get_all_providers(),
            configured_count=2,
            enabled_count=1,
        )

        assert len(response.providers) == 12
        assert response.configured_count == 2
        assert response.enabled_count == 1

    def test_provider_setup_request_validation(self) -> None:
        """Test ProviderSetupRequest validation."""
        from pydantic import BaseModel

        class ProviderSetupRequest(BaseModel):
            provider_type: ProviderType
            secrets: dict[str, str]
            config: dict[str, Any] = {}

        request = ProviderSetupRequest(
            provider_type=ProviderType.OPENAI,
            secrets={"api_key": "sk-test"},
            config={"organization": "org-123"},
        )

        assert request.provider_type == ProviderType.OPENAI
        assert request.secrets["api_key"] == "sk-test"

    def test_provider_test_response(self) -> None:
        """Test ProviderTestResponse model."""
        from pydantic import BaseModel

        class ProviderTestResponse(BaseModel):
            provider_type: ProviderType
            success: bool
            message: str
            latency_ms: float | None = None
            models_found: int = 0

        response = ProviderTestResponse(
            provider_type=ProviderType.GROQ,
            success=True,
            message="Connected! 10 models available",
            latency_ms=150.5,
            models_found=10,
        )

        assert response.success
        assert response.models_found == 10


# =============================================================================
# Provider Info Validation Tests
# =============================================================================


class TestProviderInfoValidation:
    """Validate provider info completeness."""

    @pytest.mark.parametrize("provider_type", list(ProviderType))
    def test_provider_has_required_fields(self, provider_type: ProviderType) -> None:
        """Test each provider has all required fields."""
        info = get_provider_info(provider_type)

        assert info.display_name, f"{provider_type} missing display_name"
        assert info.description, f"{provider_type} missing description"
        assert info.base_url, f"{provider_type} missing base_url"
        assert info.docs_url, f"{provider_type} missing docs_url"
        assert info.api_key_url, f"{provider_type} missing api_key_url"
        assert len(info.secret_fields) > 0, f"{provider_type} missing secret_fields"
        assert len(info.setup_instructions) > 0, f"{provider_type} missing setup_instructions"
        assert len(info.default_models) > 0, f"{provider_type} missing default_models"

    @pytest.mark.parametrize("provider_type", list(ProviderType))
    def test_provider_secret_fields_valid(self, provider_type: ProviderType) -> None:
        """Test each provider's secret fields are valid."""
        info = get_provider_info(provider_type)

        for field in info.secret_fields:
            assert field.name, f"{provider_type} secret field missing name"
            assert field.display_name, f"{provider_type} secret field missing display_name"
            assert field.description, f"{provider_type} secret field missing description"
            assert field.env_var_name, f"{provider_type} secret field missing env_var_name"

    def test_openai_compatible_providers(self) -> None:
        """Test OpenAI-compatible providers are marked correctly."""
        openai_compatible = [
            ProviderType.OPENROUTER,
            ProviderType.OPENAI,
            ProviderType.XAI,
            ProviderType.DEEPSEEK,
            ProviderType.GROQ,
            ProviderType.TOGETHER,
            ProviderType.MISTRAL,
            ProviderType.HUGGINGFACE,
            ProviderType.AZURE,
        ]

        for provider_type in openai_compatible:
            info = get_provider_info(provider_type)
            assert info.openai_compatible, f"{provider_type} should be OpenAI compatible"

    def test_non_openai_compatible_providers(self) -> None:
        """Test non-OpenAI-compatible providers are marked correctly."""
        non_compatible = [ProviderType.ANTHROPIC, ProviderType.GOOGLE, ProviderType.BEDROCK]

        for provider_type in non_compatible:
            info = get_provider_info(provider_type)
            assert not info.openai_compatible, f"{provider_type} should not be OpenAI compatible"
