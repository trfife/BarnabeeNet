"""Configuration API routes for LLM provider management.

Provides endpoints for:
- Listing available providers and their setup requirements
- Configuring provider credentials (encrypted storage)
- Testing provider connections
- Managing provider enable/disable state
- Listing available models from providers
- Configuring activity-based model selection
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
                limit_remaining = data.get("data", {}).get("limit_remaining")
                if limit_remaining is not None:
                    credit_msg = f"Credit: ${float(limit_remaining):.2f}"
                else:
                    credit_msg = "API key valid"
                return {
                    "success": True,
                    "message": f"Connected! {credit_msg}",
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


# =============================================================================
# Model Listing Endpoints
# =============================================================================


class ModelInfo(BaseModel):
    """Information about an available LLM model."""

    id: str
    name: str
    provider: str
    provider_display: str = ""  # Human-readable provider name
    context_length: int
    pricing_prompt: float  # per 1M tokens in USD
    pricing_completion: float  # per 1M tokens in USD
    modality: str = "text->text"
    is_free: bool = False
    description: str = ""
    health_status: str = "unknown"  # working, failed, unknown
    health_error: str | None = None


class ModelsListResponse(BaseModel):
    """Response with available models."""

    models: list[ModelInfo]
    total_count: int
    free_count: int
    working_count: int = 0
    provider: str
    providers_included: list[str] = []  # All providers included in this response


# Cache for model listings (refresh every 5 minutes)
_models_cache: dict[str, tuple[list[ModelInfo], datetime]] = {}
MODELS_CACHE_TTL_SECONDS = 300  # 5 minutes

# Background health check state
_last_health_check_time: datetime | None = None
HEALTH_CHECK_INTERVAL_SECONDS = 3600  # 1 hour


@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    request: Request,
    provider: str = "all",  # "all" fetches from all configured providers
    include_failed: bool = False,  # By default, exclude models that failed health check
    secrets: SecretsService = Depends(get_secrets),
) -> ModelsListResponse:
    """List available models from configured providers.

    By default, fetches from all configured providers and excludes models
    that have failed health checks. Set include_failed=True to see all models.
    """
    providers_to_fetch = []
    providers_included = []

    if provider == "all":
        # Get all configured providers
        from barnabeenet.models.provider_config import PROVIDER_REGISTRY

        stored_secrets = await secrets.list_secrets()
        configured_providers = {s.provider for s in stored_secrets}

        # Always include OpenRouter if configured
        if "openrouter" in configured_providers:
            providers_to_fetch.append("openrouter")

        # Add other configured providers
        for p in configured_providers:
            if p not in providers_to_fetch and p in [pt.value for pt in PROVIDER_REGISTRY]:
                providers_to_fetch.append(p)

        # If nothing configured, just use openrouter
        if not providers_to_fetch:
            providers_to_fetch = ["openrouter"]
    else:
        providers_to_fetch = [provider]

    all_models: list[ModelInfo] = []

    for prov in providers_to_fetch:
        cache_key = f"models_{prov}"

        # Check cache
        if cache_key in _models_cache:
            models, cached_at = _models_cache[cache_key]
            if (datetime.now(UTC) - cached_at).total_seconds() < MODELS_CACHE_TTL_SECONDS:
                all_models.extend(models)
                providers_included.append(prov)
                continue

        # Fetch from provider
        provider_secrets = await secrets.get_secrets_for_provider(prov)
        api_key = provider_secrets.get(f"{prov}_api_key")

        if prov == "openrouter":
            models = await _fetch_openrouter_models(api_key)
        elif prov == "openai":
            models = await _fetch_openai_models(api_key)
        elif prov == "anthropic":
            models = await _fetch_anthropic_models(api_key)
        else:
            # For other providers, add their default models
            models = _get_provider_default_models(prov)

        if models:
            _models_cache[cache_key] = (models, datetime.now(UTC))
            all_models.extend(models)
            providers_included.append(prov)

    # Apply health status to models
    for model in all_models:
        if model.id in _model_health_cache:
            working, _, error = _model_health_cache[model.id]
            model.health_status = "working" if working else "failed"
            model.health_error = error
        else:
            model.health_status = "unknown"

    # Filter out failed models unless requested
    if not include_failed:
        all_models = [m for m in all_models if m.health_status != "failed"]

    # Sort: working first, then unknown, then free, then by name
    def sort_key(m: ModelInfo) -> tuple:
        health_order = {"working": 0, "unknown": 1, "failed": 2}
        return (health_order.get(m.health_status, 1), not m.is_free, m.name.lower())

    all_models.sort(key=sort_key)

    working_count = sum(1 for m in all_models if m.health_status == "working")

    return ModelsListResponse(
        models=all_models,
        total_count=len(all_models),
        free_count=sum(1 for m in all_models if m.is_free),
        working_count=working_count,
        provider=provider,
        providers_included=providers_included,
    )


async def _fetch_openrouter_models(api_key: str | None = None) -> list[ModelInfo]:
    """Fetch available models from OpenRouter API."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
        )

        if response.status_code != 200:
            logger.error(f"Failed to fetch OpenRouter models: {response.status_code}")
            return []

        data = response.json()
        models_data = data.get("data", [])

        models = []
        for m in models_data:
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "0")) * 1_000_000  # Convert to per 1M
            completion_price = float(pricing.get("completion", "0")) * 1_000_000

            is_free = prompt_price == 0 and completion_price == 0

            models.append(
                ModelInfo(
                    id=m.get("id", ""),
                    name=m.get("name", m.get("id", "")),
                    provider="openrouter",
                    provider_display="OpenRouter",
                    context_length=m.get("context_length", 0),
                    pricing_prompt=prompt_price,
                    pricing_completion=completion_price,
                    modality=m.get("architecture", {}).get("modality", "text->text"),
                    is_free=is_free,
                    description=m.get("description", "")[:200],  # Truncate long descriptions
                )
            )

        # Sort: free models first, then by name
        models.sort(key=lambda x: (not x.is_free, x.name.lower()))

        return models


async def _fetch_openai_models(api_key: str | None = None) -> list[ModelInfo]:
    """Fetch available models from OpenAI API."""
    if not api_key:
        return _get_provider_default_models("openai")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers=headers,
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch OpenAI models: {response.status_code}")
                return _get_provider_default_models("openai")

            data = response.json()
            models_data = data.get("data", [])

            models = []
            for m in models_data:
                model_id = m.get("id", "")
                # Only include GPT models (skip embeddings, whisper, etc.)
                if not any(x in model_id for x in ["gpt", "o1", "o3"]):
                    continue

                models.append(
                    ModelInfo(
                        id=model_id,
                        name=model_id,
                        provider="openai",
                        provider_display="OpenAI",
                        context_length=128000,  # Default, varies by model
                        pricing_prompt=0,  # Would need separate pricing lookup
                        pricing_completion=0,
                        is_free=False,
                    )
                )

            models.sort(key=lambda x: x.name)
            return models
    except Exception as e:
        logger.error(f"Error fetching OpenAI models: {e}")
        return _get_provider_default_models("openai")


async def _fetch_anthropic_models(api_key: str | None = None) -> list[ModelInfo]:
    """Return known Anthropic models (no public models API)."""
    # Anthropic doesn't have a public models listing API
    return _get_provider_default_models("anthropic")


def _get_provider_default_models(provider: str) -> list[ModelInfo]:
    """Get default models for a provider from the registry."""
    from barnabeenet.models.provider_config import PROVIDER_REGISTRY, ProviderType

    try:
        provider_type = ProviderType(provider)
        provider_info = PROVIDER_REGISTRY.get(provider_type)

        if not provider_info:
            return []

        models = []
        for model_id in provider_info.default_models:
            models.append(
                ModelInfo(
                    id=model_id,
                    name=model_id,
                    provider=provider,
                    provider_display=provider_info.display_name,
                    context_length=128000,  # Default
                    pricing_prompt=0,
                    pricing_completion=0,
                    is_free=False,
                )
            )

        return models
    except ValueError:
        return []


@router.post("/models/refresh")
async def refresh_models_cache(
    provider: str = "openrouter",
) -> dict[str, Any]:
    """Force refresh the models cache for a provider."""
    cache_key = f"models_{provider}"
    if cache_key in _models_cache:
        del _models_cache[cache_key]

    # Also clear health cache
    global _model_health_cache
    _model_health_cache = {}

    return {"success": True, "message": f"Cache cleared for {provider}"}


# =============================================================================
# Model Health Check Endpoints
# =============================================================================

# Cache for model health status: model_id -> (working: bool, last_check: datetime, error: str|None)
_model_health_cache: dict[str, tuple[bool, datetime, str | None]] = {}
MODEL_HEALTH_CACHE_TTL_SECONDS = 600  # 10 minutes


class ModelHealthResponse(BaseModel):
    """Health status of a model."""

    model_id: str
    working: bool
    last_checked: datetime | None
    error: str | None = None
    latency_ms: float | None = None


class ModelHealthBatchResponse(BaseModel):
    """Batch health check results."""

    checked: int
    working: int
    failed: int
    results: list[ModelHealthResponse]


# NOTE: /schedule must come BEFORE /{model_id:path} to avoid capture
@router.post("/models/health-check/schedule")
async def trigger_scheduled_health_check(
    secrets: SecretsService = Depends(get_secrets),
    force: bool = False,
) -> dict[str, Any]:
    """Trigger the scheduled health check.

    Set force=True to run even if not enough time has passed.
    """
    global _last_health_check_time

    if force:
        _last_health_check_time = None  # Reset to force run

    result = await run_scheduled_health_check(secrets, limit=20)

    if result is None:
        next_check = _get_seconds_until_next_health_check()
        return {
            "ran": False,
            "message": f"Health check not due yet. Next check in {next_check} seconds.",
            "next_check_in_seconds": next_check,
        }

    return {
        "ran": True,
        "checked": result.checked,
        "working": result.working,
        "failed": result.failed,
    }


@router.post("/models/health-check/{model_id:path}")
async def check_model_health(
    model_id: str,
    request: Request,
    force: bool = False,
    secrets: SecretsService = Depends(get_secrets),
) -> ModelHealthResponse:
    """Check if a specific model is working by making a minimal test call.

    Results are cached for 10 minutes unless force=True.
    """
    import time

    # Check cache
    if not force and model_id in _model_health_cache:
        working, last_check, error = _model_health_cache[model_id]
        if (datetime.now(UTC) - last_check).total_seconds() < MODEL_HEALTH_CACHE_TTL_SECONDS:
            return ModelHealthResponse(
                model_id=model_id,
                working=working,
                last_checked=last_check,
                error=error,
            )

    # Get API key
    provider_secrets = await secrets.get_secrets_for_provider("openrouter")
    api_key = provider_secrets.get("openrouter_api_key")

    if not api_key:
        return ModelHealthResponse(
            model_id=model_id,
            working=False,
            last_checked=datetime.now(UTC),
            error="No OpenRouter API key configured",
        )

    # Make minimal test call
    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 5,
                },
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                _model_health_cache[model_id] = (True, datetime.now(UTC), None)
                return ModelHealthResponse(
                    model_id=model_id,
                    working=True,
                    last_checked=datetime.now(UTC),
                    latency_ms=latency_ms,
                )
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data["error"].get("message", error_msg)
                except Exception:
                    pass

                _model_health_cache[model_id] = (False, datetime.now(UTC), error_msg)
                return ModelHealthResponse(
                    model_id=model_id,
                    working=False,
                    last_checked=datetime.now(UTC),
                    error=error_msg,
                    latency_ms=latency_ms,
                )

    except Exception as e:
        error_msg = str(e)
        _model_health_cache[model_id] = (False, datetime.now(UTC), error_msg)
        return ModelHealthResponse(
            model_id=model_id,
            working=False,
            last_checked=datetime.now(UTC),
            error=error_msg,
        )


@router.post("/models/health-check-free")
async def check_free_models_health(
    request: Request,
    limit: int = 10,
    secrets: SecretsService = Depends(get_secrets),
) -> ModelHealthBatchResponse:
    """Check health of top free models and return working ones.

    This helps identify which free models are actually usable.
    """
    # Get current free models (include failed to check them again)
    models_response = await list_models(
        request=request,
        provider="all",
        include_failed=True,
        secrets=secrets,
    )
    free_models = [m for m in models_response.models if m.is_free][:limit]

    results = []
    working_count = 0
    failed_count = 0

    for model in free_models:
        result = await check_model_health(model.id, request, force=False, secrets=secrets)
        results.append(result)
        if result.working:
            working_count += 1
        else:
            failed_count += 1

    return ModelHealthBatchResponse(
        checked=len(results),
        working=working_count,
        failed=failed_count,
        results=results,
    )


@router.get("/models/health-status")
async def get_model_health_status() -> dict[str, Any]:
    """Get cached health status for all checked models."""
    statuses = {}
    for model_id, (working, last_check, error) in _model_health_cache.items():
        statuses[model_id] = {
            "working": working,
            "last_checked": last_check.isoformat(),
            "error": error,
        }

    global _last_health_check_time
    last_check_str = _last_health_check_time.isoformat() if _last_health_check_time else None

    return {
        "total_checked": len(statuses),
        "working": sum(1 for s in statuses.values() if s["working"]),
        "failed": sum(1 for s in statuses.values() if not s["working"]),
        "last_full_check": last_check_str,
        "next_check_in_seconds": _get_seconds_until_next_health_check(),
        "models": statuses,
    }


def _get_seconds_until_next_health_check() -> int | None:
    """Calculate seconds until next scheduled health check."""
    global _last_health_check_time
    if _last_health_check_time is None:
        return 0  # Should run immediately

    elapsed = (datetime.now(UTC) - _last_health_check_time).total_seconds()
    remaining = HEALTH_CHECK_INTERVAL_SECONDS - elapsed
    return max(0, int(remaining))


async def run_scheduled_health_check(
    secrets: SecretsService,
    limit: int = 20,
) -> ModelHealthBatchResponse | None:
    """Run health check if enough time has passed since last check.

    Called periodically (e.g., from a background task or on-demand).
    Returns None if not enough time has passed.
    """
    global _last_health_check_time

    # Check if enough time has passed
    if _last_health_check_time is not None:
        elapsed = (datetime.now(UTC) - _last_health_check_time).total_seconds()
        if elapsed < HEALTH_CHECK_INTERVAL_SECONDS:
            return None

    logger.info("Running scheduled model health check")

    # Get free models directly (can't use list_models without Request)
    openrouter_secrets = await secrets.get_secrets_for_provider("openrouter")
    api_key = openrouter_secrets.get("openrouter_api_key")

    if not api_key:
        logger.warning("No OpenRouter API key configured for health check")
        return None

    models = await _fetch_openrouter_models(api_key)
    free_models = [m for m in models if m.is_free][:limit]

    results = []
    working_count = 0
    failed_count = 0

    for model in free_models:
        result = await _check_model_health_internal(model.id, api_key)
        results.append(result)
        if result.working:
            working_count += 1
        else:
            failed_count += 1

    _last_health_check_time = datetime.now(UTC)
    logger.info(
        f"Health check complete: {working_count} working, {failed_count} failed of {len(results)} checked"
    )

    return ModelHealthBatchResponse(
        checked=len(results),
        working=working_count,
        failed=failed_count,
        results=results,
    )


async def _check_model_health_internal(model_id: str, api_key: str) -> ModelHealthResponse:
    """Internal health check without Request dependency."""
    import time

    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 5,
                },
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                _model_health_cache[model_id] = (True, datetime.now(UTC), None)
                return ModelHealthResponse(
                    model_id=model_id,
                    working=True,
                    last_checked=datetime.now(UTC),
                    latency_ms=latency_ms,
                )
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data["error"].get("message", error_msg)
                except Exception:
                    pass

                _model_health_cache[model_id] = (False, datetime.now(UTC), error_msg)
                return ModelHealthResponse(
                    model_id=model_id,
                    working=False,
                    last_checked=datetime.now(UTC),
                    error=error_msg,
                    latency_ms=latency_ms,
                )

    except Exception as e:
        error_msg = str(e)
        _model_health_cache[model_id] = (False, datetime.now(UTC), error_msg)
        return ModelHealthResponse(
            model_id=model_id,
            working=False,
            last_checked=datetime.now(UTC),
            error=error_msg,
        )


# =============================================================================
# AI-Powered Model Auto-Selection
# =============================================================================


class AutoSelectRequest(BaseModel):
    """Request for AI auto-selection."""

    free_only: bool = True
    prefer_speed: bool = False
    prefer_quality: bool = False


class AutoSelectResponse(BaseModel):
    """Response from AI auto-selection."""

    success: bool
    recommendations: dict[str, str]  # activity -> model
    reasoning: dict[str, str]  # activity -> why this model
    applied: bool = False
    error: str | None = None


@router.post("/activities/auto-select")
async def auto_select_models(
    request: Request,
    params: AutoSelectRequest,
    secrets: SecretsService = Depends(get_secrets),
) -> AutoSelectResponse:
    """Use AI to intelligently select optimal models for each activity.

    Analyzes each activity's requirements (speed, accuracy, quality, context length)
    and matches them to the best available models.
    """
    import json

    from barnabeenet.services.llm.activities import DEFAULT_ACTIVITY_CONFIGS

    # Get available models with health status (include failed to see health)
    models_response = await list_models(
        request=request,
        provider="all",
        include_failed=True,
        secrets=secrets,
    )

    if params.free_only:
        available_models = [m for m in models_response.models if m.is_free]
    else:
        available_models = models_response.models

    if not available_models:
        return AutoSelectResponse(
            success=False,
            recommendations={},
            reasoning={},
            error="No models available" + (" (free only)" if params.free_only else ""),
        )

    # Filter to only working models if we have health data
    working_models = []
    for m in available_models:
        if m.id in _model_health_cache:
            working, _, _ = _model_health_cache[m.id]
            if working:
                working_models.append(m)
        else:
            # Include unchecked models
            working_models.append(m)

    if not working_models:
        working_models = available_models  # Fall back to all if none verified

    # Build model summary for AI
    model_summary = []
    for m in working_models[:30]:  # Limit to top 30
        health_note = ""
        if m.id in _model_health_cache:
            working, _, _ = _model_health_cache[m.id]
            health_note = " [VERIFIED WORKING]" if working else " [FAILED]"

        model_summary.append(
            f"- {m.id}: {m.name}, context={m.context_length}, "
            f"{'FREE' if m.is_free else f'${m.pricing_prompt}/1M in, ${m.pricing_completion}/1M out'}"
            f"{health_note}"
        )

    # Build activity summary
    activity_summary = []
    for activity_name, config in DEFAULT_ACTIVITY_CONFIGS.items():
        activity_summary.append(
            f"- {activity_name}: {config['description']}, "
            f"priority={config['priority']}, max_tokens={config['max_tokens']}"
        )

    # Create prompt for AI
    system_prompt = """You are an expert at selecting LLM models for different tasks.
Given a list of available models and activities that need models assigned, select the BEST model for each activity.

Consider:
1. Activity PRIORITY: "speed" needs fast models, "accuracy" needs reliable models, "quality" needs best output, "balanced" is flexible
2. MAX_TOKENS: Ensure model context length can handle the task
3. Model capabilities: Some models are better at certain tasks (coding, conversation, analysis)
4. If a model is marked [VERIFIED WORKING], prefer it over unchecked ones
5. NEVER select a model marked [FAILED]

Respond with ONLY a JSON object mapping activity names to model IDs, like:
{"meta.classify_intent": "model/id", "interaction.respond": "other/model", ...}

Include ALL activities listed."""

    user_prompt = f"""Available Models:
{chr(10).join(model_summary)}

Activities needing models:
{chr(10).join(activity_summary)}

Preferences:
- Free models only: {params.free_only}
- Prefer speed: {params.prefer_speed}
- Prefer quality: {params.prefer_quality}

Select the best model for EACH activity. Return ONLY the JSON mapping."""

    # Get API key and make call
    provider_secrets = await secrets.get_secrets_for_provider("openrouter")
    api_key = provider_secrets.get("openrouter_api_key")

    if not api_key:
        return AutoSelectResponse(
            success=False,
            recommendations={},
            reasoning={},
            error="No OpenRouter API key configured",
        )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Use a verified working model for the selection
            # Priority: deepseek-r1 (good reasoning), llama-3.3-70b, mistral devstral, then any working
            preferred_selectors = [
                "deepseek/deepseek-r1-0528:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "mistralai/devstral-2512:free",
                "google/gemma-3-27b-it:free",
                "nvidia/nemotron-nano-9b-v2:free",
            ]

            selector_model = None
            if params.free_only:
                # Find a verified working model
                for model_id in preferred_selectors:
                    if model_id in _model_health_cache:
                        working, _, _ = _model_health_cache[model_id]
                        if working:
                            selector_model = model_id
                            break
                # Fallback to first preferred if no health data
                if not selector_model:
                    selector_model = preferred_selectors[0]
            else:
                selector_model = "anthropic/claude-3.5-sonnet"

            logger.info(f"Auto-select using selector model: {selector_model}")

            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": selector_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.3,
                },
            )

            if response.status_code != 200:
                return AutoSelectResponse(
                    success=False,
                    recommendations={},
                    reasoning={},
                    error=f"AI call failed: HTTP {response.status_code}",
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response
            # Handle DeepSeek R1's <think> reasoning tokens
            if "<think>" in content and "</think>" in content:
                content = content.split("</think>")[-1]

            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            # Try to extract JSON object from anywhere in the content
            content = content.strip()
            if not content.startswith("{"):
                # Find first { and last }
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    content = content[start : end + 1]

            logger.debug(f"Auto-select parsing JSON: {content[:200]}...")
            recommendations = json.loads(content.strip())

            # Validate recommendations
            valid_recs = {}
            reasoning = {}
            valid_model_ids = {m.id for m in available_models}

            for activity, model_id in recommendations.items():
                if activity in DEFAULT_ACTIVITY_CONFIGS:
                    if model_id in valid_model_ids:
                        valid_recs[activity] = model_id
                        priority = DEFAULT_ACTIVITY_CONFIGS[activity]["priority"]
                        reasoning[activity] = f"Selected for {priority} priority task"
                    else:
                        # Model not in our list, use a fallback
                        fallback = working_models[0].id if working_models else available_models[0].id
                        valid_recs[activity] = fallback
                        reasoning[activity] = f"Fallback (requested {model_id} not available)"

            # Fill any missing activities
            for activity in DEFAULT_ACTIVITY_CONFIGS:
                if activity not in valid_recs:
                    valid_recs[activity] = working_models[0].id if working_models else available_models[0].id
                    reasoning[activity] = "Default fallback"

            return AutoSelectResponse(
                success=True,
                recommendations=valid_recs,
                reasoning=reasoning,
            )

    except json.JSONDecodeError as e:
        return AutoSelectResponse(
            success=False,
            recommendations={},
            reasoning={},
            error=f"Failed to parse AI response: {e}",
        )
    except Exception as e:
        return AutoSelectResponse(
            success=False,
            recommendations={},
            reasoning={},
            error=f"AI selection failed: {e}",
        )


@router.post("/activities/auto-select/apply")
async def apply_auto_selection(
    request: Request,
    params: AutoSelectRequest,
    secrets: SecretsService = Depends(get_secrets),
) -> AutoSelectResponse:
    """Auto-select models AND apply them to all activities."""
    import json

    from barnabeenet.services.llm.activities import get_activity_config_manager

    # First get recommendations
    result = await auto_select_models(request, params, secrets)

    if not result.success:
        return result

    # Apply recommendations
    redis = request.app.state.redis
    manager = get_activity_config_manager()

    for activity_name, model in result.recommendations.items():
        # Store in Redis
        override = {"model": model}
        await redis.hset(ACTIVITY_CONFIGS_KEY, activity_name, json.dumps(override))

        # Update in-memory
        try:
            config = manager.get(activity_name)
            config.model = model
        except Exception:
            pass

    logger.info(f"Applied auto-selection: {len(result.recommendations)} activities updated")

    result.applied = True
    return result


# =============================================================================
# Activity Configuration Endpoints
# =============================================================================


class ActivityConfigResponse(BaseModel):
    """Configuration for a single activity."""

    activity: str
    model: str
    temperature: float
    max_tokens: int
    priority: str
    description: str
    provider_override: str | None = None


class AllActivitiesResponse(BaseModel):
    """All activity configurations."""

    activities: list[ActivityConfigResponse]
    groups: dict[str, list[str]]  # Group activities by agent


class UpdateActivityRequest(BaseModel):
    """Request to update activity configuration."""

    model: str
    temperature: float | None = None
    max_tokens: int | None = None


# Redis key for activity config overrides
ACTIVITY_CONFIGS_KEY = "barnabeenet:activity_configs"


@router.get("/activities", response_model=AllActivitiesResponse)
async def list_activities(request: Request) -> AllActivitiesResponse:
    """List all LLM activities and their current configuration.

    Returns activities grouped by agent (meta, action, interaction, memory, instant).
    """
    from barnabeenet.services.llm.activities import get_activity_config_manager

    manager = get_activity_config_manager()

    # Load any Redis overrides
    redis = request.app.state.redis
    overrides = await redis.hgetall(ACTIVITY_CONFIGS_KEY)

    activities = []
    groups: dict[str, list[str]] = {
        "meta": [],
        "action": [],
        "interaction": [],
        "memory": [],
        "instant": [],
    }

    for activity_name, config in manager.get_all().items():
        # Apply Redis override if exists
        if activity_name in overrides:
            import json

            override = json.loads(overrides[activity_name])
            config.model = override.get("model", config.model)
            if "temperature" in override:
                config.temperature = override["temperature"]
            if "max_tokens" in override:
                config.max_tokens = override["max_tokens"]

        activities.append(
            ActivityConfigResponse(
                activity=activity_name,
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                priority=config.priority,
                description=config.description,
                provider_override=config.provider_override,
            )
        )

        # Group by agent prefix
        agent = activity_name.split(".")[0] if "." in activity_name else "other"
        if agent in groups:
            groups[agent].append(activity_name)

    # Sort activities by name
    activities.sort(key=lambda x: x.activity)

    return AllActivitiesResponse(activities=activities, groups=groups)


@router.get("/activities/{activity_name}", response_model=ActivityConfigResponse)
async def get_activity(request: Request, activity_name: str) -> ActivityConfigResponse:
    """Get configuration for a specific activity."""
    from barnabeenet.services.llm.activities import get_activity_config_manager

    manager = get_activity_config_manager()
    all_activities = manager.get_all()

    if activity_name not in all_activities:
        raise HTTPException(status_code=404, detail=f"Activity not found: {activity_name}")

    config = all_activities[activity_name]

    # Apply Redis override if exists
    redis = request.app.state.redis
    override_json = await redis.hget(ACTIVITY_CONFIGS_KEY, activity_name)
    if override_json:
        import json

        override = json.loads(override_json)
        config.model = override.get("model", config.model)
        if "temperature" in override:
            config.temperature = override["temperature"]
        if "max_tokens" in override:
            config.max_tokens = override["max_tokens"]

    return ActivityConfigResponse(
        activity=activity_name,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        priority=config.priority,
        description=config.description,
        provider_override=config.provider_override,
    )


@router.put("/activities/{activity_name}")
async def update_activity(
    request: Request,
    activity_name: str,
    update: UpdateActivityRequest,
) -> dict[str, Any]:
    """Update configuration for a specific activity.

    Changes are stored in Redis and override defaults.
    """
    import json

    from barnabeenet.services.llm.activities import get_activity_config_manager

    manager = get_activity_config_manager()
    all_activities = manager.get_all()

    if activity_name not in all_activities:
        raise HTTPException(status_code=404, detail=f"Activity not found: {activity_name}")

    # Build override dict
    override: dict[str, Any] = {"model": update.model}
    if update.temperature is not None:
        override["temperature"] = update.temperature
    if update.max_tokens is not None:
        override["max_tokens"] = update.max_tokens

    # Store in Redis
    redis = request.app.state.redis
    await redis.hset(ACTIVITY_CONFIGS_KEY, activity_name, json.dumps(override))

    # Also update the in-memory manager
    config = manager.get(activity_name)
    config.model = update.model
    if update.temperature is not None:
        config.temperature = update.temperature
    if update.max_tokens is not None:
        config.max_tokens = update.max_tokens

    logger.info(f"Updated activity config: {activity_name} -> {update.model}")

    return {
        "success": True,
        "activity": activity_name,
        "model": update.model,
        "temperature": update.temperature or config.temperature,
        "max_tokens": update.max_tokens or config.max_tokens,
    }


@router.delete("/activities/{activity_name}/override")
async def reset_activity(request: Request, activity_name: str) -> dict[str, Any]:
    """Reset activity configuration to defaults (remove Redis override)."""
    from barnabeenet.services.llm.activities import (
        DEFAULT_ACTIVITY_CONFIGS,
        get_activity_config_manager,
    )

    if activity_name not in DEFAULT_ACTIVITY_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Activity not found: {activity_name}")

    # Remove from Redis
    redis = request.app.state.redis
    await redis.hdel(ACTIVITY_CONFIGS_KEY, activity_name)

    # Reset in-memory config
    manager = get_activity_config_manager()
    default_config = DEFAULT_ACTIVITY_CONFIGS[activity_name]
    config = manager.get(activity_name)
    config.model = default_config["model"]
    config.temperature = default_config.get("temperature", 0.7)
    config.max_tokens = default_config.get("max_tokens", 1000)

    logger.info(f"Reset activity config: {activity_name}")

    return {
        "success": True,
        "activity": activity_name,
        "reset_to": default_config,
    }


# =============================================================================
# Mode Presets (Testing vs Production)
# =============================================================================

# Best free models for testing (as of Jan 2026)
TESTING_MODE_MODELS: dict[str, str] = {
    # MetaAgent - needs to be fast, free Gemini is great
    "meta.classify_intent": "google/gemini-2.0-flash-exp:free",
    "meta.evaluate_context": "google/gemini-2.0-flash-exp:free",
    "meta.generate_queries": "google/gemini-2.0-flash-exp:free",
    # ActionAgent - needs accuracy, Gemini handles this well
    "action.parse_intent": "google/gemini-2.0-flash-exp:free",
    "action.resolve_entities": "google/gemini-2.0-flash-exp:free",
    "action.generate_confirm": "google/gemini-2.0-flash-exp:free",
    "action.generate_error": "google/gemini-2.0-flash-exp:free",
    # InteractionAgent - quality matters, Gemini 2.0 Flash is good
    "interaction.respond": "google/gemini-2.0-flash-exp:free",
    "interaction.followup": "google/gemini-2.0-flash-exp:free",
    "interaction.empathy": "google/gemini-2.0-flash-exp:free",
    "interaction.factual": "google/gemini-2.0-flash-exp:free",
    # MemoryAgent - summarization, Gemini handles well
    "memory.generate": "google/gemini-2.0-flash-exp:free",
    "memory.extract_facts": "google/gemini-2.0-flash-exp:free",
    "memory.summarize": "google/gemini-2.0-flash-exp:free",
    "memory.rank": "google/gemini-2.0-flash-exp:free",
    # InstantAgent fallback
    "instant.fallback": "google/gemini-2.0-flash-exp:free",
}

# Recommended production models (quality + cost balance)
PRODUCTION_MODE_MODELS: dict[str, str] = {
    # MetaAgent - fast/cheap for every request
    "meta.classify_intent": "deepseek/deepseek-chat",
    "meta.evaluate_context": "deepseek/deepseek-chat",
    "meta.generate_queries": "deepseek/deepseek-chat",
    # ActionAgent - accuracy for device control
    "action.parse_intent": "openai/gpt-4o-mini",
    "action.resolve_entities": "openai/gpt-4o-mini",
    "action.generate_confirm": "deepseek/deepseek-chat",
    "action.generate_error": "deepseek/deepseek-chat",
    # InteractionAgent - quality for personality
    "interaction.respond": "anthropic/claude-3.5-sonnet",
    "interaction.followup": "anthropic/claude-3.5-sonnet",
    "interaction.empathy": "anthropic/claude-3.5-sonnet",
    "interaction.factual": "openai/gpt-4o",
    # MemoryAgent - good summarization
    "memory.generate": "openai/gpt-4o-mini",
    "memory.extract_facts": "openai/gpt-4o-mini",
    "memory.summarize": "openai/gpt-4o-mini",
    "memory.rank": "deepseek/deepseek-chat",
    # InstantAgent fallback
    "instant.fallback": "deepseek/deepseek-chat",
}

# Redis key for current mode
MODE_KEY = "barnabeenet:model_mode"


class ModePreset(BaseModel):
    """Mode preset configuration."""

    mode: str  # "testing" or "production"


class ModeResponse(BaseModel):
    """Response after switching modes."""

    mode: str
    updated_count: int
    models: dict[str, str]


@router.get("/mode")
async def get_current_mode(request: Request) -> dict[str, str]:
    """Get the current model mode (testing or production)."""
    redis = request.app.state.redis
    mode = await redis.get(MODE_KEY)
    return {"mode": mode.decode() if mode else "testing"}


@router.post("/mode", response_model=ModeResponse)
async def set_mode(request: Request, preset: ModePreset) -> ModeResponse:
    """Switch all activities to testing or production models.

    Testing mode: All free models (Google Gemini 2.0 Flash)
    Production mode: Recommended quality models (Claude, GPT-4o, DeepSeek)
    """
    import json

    from barnabeenet.services.llm.activities import get_activity_config_manager

    if preset.mode not in ("testing", "production"):
        raise HTTPException(
            status_code=400,
            detail="Mode must be 'testing' or 'production'",
        )

    models = TESTING_MODE_MODELS if preset.mode == "testing" else PRODUCTION_MODE_MODELS

    redis = request.app.state.redis
    manager = get_activity_config_manager()

    updated = 0
    for activity_name, model in models.items():
        # Store in Redis
        override = {"model": model}
        await redis.hset(ACTIVITY_CONFIGS_KEY, activity_name, json.dumps(override))

        # Update in-memory
        try:
            config = manager.get(activity_name)
            config.model = model
            updated += 1
        except Exception:
            pass  # Activity might not exist

    # Store current mode
    await redis.set(MODE_KEY, preset.mode)

    logger.info(f"Switched to {preset.mode} mode, updated {updated} activities")

    return ModeResponse(
        mode=preset.mode,
        updated_count=updated,
        models=models,
    )
