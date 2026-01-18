"""LLM Provider configuration models.

Defines all supported providers with their authentication requirements,
endpoints, and setup instructions for the dashboard configuration UI.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    GOOGLE = "google"
    XAI = "xai"
    DEEPSEEK = "deepseek"
    HUGGINGFACE = "huggingface"
    BEDROCK = "bedrock"
    TOGETHER = "together"
    MISTRAL = "mistral"
    GROQ = "groq"


class AuthType(str, Enum):
    """Authentication method types."""

    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    AWS_CREDENTIALS = "aws_credentials"
    AZURE_AD = "azure_ad"
    SERVICE_ACCOUNT = "service_account"


class SecretField(BaseModel):
    """Definition of a secret field required by a provider."""

    name: str = Field(description="Internal name (e.g., 'api_key')")
    display_name: str = Field(description="Human-readable name")
    description: str = Field(description="Help text for the field")
    required: bool = True
    placeholder: str = ""
    env_var_name: str = Field(description="Suggested env var name")


class ConfigField(BaseModel):
    """Definition of a non-secret configuration field."""

    name: str
    display_name: str
    description: str
    field_type: str = "text"  # text, select, number, boolean
    required: bool = False
    default: Any = None
    options: list[str] | None = None  # For select fields
    placeholder: str = ""


class ProviderInfo(BaseModel):
    """Complete information about an LLM provider."""

    provider_type: ProviderType
    display_name: str
    description: str
    base_url: str
    docs_url: str
    api_key_url: str  # Where to get API keys
    auth_type: AuthType
    secret_fields: list[SecretField]
    config_fields: list[ConfigField] = []
    default_models: list[str]
    openai_compatible: bool = False
    setup_instructions: list[str]
    pricing_notes: str = ""


class ProviderConfig(BaseModel):
    """User's configuration for a specific provider."""

    provider_type: ProviderType
    enabled: bool = False
    base_url: str | None = None  # Override default
    default_model: str | None = None
    extra_config: dict[str, Any] = {}
    # Secrets are stored separately via SecretsService


class ProviderStatus(BaseModel):
    """Status of a configured provider."""

    provider_type: ProviderType
    display_name: str
    enabled: bool
    configured: bool  # Has required secrets
    last_health_check: str | None = None
    health_status: str = "unknown"  # healthy, unhealthy, unknown
    models_available: int = 0


# =============================================================================
# Provider Definitions - Based on docs/llm-api-providers-reference.md
# =============================================================================

PROVIDER_REGISTRY: dict[ProviderType, ProviderInfo] = {
    ProviderType.OPENROUTER: ProviderInfo(
        provider_type=ProviderType.OPENROUTER,
        display_name="OpenRouter",
        description="Unified gateway to 400+ models from all major providers",
        base_url="https://openrouter.ai/api/v1",
        docs_url="https://openrouter.ai/docs",
        api_key_url="https://openrouter.ai/keys",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your OpenRouter API key (starts with sk-or-v1-)",
                placeholder="sk-or-v1-...",
                env_var_name="OPENROUTER_API_KEY",
            ),
        ],
        config_fields=[
            ConfigField(
                name="site_url",
                display_name="Site URL",
                description="Your app URL for leaderboard attribution",
                default="https://barnabeenet.local",
            ),
            ConfigField(
                name="site_name",
                display_name="Site Name",
                description="Your app name for leaderboard attribution",
                default="BarnabeeNet",
            ),
        ],
        default_models=[
            "anthropic/claude-sonnet-4-5",
            "openai/gpt-4o",
            "deepseek/deepseek-chat",
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://openrouter.ai and sign in",
            "2. Navigate to https://openrouter.ai/keys",
            "3. Click 'Create Key' and copy the key (starts with sk-or-v1-)",
            "4. Paste the key below",
            "5. OpenRouter provides unified access to all providers with single billing",
        ],
        pricing_notes="Pass-through pricing from underlying providers. Free tier available.",
    ),
    ProviderType.OPENAI: ProviderInfo(
        provider_type=ProviderType.OPENAI,
        display_name="OpenAI",
        description="GPT-5.x series with reasoning capabilities",
        base_url="https://api.openai.com/v1",
        docs_url="https://platform.openai.com/docs",
        api_key_url="https://platform.openai.com/api-keys",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your OpenAI API key (starts with sk-)",
                placeholder="sk-...",
                env_var_name="OPENAI_API_KEY",
            ),
        ],
        config_fields=[
            ConfigField(
                name="organization",
                display_name="Organization ID",
                description="Optional organization ID for billing",
                required=False,
                placeholder="org-...",
            ),
            ConfigField(
                name="project",
                display_name="Project ID",
                description="Optional project ID for project-level billing",
                required=False,
                placeholder="proj-...",
            ),
        ],
        default_models=[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "o1-preview",
            "o1-mini",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://platform.openai.com and sign in",
            "2. Navigate to https://platform.openai.com/api-keys",
            "3. Click 'Create new secret key'",
            "4. Copy the key (starts with sk-) - you won't see it again!",
            "5. Paste the key below",
        ],
        pricing_notes="Pay-per-token. GPT-4o: $2.50/$10 per 1M tokens (input/output).",
    ),
    ProviderType.ANTHROPIC: ProviderInfo(
        provider_type=ProviderType.ANTHROPIC,
        display_name="Anthropic Claude",
        description="Claude 4.5 family with extended thinking capabilities",
        base_url="https://api.anthropic.com/v1",
        docs_url="https://docs.anthropic.com",
        api_key_url="https://console.anthropic.com/settings/keys",
        auth_type=AuthType.API_KEY,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your Anthropic API key (starts with sk-ant-)",
                placeholder="sk-ant-...",
                env_var_name="ANTHROPIC_API_KEY",
            ),
        ],
        default_models=[
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
        openai_compatible=False,
        setup_instructions=[
            "1. Go to https://console.anthropic.com and sign in",
            "2. Navigate to https://console.anthropic.com/settings/keys",
            "3. Click 'Create Key'",
            "4. Copy the key (starts with sk-ant-)",
            "5. Paste the key below",
        ],
        pricing_notes="Claude Sonnet: $3/$15 per 1M tokens. Opus: $15/$75 per 1M tokens.",
    ),
    ProviderType.AZURE: ProviderInfo(
        provider_type=ProviderType.AZURE,
        display_name="Azure OpenAI",
        description="OpenAI models with enterprise Azure security",
        base_url="https://{resource}.openai.azure.com/openai/v1",
        docs_url="https://learn.microsoft.com/azure/ai-services/openai/",
        api_key_url="https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub",
        auth_type=AuthType.API_KEY,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your Azure OpenAI API key",
                placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                env_var_name="AZURE_OPENAI_API_KEY",
            ),
        ],
        config_fields=[
            ConfigField(
                name="resource_name",
                display_name="Resource Name",
                description="Your Azure OpenAI resource name",
                required=True,
                placeholder="my-openai-resource",
            ),
            ConfigField(
                name="api_version",
                display_name="API Version",
                description="Azure API version",
                default="2024-10-21",
            ),
        ],
        default_models=[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to Azure Portal and create an Azure OpenAI resource",
            "2. Navigate to your resource → Keys and Endpoint",
            "3. Copy Key 1 or Key 2",
            "4. Note your resource name from the endpoint URL",
            "5. Enter both below",
        ],
        pricing_notes="Same as OpenAI pricing. Enterprise agreements may apply.",
    ),
    ProviderType.GOOGLE: ProviderInfo(
        provider_type=ProviderType.GOOGLE,
        display_name="Google Gemini",
        description="Gemini models with native multimodal and 2M context",
        base_url="https://generativelanguage.googleapis.com/v1",
        docs_url="https://ai.google.dev/docs",
        api_key_url="https://aistudio.google.com/apikey",
        auth_type=AuthType.API_KEY,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your Google AI Studio API key",
                placeholder="AIza...",
                env_var_name="GOOGLE_API_KEY",
            ),
        ],
        default_models=[
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ],
        openai_compatible=False,
        setup_instructions=[
            "1. Go to https://aistudio.google.com",
            "2. Click 'Get API Key' in the left sidebar",
            "3. Create a new API key or use existing",
            "4. Copy the key (starts with AIza)",
            "5. Paste the key below",
        ],
        pricing_notes="Gemini Flash: Free tier available. Pro: $1.25/$5 per 1M tokens.",
    ),
    ProviderType.XAI: ProviderInfo(
        provider_type=ProviderType.XAI,
        display_name="xAI (Grok)",
        description="Grok models with real-time X/Twitter integration",
        base_url="https://api.x.ai/v1",
        docs_url="https://docs.x.ai",
        api_key_url="https://console.x.ai",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your xAI API key (starts with xai-)",
                placeholder="xai-...",
                env_var_name="XAI_API_KEY",
            ),
        ],
        default_models=[
            "grok-2",
            "grok-2-mini",
            "grok-beta",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://console.x.ai",
            "2. Sign in with your X account",
            "3. Create a new API key",
            "4. Copy the key (starts with xai-)",
            "5. Paste the key below",
        ],
        pricing_notes="Grok-2: $2/$10 per 1M tokens. Includes X search capabilities.",
    ),
    ProviderType.DEEPSEEK: ProviderInfo(
        provider_type=ProviderType.DEEPSEEK,
        display_name="DeepSeek",
        description="Cost-effective reasoning models with R1 thinking",
        base_url="https://api.deepseek.com",
        docs_url="https://platform.deepseek.com/docs",
        api_key_url="https://platform.deepseek.com/api_keys",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your DeepSeek API key (starts with sk-)",
                placeholder="sk-...",
                env_var_name="DEEPSEEK_API_KEY",
            ),
        ],
        default_models=[
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://platform.deepseek.com",
            "2. Sign in and navigate to API Keys",
            "3. Create a new API key",
            "4. Copy the key",
            "5. Paste the key below",
        ],
        pricing_notes="Very cost-effective: $0.14/$0.28 per 1M tokens. R1: $0.55/$2.19.",
    ),
    ProviderType.HUGGINGFACE: ProviderInfo(
        provider_type=ProviderType.HUGGINGFACE,
        display_name="Hugging Face",
        description="Access to 800K+ open models via Inference API",
        base_url="https://api-inference.huggingface.co",
        docs_url="https://huggingface.co/docs/api-inference",
        api_key_url="https://huggingface.co/settings/tokens",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="Access Token",
                description="Your Hugging Face access token (starts with hf_)",
                placeholder="hf_...",
                env_var_name="HF_TOKEN",
            ),
        ],
        default_models=[
            "meta-llama/Llama-3.3-70B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "microsoft/Phi-3-mini-4k-instruct",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://huggingface.co/settings/tokens",
            "2. Click 'New token'",
            "3. Give it a name and select 'Read' access (or 'Write' for endpoints)",
            "4. Copy the token (starts with hf_)",
            "5. Paste the token below",
        ],
        pricing_notes="Free tier with rate limits. Pro: $9/month for higher limits.",
    ),
    ProviderType.BEDROCK: ProviderInfo(
        provider_type=ProviderType.BEDROCK,
        display_name="AWS Bedrock",
        description="Multi-provider access with AWS security",
        base_url="https://bedrock-runtime.{region}.amazonaws.com",
        docs_url="https://docs.aws.amazon.com/bedrock/",
        api_key_url="https://console.aws.amazon.com/iam/home#/security_credentials",
        auth_type=AuthType.AWS_CREDENTIALS,
        secret_fields=[
            SecretField(
                name="access_key_id",
                display_name="AWS Access Key ID",
                description="Your AWS access key ID",
                placeholder="AKIA...",
                env_var_name="AWS_ACCESS_KEY_ID",
            ),
            SecretField(
                name="secret_access_key",
                display_name="AWS Secret Access Key",
                description="Your AWS secret access key",
                placeholder="...",
                env_var_name="AWS_SECRET_ACCESS_KEY",
            ),
        ],
        config_fields=[
            ConfigField(
                name="region",
                display_name="AWS Region",
                description="AWS region for Bedrock",
                default="us-west-2",
                field_type="select",
                options=["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"],
            ),
        ],
        default_models=[
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "meta.llama3-70b-instruct-v1:0",
        ],
        openai_compatible=False,
        setup_instructions=[
            "1. Go to AWS Console → IAM → Security Credentials",
            "2. Create Access Keys or use existing",
            "3. Ensure your IAM user/role has Bedrock permissions",
            "4. Enable desired models in Bedrock console",
            "5. Enter credentials and region below",
        ],
        pricing_notes="Same as provider pricing. On-demand or provisioned throughput.",
    ),
    ProviderType.TOGETHER: ProviderInfo(
        provider_type=ProviderType.TOGETHER,
        display_name="Together AI",
        description="200+ open-source models with fast inference",
        base_url="https://api.together.xyz/v1",
        docs_url="https://docs.together.ai",
        api_key_url="https://api.together.xyz/settings/api-keys",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your Together AI API key",
                placeholder="...",
                env_var_name="TOGETHER_API_KEY",
            ),
        ],
        default_models=[
            "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "mistralai/Mixtral-8x22B-Instruct-v0.1",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://api.together.xyz",
            "2. Sign in and go to Settings → API Keys",
            "3. Create a new API key",
            "4. Copy the key",
            "5. Paste the key below",
        ],
        pricing_notes="Competitive pricing. Llama 70B: ~$0.90 per 1M tokens.",
    ),
    ProviderType.MISTRAL: ProviderInfo(
        provider_type=ProviderType.MISTRAL,
        display_name="Mistral AI",
        description="European AI with strong open-weight models",
        base_url="https://api.mistral.ai/v1",
        docs_url="https://docs.mistral.ai",
        api_key_url="https://console.mistral.ai/api-keys/",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your Mistral AI API key",
                placeholder="...",
                env_var_name="MISTRAL_API_KEY",
            ),
        ],
        default_models=[
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "codestral-latest",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://console.mistral.ai",
            "2. Navigate to API Keys",
            "3. Create a new API key",
            "4. Copy the key",
            "5. Paste the key below",
        ],
        pricing_notes="Mistral Large: $2/$6 per 1M tokens. Codestral: $0.2/$0.6.",
    ),
    ProviderType.GROQ: ProviderInfo(
        provider_type=ProviderType.GROQ,
        display_name="Groq",
        description="Ultra-fast LPU inference (300-1000+ tokens/sec)",
        base_url="https://api.groq.com/openai/v1",
        docs_url="https://console.groq.com/docs",
        api_key_url="https://console.groq.com/keys",
        auth_type=AuthType.BEARER_TOKEN,
        secret_fields=[
            SecretField(
                name="api_key",
                display_name="API Key",
                description="Your Groq API key (starts with gsk_)",
                placeholder="gsk_...",
                env_var_name="GROQ_API_KEY",
            ),
        ],
        default_models=[
            "llama-3.3-70b-versatile",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
        openai_compatible=True,
        setup_instructions=[
            "1. Go to https://console.groq.com",
            "2. Navigate to API Keys",
            "3. Create a new API key",
            "4. Copy the key (starts with gsk_)",
            "5. Paste the key below",
        ],
        pricing_notes="Generous free tier. Very fast inference on LPU hardware.",
    ),
}


def get_provider_info(provider_type: ProviderType) -> ProviderInfo:
    """Get provider information by type."""
    return PROVIDER_REGISTRY[provider_type]


def get_all_providers() -> list[ProviderInfo]:
    """Get all provider definitions."""
    return list(PROVIDER_REGISTRY.values())
