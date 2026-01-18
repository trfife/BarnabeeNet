"""Configuration API routes for LLM provider management.

Provides endpoints for:
- Listing available providers and their setup requirements
- Configuring provider credentials (encrypted storage)
- Testing provider connections
- Managing provider enable/disable state
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from barnabeenet.models.provider_config import (
    PROVIDER_REGISTRY,
    ProviderConfig,
    ProviderInfo,
    ProviderStatus,
    ProviderType,
    get_all_providers,
    get_provider_info,
)
from barnabeenet.services.secrets import SecretMetadata, SecretsService, get_secrets_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["configuration"])

# Redis key for provider configs (non-secret data)
PROVIDER_CONFIGS_KEY = "barnabeenet:provider_configs"


# =============================================================================
# Request/Response Models
# =============================================================================


class ProviderListResponse(BaseModel):
    """Response with all available providers."""

    providers: list[ProviderInfo]
    configured_count: int
    enabled_count: int


class ProviderSetupRequest(BaseModel):
    """Request to configure a provider's credentials."""

    provider_type: ProviderType
    secrets: dict[str, str]  # field_name -> value
    config: dict[str, Any] = {}  # Non-secret config fields


class ProviderEnableRequest(BaseModel):
    """Request to enable/disable a provider."""

    provider_type: ProviderType
    enabled: bool


class ProviderTestRequest(BaseModel):
    """Request to test a provider connection."""

    provider_type: ProviderType


class ProviderTestResponse(BaseModel):
    """Response from provider test."""

    provider_type: ProviderType
    success: bool
    message: str
    latency_ms: float | None = None
    models_found: int = 0


class SecretsListResponse(BaseModel):
    """Response with stored secrets metadata (not values)."""

    secrets: list[SecretMetadata]
    providers_with_secrets: list[str]


class ProviderStatusResponse(BaseModel):
    """Response with provider status."""

    statuses: list[ProviderStatus]


# =============================================================================
# Dependency Injection
# =============================================================================


async def get_redis(request: Request):
    """Get Redis client from app state."""
    return request.app.state.redis


async def get_secrets(request: Request) -> SecretsService:
    """Get secrets service."""
    redis = request.app.state.redis
    return await get_secrets_service(redis)
    return await get_secrets_service(redis)


# =============================================================================
# Provider Information Endpoints
# =============================================================================


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers(
    request: Request,
    secrets: SecretsService = Depends(get_secrets),
) -> ProviderListResponse:
    """List all available LLM providers with their setup requirements."""
    providers = get_all_providers()
    stored_secrets = await secrets.list_secrets()

    # Count configured and enabled providers
    providers_with_secrets = {s.provider for s in stored_secrets}
    redis = request.app.state.redis
    configs = await redis.hgetall(PROVIDER_CONFIGS_KEY)

    configured_count = len(providers_with_secrets)
    enabled_count = 0

    for _provider_type, config_json in configs.items():
        import json

        config = json.loads(config_json)
        if config.get("enabled"):
            enabled_count += 1

    return ProviderListResponse(
        providers=providers,
        configured_count=configured_count,
        enabled_count=enabled_count,
    )


@router.get("/providers/status", response_model=ProviderStatusResponse)
async def get_providers_status(
    request: Request,
    secrets: SecretsService = Depends(get_secrets),
) -> ProviderStatusResponse:
    """Get status of all providers (configured, enabled, health)."""
    import json

    stored_secrets = await secrets.list_secrets()
    providers_with_secrets = {s.provider for s in stored_secrets}
    redis = request.app.state.redis
    configs = await redis.hgetall(PROVIDER_CONFIGS_KEY)

    statuses = []
    for provider_type in ProviderType:
        info = get_provider_info(provider_type)

        # Check if configured
        configured = provider_type.value in providers_with_secrets

        # Check if enabled
        enabled = False
        config_json = configs.get(provider_type.value)
        if config_json:
            config = json.loads(config_json)
            enabled = config.get("enabled", False)

        statuses.append(
            ProviderStatus(
                provider_type=provider_type,
                display_name=info.display_name,
                enabled=enabled,
                configured=configured,
                health_status="unknown",
            )
        )

    return ProviderStatusResponse(statuses=statuses)


@router.get("/providers/{provider_type}", response_model=ProviderInfo)
async def get_provider(provider_type: ProviderType) -> ProviderInfo:
    """Get detailed information about a specific provider."""
    if provider_type not in PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_type}")
    return get_provider_info(provider_type)


# =============================================================================
# Provider Configuration Endpoints
# =============================================================================


@router.post("/providers/setup")
async def setup_provider(
    request: Request,
    setup_request: ProviderSetupRequest,
    secrets: SecretsService = Depends(get_secrets),
) -> dict[str, Any]:
    """Configure a provider with credentials.

    Stores secrets encrypted, config in plain JSON.
    """

    provider_info = get_provider_info(setup_request.provider_type)

    # Validate required secrets
    required_fields = [f.name for f in provider_info.secret_fields if f.required]
    missing = [
        f for f in required_fields if f not in setup_request.secrets or not setup_request.secrets[f]
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required secrets: {', '.join(missing)}",
        )

    # Store each secret
    stored_secrets = []
    for field_name, value in setup_request.secrets.items():
        if value:  # Only store non-empty values
            key_name = f"{setup_request.provider_type.value}_{field_name}"
            meta = await secrets.set_secret(
                key_name=key_name,
                value=value,
                provider=setup_request.provider_type.value,
            )
            stored_secrets.append(meta)

    # Store non-secret config
    redis = request.app.state.redis
    config = ProviderConfig(
        provider_type=setup_request.provider_type,
        enabled=True,  # Enable on setup
        extra_config=setup_request.config,
    )
    await redis.hset(
        PROVIDER_CONFIGS_KEY,
        setup_request.provider_type.value,
        config.model_dump_json(),
    )

    logger.info(f"Configured provider: {setup_request.provider_type.value}")

    return {
        "success": True,
        "provider": setup_request.provider_type.value,
        "secrets_stored": len(stored_secrets),
        "enabled": True,
    }


@router.post("/providers/enable")
async def enable_provider(
    request: Request,
    enable_request: ProviderEnableRequest,
) -> dict[str, Any]:
    """Enable or disable a provider."""
    import json

    redis = request.app.state.redis
    config_json = await redis.hget(PROVIDER_CONFIGS_KEY, enable_request.provider_type.value)

    if config_json:
        config = json.loads(config_json)
    else:
        config = {"provider_type": enable_request.provider_type.value, "extra_config": {}}

    config["enabled"] = enable_request.enabled
    await redis.hset(
        PROVIDER_CONFIGS_KEY,
        enable_request.provider_type.value,
        json.dumps(config),
    )

    logger.info(f"Provider {enable_request.provider_type.value} enabled={enable_request.enabled}")

    return {
        "success": True,
        "provider": enable_request.provider_type.value,
        "enabled": enable_request.enabled,
    }


@router.delete("/providers/{provider_type}")
async def delete_provider(
    request: Request,
    provider_type: ProviderType,
    secrets: SecretsService = Depends(get_secrets),
) -> dict[str, Any]:
    """Remove a provider's configuration and credentials."""
    # Delete all secrets for this provider
    stored_secrets = await secrets.list_secrets()
    deleted_count = 0
    for secret in stored_secrets:
        if secret.provider == provider_type.value:
            await secrets.delete_secret(secret.key_name)
            deleted_count += 1

    # Delete config
    redis = request.app.state.redis
    await redis.hdel(PROVIDER_CONFIGS_KEY, provider_type.value)

    logger.info(f"Deleted provider config: {provider_type.value}")

    return {
        "success": True,
        "provider": provider_type.value,
        "secrets_deleted": deleted_count,
    }


# =============================================================================
# Provider Testing Endpoints
# =============================================================================


@router.post("/providers/test", response_model=ProviderTestResponse)
async def test_provider(
    test_request: ProviderTestRequest,
    secrets: SecretsService = Depends(get_secrets),
) -> ProviderTestResponse:
    """Test a provider connection by listing models or making a simple API call."""
    provider_info = get_provider_info(test_request.provider_type)

    # Get secrets for this provider
    provider_secrets = await secrets.get_secrets_for_provider(test_request.provider_type.value)

    if not provider_secrets:
        return ProviderTestResponse(
            provider_type=test_request.provider_type,
            success=False,
            message="No credentials configured for this provider",
        )

    # Get API key (most providers use 'api_key')
    api_key = provider_secrets.get(f"{test_request.provider_type.value}_api_key")
    if not api_key:
        # Try alternate names
        for key_name, value in provider_secrets.items():
            if "key" in key_name or "token" in key_name:
                api_key = value
                break

    if not api_key:
        return ProviderTestResponse(
            provider_type=test_request.provider_type,
            success=False,
            message="API key not found in stored credentials",
        )

    # Test based on provider type
    start_time = datetime.now(UTC)
    try:
        result = await _test_provider_connection(test_request.provider_type, api_key, provider_info)
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        return ProviderTestResponse(
            provider_type=test_request.provider_type,
            success=result["success"],
            message=result["message"],
            latency_ms=latency_ms,
            models_found=result.get("models_found", 0),
        )
    except Exception as e:
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        logger.exception(f"Provider test failed: {test_request.provider_type.value}")
        return ProviderTestResponse(
            provider_type=test_request.provider_type,
            success=False,
            message=f"Connection failed: {e!s}",
            latency_ms=latency_ms,
        )


async def _test_provider_connection(
    provider_type: ProviderType,
    api_key: str,
    provider_info: ProviderInfo,
) -> dict[str, Any]:
    """Test connection to a specific provider."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        if provider_type == ProviderType.OPENROUTER:
            # OpenRouter: Check /api/v1/auth/key
            response = await client.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": f"Connected! Credit: ${data.get('data', {}).get('limit_remaining', 0):.2f}",
                }
            return {"success": False, "message": f"Auth failed: {response.status_code}"}

        elif provider_type in (
            ProviderType.OPENAI,
            ProviderType.GROQ,
            ProviderType.TOGETHER,
            ProviderType.MISTRAL,
        ):
            # OpenAI-compatible: List models
            response = await client.get(
                f"{provider_info.base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                return {
                    "success": True,
                    "message": f"Connected! {len(models)} models available",
                    "models_found": len(models),
                }
            return {"success": False, "message": f"Auth failed: {response.status_code}"}

        elif provider_type == ProviderType.ANTHROPIC:
            # Anthropic: Make a minimal completion request
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            if response.status_code == 200:
                return {"success": True, "message": "Connected! API key valid"}
            elif response.status_code == 401:
                return {"success": False, "message": "Invalid API key"}
            return {"success": False, "message": f"API error: {response.status_code}"}

        elif provider_type == ProviderType.GOOGLE:
            # Google: List models
            response = await client.get(
                f"https://generativelanguage.googleapis.com/v1/models?key={api_key}",
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return {
                    "success": True,
                    "message": f"Connected! {len(models)} models available",
                    "models_found": len(models),
                }
            return {"success": False, "message": f"Auth failed: {response.status_code}"}

        elif provider_type == ProviderType.DEEPSEEK:
            # DeepSeek: OpenAI-compatible
            response = await client.get(
                "https://api.deepseek.com/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                return {
                    "success": True,
                    "message": f"Connected! {len(models)} models available",
                    "models_found": len(models),
                }
            return {"success": False, "message": f"Auth failed: {response.status_code}"}

        elif provider_type == ProviderType.XAI:
            # xAI: OpenAI-compatible
            response = await client.get(
                "https://api.x.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                return {
                    "success": True,
                    "message": f"Connected! {len(models)} models available",
                    "models_found": len(models),
                }
            return {"success": False, "message": f"Auth failed: {response.status_code}"}

        elif provider_type == ProviderType.HUGGINGFACE:
            # HuggingFace: Check whoami
            response = await client.get(
                "https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message": f"Connected as {data.get('name', 'unknown')}",
                }
            return {"success": False, "message": f"Auth failed: {response.status_code}"}

        elif provider_type == ProviderType.AZURE:
            # Azure requires resource name, can't test without config
            return {
                "success": True,
                "message": "API key stored. Configure resource name to test connection.",
            }

        elif provider_type == ProviderType.BEDROCK:
            # AWS Bedrock requires SDK, can't test simply
            return {
                "success": True,
                "message": "AWS credentials stored. Requires AWS SDK for full test.",
            }

        else:
            return {
                "success": True,
                "message": "Credentials stored. Connection test not implemented.",
            }


# =============================================================================
# Secrets Management Endpoints
# =============================================================================


@router.get("/secrets", response_model=SecretsListResponse)
async def list_secrets(
    secrets: SecretsService = Depends(get_secrets),
) -> SecretsListResponse:
    """List all stored secrets (metadata only, not values)."""
    stored_secrets = await secrets.list_secrets()
    providers = list({s.provider for s in stored_secrets})

    return SecretsListResponse(
        secrets=stored_secrets,
        providers_with_secrets=sorted(providers),
    )


@router.delete("/secrets/{key_name}")
async def delete_secret(
    key_name: str,
    secrets: SecretsService = Depends(get_secrets),
) -> dict[str, Any]:
    """Delete a specific secret."""
    deleted = await secrets.delete_secret(key_name)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Secret not found: {key_name}")

    return {"success": True, "deleted": key_name}
