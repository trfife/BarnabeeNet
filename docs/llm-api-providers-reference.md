# LLM API Providers Reference Guide

A comprehensive reference for building a multi-provider LLM agent system. This document covers API specifications, authentication methods, endpoints, and key features for each major provider.

---

## Table of Contents

1. [OpenRouter](#openrouter) - Unified gateway to 400+ models
2. [OpenAI](#openai) - GPT-5.x series and reasoning models
3. [Anthropic Claude](#anthropic-claude) - Claude 4.5 family
4. [Azure OpenAI Service](#azure-openai-service) - Enterprise Microsoft integration
5. [Google Gemini](#google-gemini) - Gemini API and Vertex AI
6. [xAI (Grok)](#xai-grok) - Grok 3/4 models
7. [DeepSeek](#deepseek) - DeepSeek-V3 and R1 reasoning models
8. [Hugging Face](#hugging-face) - Inference API and Endpoints
9. [AWS Bedrock](#aws-bedrock) - Multi-model AWS service
10. [Together AI](#together-ai) - Open-source model hosting
11. [Mistral AI](#mistral-ai) - Mistral and Codestral models
12. [Groq](#groq) - Ultra-fast LPU inference
13. [Implementation Architecture](#implementation-architecture)

---

## OpenRouter

**The unified API gateway** - Access 400+ models from all major providers through a single endpoint.

### Base Configuration

```python
BASE_URL = "https://openrouter.ai/api/v1"
AUTH_HEADER = "Authorization: Bearer {OPENROUTER_API_KEY}"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Main inference endpoint (OpenAI-compatible) |
| `/api/v1/models` | GET | List all available models |
| `/api/v1/models/:author/:slug/endpoints` | GET | List endpoints for specific model |
| `/api/v1/generation` | GET | Get generation stats (tokens, cost) |
| `/api/v1/auth/key` | GET | Get current API key info |

### Authentication

```python
import openai

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-or-v1-xxxx"  # OpenRouter API key
)

# Optional headers for app attribution
headers = {
    "HTTP-Referer": "https://your-app.com",  # For leaderboards
    "X-Title": "Your App Name"
}
```

### Model Selection

```python
# Direct model specification
response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4-5",
    messages=[{"role": "user", "content": "Hello"}]
)

# Model variants (append to model name)
# :free     - Free tier with rate limits
# :extended - Longer context window
# :nitro    - Optimized for throughput
# :floor    - Lowest cost option
# :online   - Web search enabled
# :thinking - Reasoning mode enabled
```

### Provider Routing

```python
# Let OpenRouter choose optimal provider
response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4-5:fastest",  # Route to fastest
    # or :cheapest for most cost-effective
    messages=[...]
)

# Specify provider preferences
headers = {
    "X-Provider-Preferences": '{"order": ["anthropic", "aws-bedrock"]}'
}
```

### BYOK (Bring Your Own Key)

```python
# Use your own provider API keys
headers = {
    "X-Provider-Auth": json.dumps({
        "anthropic": {"api_key": "sk-ant-xxx"},
        "openai": {"api_key": "sk-xxx"}
    })
}
```

### Key Features
- **Unified billing** across all providers
- **Automatic fallbacks** when providers are unavailable
- **Consistent API format** (OpenAI-compatible)
- **Pass-through pricing** (same as direct provider costs)
- **BYOK support** with 5% fee after 1M requests/month

---

## OpenAI

**The industry standard** - GPT-5.x series with reasoning capabilities.

### Base Configuration

```python
BASE_URL = "https://api.openai.com/v1"
AUTH_HEADER = "Authorization: Bearer {OPENAI_API_KEY}"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Chat completion (legacy) |
| `/responses` | POST | New Responses API (stateful) |
| `/models` | GET | List available models |
| `/embeddings` | POST | Generate embeddings |
| `/images/generations` | POST | DALL-E image generation |
| `/audio/transcriptions` | POST | Whisper transcription |

### Current Models (Late 2025)

| Model ID | Context | Use Case |
|----------|---------|----------|
| `gpt-5.2` | 400K | Latest flagship, best for complex tasks |
| `gpt-5.2-codex` | 400K | Optimized for agentic coding |
| `gpt-5.1` | 128K | Previous flagship |
| `gpt-5.1-codex` | 400K | Agentic coding |
| `gpt-5-mini` | 400K | Cost-effective alternative |
| `gpt-5-nano` | 400K | Fastest, most economical |
| `o3` | 200K | Reasoning model |
| `o4-mini` | 200K | Efficient reasoning |

### Authentication

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    organization="org-xxx",  # Optional
    project="proj-xxx"       # Optional - for project-level billing
)
```

### Chat Completions (Legacy)

```python
response = client.chat.completions.create(
    model="gpt-5.2",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    temperature=0.7,
    max_tokens=1000
)
```

### Responses API (New - Recommended)

```python
# Stateful conversation management
response = client.responses.create(
    model="gpt-5.2",
    input="What is the weather in San Francisco?",
    reasoning={"effort": "medium"}  # none, low, medium, high
)

# With tools
response = client.responses.create(
    model="gpt-5.2",
    input=[{"role": "user", "content": "Search the web for..."}],
    tools=[{"type": "web_search"}]
)
```

### Reasoning Effort

```python
# Control reasoning depth (GPT-5.2)
response = client.responses.create(
    model="gpt-5.2",
    input="Solve this complex problem...",
    reasoning={
        "effort": "high"  # none (default), low, medium, high
    }
)
```

### Key Features
- **Reasoning modes** with configurable effort levels
- **Built-in tools**: web_search, code_interpreter, computer_use
- **Function calling** for custom tool integration
- **Structured outputs** with JSON mode
- **Batch API** for 50% cost reduction on async workloads

---

## Anthropic Claude

**Advanced reasoning and safety** - Claude 4.5 family with extended thinking.

### Base Configuration

```python
BASE_URL = "https://api.anthropic.com/v1"
AUTH_HEADER = "X-Api-Key: {ANTHROPIC_API_KEY}"
VERSION_HEADER = "anthropic-version: 2023-06-01"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/messages` | POST | Main chat completion |
| `/messages/batches` | POST | Batch processing |
| `/models` | GET | List available models |
| `/files` | POST | Upload files (beta) |

### Current Models

| Model ID | Context | Best For |
|----------|---------|----------|
| `claude-opus-4-5-20250929` | 200K | Most intelligent, complex reasoning |
| `claude-sonnet-4-5-20250929` | 200K (1M beta) | Best balance of speed/intelligence |
| `claude-haiku-4-5-20251001` | 200K | Fast, cost-effective |

### Authentication

```python
from anthropic import Anthropic

client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)
```

### Basic Request

```python
message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain quantum computing"}
    ]
)
```

### Extended Thinking

```python
# Enable extended thinking for complex reasoning
message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # Tokens for internal reasoning
    },
    messages=[{"role": "user", "content": "Solve this complex problem..."}]
)
```

### Tool Use

```python
message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    tools=[
        {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    ],
    messages=[{"role": "user", "content": "What's the weather in NYC?"}]
)
```

### Beta Features (Require Headers)

```python
# Enable beta features via anthropic-beta header
headers = {
    "anthropic-beta": "prompt-caching-2024-07-31,computer-use-2025-01-24"
}

# Available betas:
# - prompt-caching-2024-07-31: Cache system prompts
# - computer-use-2025-01-24: Computer use tool
# - pdfs-2024-09-25: PDF processing
# - output-128k-2025-02-19: Extended output
# - context-1m-2025-08-07: 1M context (Sonnet 4.5)
```

### Key Features
- **Extended thinking** for complex reasoning
- **Prompt caching** for cost reduction (90% savings on cache hits)
- **Vision support** for image analysis
- **PDF processing** (beta)
- **Computer use** tool for automation
- **Citations** for source attribution

---

## Azure OpenAI Service

**Enterprise Microsoft integration** - OpenAI models with Azure security.

### Base Configuration

```python
# New v1 API (August 2025+)
BASE_URL = "https://{resource-name}.openai.azure.com/openai/v1"

# Legacy API (still supported)
BASE_URL = "https://{resource-name}.openai.azure.com/openai/deployments/{deployment-id}"
API_VERSION = "2024-10-21"  # or latest preview
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Chat completion |
| `/completions` | POST | Text completion |
| `/embeddings` | POST | Generate embeddings |
| `/models` | GET | List deployed models |

### Authentication Methods

**Option 1: API Key**
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-resource.openai.azure.com/openai/v1/",
    api_key=os.environ["AZURE_OPENAI_API_KEY"]
)
```

**Option 2: Microsoft Entra ID (Recommended for Enterprise)**
```python
from azure.identity import DefaultAzureCredential
from openai import OpenAI

credential = DefaultAzureCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default")

client = OpenAI(
    base_url="https://your-resource.openai.azure.com/openai/v1/",
    api_key=token.token
)
```

**Option 3: Managed Identity**
```python
from azure.identity import ManagedIdentityCredential

credential = ManagedIdentityCredential()
# Use with Azure-hosted applications
```

### v1 API Usage (New)

```python
# v1 API - no api-version parameter needed
client = OpenAI(
    base_url="https://your-resource.openai.azure.com/openai/v1/",
    api_key=os.environ["AZURE_OPENAI_API_KEY"]
)

response = client.chat.completions.create(
    model="gpt-5.2",  # Your deployment name
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Legacy API Usage

```python
# Legacy API requires api-version
import requests

response = requests.post(
    f"https://your-resource.openai.azure.com/openai/deployments/{deployment}/chat/completions",
    params={"api-version": "2024-10-21"},
    headers={"api-key": api_key},
    json={"messages": [{"role": "user", "content": "Hello"}]}
)
```

### Key Features
- **Enterprise security** with Azure AD integration
- **Regional deployment** for data residency
- **Private endpoints** via VNet
- **Content filtering** built-in
- **On Your Data** - RAG with Azure AI Search

---

## Google Gemini

**Multimodal AI** - Native vision, video, and long context.

### Base Configuration

```python
# Google AI Studio (Direct)
BASE_URL = "https://generativelanguage.googleapis.com/v1"
AUTH_HEADER = "x-goog-api-key: {GOOGLE_API_KEY}"

# Vertex AI (Enterprise)
BASE_URL = "https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/endpoints/openapi"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/models/{model}:generateContent` | POST | Standard generation |
| `/models/{model}:streamGenerateContent` | POST | Streaming (SSE) |
| `/models/{model}:batchGenerateContent` | POST | Batch processing |
| `/models/{model}:embedContent` | POST | Generate embeddings |

### Current Models

| Model ID | Context | Features |
|----------|---------|----------|
| `gemini-2.5-pro` | 2M | Most capable, thinking |
| `gemini-2.5-flash` | 1M | Fast, multimodal |
| `gemini-2.0-flash` | 1M | Production workhorse |

### Authentication

**Google AI Studio (API Key)**
```python
import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")
```

**Vertex AI (Service Account)**
```python
from google.auth import default
from openai import OpenAI

credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
credentials.refresh(google.auth.transport.requests.Request())

client = OpenAI(
    base_url=f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/endpoints/openapi",
    api_key=credentials.token
)
```

### Basic Request

```python
# Using Google AI SDK
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Explain quantum computing")

# Using REST/OpenAI-compatible
response = client.chat.completions.create(
    model="google/gemini-2.0-flash-001",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Multimodal Input

```python
import PIL.Image

model = genai.GenerativeModel("gemini-2.5-flash")
image = PIL.Image.open("image.jpg")
response = model.generate_content(["Describe this image:", image])
```

### Key Features
- **2M token context** for massive documents
- **Native multimodal** (text, images, video, audio)
- **Thinking mode** for complex reasoning
- **Code execution** built-in
- **Grounding** with Google Search

---

## xAI (Grok)

**Real-time knowledge** - Deep X/Twitter integration.

### Base Configuration

```python
BASE_URL = "https://api.x.ai/v1"
AUTH_HEADER = "Authorization: Bearer {XAI_API_KEY}"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Chat completion (OpenAI-compatible) |
| `/responses` | POST | Responses API with agent tools |
| `/models` | GET | List available models |
| `/realtime/client_secrets` | POST | Get ephemeral token for WebSocket |
| `/images/generations` | POST | Image generation |

### Current Models

| Model ID | Context | Features |
|----------|---------|----------|
| `grok-4` | 128K | Latest flagship |
| `grok-4-1-fast-reasoning` | 2M | Agentic with reasoning |
| `grok-4-1-fast-non-reasoning` | 2M | Fast responses |
| `grok-3-mini-beta` | 128K | Cost-effective |
| `grok-code-fast-1` | 256K | Optimized for coding |

### Authentication

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.x.ai/v1",
    api_key=os.environ["XAI_API_KEY"]  # Keys start with "xai-"
)
```

### Basic Request

```python
response = client.chat.completions.create(
    model="grok-4",
    messages=[
        {"role": "user", "content": "What's trending on X today?"}
    ]
)
```

### Agent Tools (Server-Side)

```python
# Using Responses API with built-in tools
response = client.responses.create(
    model="grok-4-1-fast-reasoning",
    input=[{"role": "user", "content": "Search for recent AI news"}],
    tools=[
        {"type": "web_search"},
        {"type": "x_search", "from_date": "2025-01-01"}
    ]
)
```

### Live Search (Deprecating Dec 2025)

```python
# Note: Migrating to Agent Tools API
response = client.chat.completions.create(
    model="grok-4",
    messages=[...],
    search_parameters={
        "mode": "auto",
        "sources": [{"type": "web"}, {"type": "x"}]
    }
)
```

### Key Features
- **X/Twitter integration** for real-time social data
- **Web search** built-in
- **Image generation** with Aurora model
- **Voice API** (WebSocket) for real-time audio
- **File upload** and collections search

---

## DeepSeek

**Cost-effective reasoning** - Open-weight models with strong performance.

### Base Configuration

```python
BASE_URL = "https://api.deepseek.com"
# Also: https://api.deepseek.com/v1 (OpenAI-compatible)
AUTH_HEADER = "Authorization: Bearer {DEEPSEEK_API_KEY}"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Chat completion |
| `/v1/chat/completions` | POST | OpenAI-compatible |
| `/v1/models` | GET | List models |

### Current Models

| Model ID | Context | Description |
|----------|---------|-------------|
| `deepseek-chat` | 64K | DeepSeek-V3.2 non-thinking mode |
| `deepseek-reasoner` | 64K | DeepSeek-V3.2 thinking mode (R1) |
| `deepseek-coder` | 16K | Code-optimized |

### Authentication

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=os.environ["DEEPSEEK_API_KEY"]
)
```

### Basic Request

```python
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    stream=False
)
```

### Reasoning Model

```python
# DeepSeek-R1 reasoning mode
response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[
        {"role": "user", "content": "Solve this step by step: ..."}
    ]
)
# Reasoning appears in <reasoning> tags before response
```

### Key Features
- **OpenAI-compatible** API format
- **Strong reasoning** with R1 model
- **Very cost-effective** pricing
- **Open weights** available on Hugging Face
- **No hard rate limits** (usage-based)

---

## Hugging Face

**Open model ecosystem** - Access to 800K+ models.

### Inference Options

| Service | Description | Pricing |
|---------|-------------|---------|
| **Inference API** | Serverless, free tier | Pay-per-token |
| **Inference Endpoints** | Dedicated GPUs | Per-hour billing |
| **Inference Providers** | Third-party routing | Provider pricing |

### Base Configuration

```python
# Inference API
BASE_URL = "https://api-inference.huggingface.co/models/{model_id}"

# Inference Providers (OpenAI-compatible)
BASE_URL = "https://router.huggingface.co/v1"

AUTH_HEADER = "Authorization: Bearer {HF_TOKEN}"
```

### Authentication

```python
from huggingface_hub import InferenceClient

# Using InferenceClient
client = InferenceClient(token=os.environ["HF_TOKEN"])

# Or with OpenAI SDK
from openai import OpenAI
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"]
)
```

### Inference API

```python
client = InferenceClient()

# Chat completion
response = client.chat_completion(
    model="meta-llama/Llama-3.3-70B-Instruct",
    messages=[{"role": "user", "content": "Hello!"}],
    max_tokens=500
)

# Text generation
response = client.text_generation(
    model="bigscience/bloom",
    prompt="The capital of France is",
    max_new_tokens=50
)
```

### Inference Providers

```python
# Route through providers (e.g., Replicate, Together, etc.)
client = InferenceClient(provider="replicate")
response = client.text_to_image(
    "A futuristic cityscape",
    model="black-forest-labs/FLUX.1-schnell"
)
```

### Dedicated Endpoints

```python
from huggingface_hub import InferenceEndpoint

# Create dedicated endpoint
endpoint = InferenceEndpoint.create(
    name="my-llama-endpoint",
    repository="meta-llama/Llama-3.3-70B-Instruct",
    framework="text-generation-inference",
    instance_size="x4",
    instance_type="nvidia-a100"
)

# Use endpoint
response = endpoint.client.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Key Features
- **800K+ models** available
- **Multiple providers** (HF, Replicate, Together, etc.)
- **Automatic failover** with provider="auto"
- **Dedicated endpoints** for production
- **OpenAI-compatible** interface

---

## AWS Bedrock

**AWS-native AI** - Multiple providers with AWS security.

### Base Configuration

```python
# Control Plane
BEDROCK_URL = "https://bedrock.{region}.amazonaws.com"

# Runtime (Inference)
RUNTIME_URL = "https://bedrock-runtime.{region}.amazonaws.com"

# OpenAI-compatible (Mantle)
MANTLE_URL = "https://bedrock-mantle.{region}.api.aws/v1"
```

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `bedrock:ListFoundationModels` | List available models |
| `bedrock-runtime:InvokeModel` | Single inference |
| `bedrock-runtime:InvokeModelWithResponseStream` | Streaming inference |
| `bedrock-runtime:Converse` | Unified chat API |

### Available Model Providers

| Provider | Notable Models |
|----------|---------------|
| Anthropic | Claude Sonnet 4.5, Claude Opus 4.5 |
| Meta | Llama 3.3, Llama 4 |
| Amazon | Titan Text, Titan Embeddings |
| Mistral | Mistral Large, Codestral |
| Cohere | Command R+ |
| AI21 | Jamba |
| OpenAI | GPT-OSS models |

### Authentication

**AWS Credentials**
```python
import boto3

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"]
)
```

**Bedrock API Key (New)**
```python
from openai import OpenAI

# Generate API key in Bedrock console
client = OpenAI(
    base_url="https://bedrock-mantle.us-west-2.api.aws/v1",
    api_key=os.environ["AWS_BEARER_TOKEN_BEDROCK"]
)
```

### Converse API (Unified)

```python
response = bedrock.converse(
    modelId="anthropic.claude-sonnet-4-5-20250929-v1:0",
    messages=[
        {"role": "user", "content": [{"text": "Hello!"}]}
    ]
)
```

### InvokeModel (Direct)

```python
import json

response = bedrock.invoke_model(
    modelId="anthropic.claude-sonnet-4-5-20250929-v1:0",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": "Hello!"}]
    })
)
```

### OpenAI-Compatible (Mantle)

```python
client = OpenAI(
    base_url="https://bedrock-mantle.us-west-2.api.aws/v1",
    api_key=os.environ["AWS_BEARER_TOKEN_BEDROCK"]
)

response = client.chat.completions.create(
    model="openai.gpt-oss-120b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Key Features
- **Multi-model access** in one service
- **AWS security** (IAM, VPC, encryption)
- **Guardrails** for content filtering
- **Knowledge Bases** for RAG
- **Agents** for autonomous workflows

---

## Together AI

**Open-source hosting** - 200+ models with fast inference.

### Base Configuration

```python
BASE_URL = "https://api.together.xyz/v1"
AUTH_HEADER = "Authorization: Bearer {TOGETHER_API_KEY}"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Chat completion |
| `/completions` | POST | Text completion |
| `/embeddings` | POST | Generate embeddings |
| `/images/generations` | POST | Image generation |
| `/models` | GET | List models |

### Authentication

```python
from together import Together

client = Together(api_key=os.environ["TOGETHER_API_KEY"])

# Or OpenAI-compatible
from openai import OpenAI
client = OpenAI(
    base_url="https://api.together.xyz/v1",
    api_key=os.environ["TOGETHER_API_KEY"]
)
```

### Basic Request

```python
response = client.chat.completions.create(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    messages=[
        {"role": "user", "content": "What are the top 3 things to do in NYC?"}
    ]
)
```

### Popular Models

| Model | Context | Best For |
|-------|---------|----------|
| `meta-llama/Llama-4-Scout-Instruct` | 10M | Latest Llama |
| `deepseek-ai/DeepSeek-R1` | 64K | Reasoning |
| `Qwen/Qwen2.5-72B-Instruct-Turbo` | 128K | Multilingual |
| `mistralai/Mixtral-8x22B-Instruct-v0.1` | 65K | Quality |
| `meta-llama/Llama-Vision-Free` | 128K | Vision (free) |

### Key Features
- **OpenAI-compatible** API
- **200+ models** including latest open-source
- **Dedicated endpoints** for production
- **Fine-tuning** support
- **Competitive pricing**

---

## Mistral AI

**European AI leader** - Strong open-weight and API models.

### Base Configuration

```python
BASE_URL = "https://api.mistral.ai/v1"
AUTH_HEADER = "Authorization: Bearer {MISTRAL_API_KEY}"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Chat completion |
| `/embeddings` | POST | Generate embeddings |
| `/models` | GET | List models |
| `/fim/completions` | POST | Fill-in-middle (Codestral) |

### Current Models

| Model ID | Context | Best For |
|----------|---------|----------|
| `mistral-large-latest` | 128K | Complex tasks |
| `mistral-medium-latest` | 32K | Balanced performance |
| `mistral-small-latest` | 32K | Cost-effective |
| `codestral-latest` | 32K | Code generation |
| `magistral-medium-2506` | 32K | Reasoning |

### Authentication

```python
from mistralai import Mistral

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
```

### Basic Request

```python
response = client.chat.complete(
    model="mistral-large-latest",
    messages=[
        {"role": "user", "content": "What is the best French cheese?"}
    ]
)
```

### Codestral (Code Generation)

```python
# Fill-in-middle for code completion
response = client.fim.complete(
    model="codestral-latest",
    prompt="def fibonacci(n):",
    suffix="\n    return result"
)
```

### Key Features
- **Strong open models** (Mixtral, Mistral)
- **Codestral** for code generation
- **Function calling** support
- **Guardrails** API
- **Fine-tuning** available

---

## Groq

**Ultra-fast inference** - LPU hardware for blazing speed.

### Base Configuration

```python
BASE_URL = "https://api.groq.com/openai/v1"
AUTH_HEADER = "Authorization: Bearer {GROQ_API_KEY}"
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Chat completion |
| `/responses` | POST | Responses API with tools |
| `/models` | GET | List models |
| `/audio/transcriptions` | POST | Whisper transcription |

### Available Models

| Model | Context | Speed |
|-------|---------|-------|
| `llama-3.3-70b-versatile` | 128K | Very fast |
| `llama-4-maverick-17b-128e-instruct` | 128K | Ultra fast |
| `deepseek-r1-distill-llama-70b` | 128K | Reasoning |
| `mixtral-8x7b-32768` | 32K | Fast |
| `openai/gpt-oss-20b` | 128K | Browser search |
| `openai/gpt-oss-120b` | 128K | Most capable |

### Authentication

```python
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Or OpenAI-compatible
from openai import OpenAI
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"]
)
```

### Basic Request

```python
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": "Explain quantum computing"}
    ]
)
```

### Built-in Tools

```python
# Server-side tool execution
response = client.responses.create(
    model="openai/gpt-oss-20b",
    input="Search the web for latest AI news",
    tools=[
        {"type": "web_search"},
        {"type": "code_execution"}
    ]
)
```

### Key Features
- **300-1000+ tokens/sec** inference speed
- **OpenAI-compatible** API
- **Built-in tools** (web search, code execution)
- **MCP support** for external tools
- **Generous free tier**

---

## Implementation Architecture

### Unified Provider Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class ProviderType(Enum):
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

@dataclass
class ProviderConfig:
    provider_type: ProviderType
    api_key: str
    base_url: Optional[str] = None
    extra_headers: Optional[Dict[str, str]] = None
    default_model: Optional[str] = None

@dataclass
class Message:
    role: str
    content: str

@dataclass
class CompletionResponse:
    content: str
    model: str
    provider: ProviderType
    usage: Dict[str, int]
    raw_response: Any

class LLMProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._client = None
    
    @abstractmethod
    def create_completion(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> CompletionResponse:
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        pass
```

### Provider Factory

```python
class ProviderFactory:
    _providers: Dict[ProviderType, type] = {}
    
    @classmethod
    def register(cls, provider_type: ProviderType):
        def decorator(provider_class):
            cls._providers[provider_type] = provider_class
            return provider_class
        return decorator
    
    @classmethod
    def create(cls, config: ProviderConfig) -> LLMProvider:
        provider_class = cls._providers.get(config.provider_type)
        if not provider_class:
            raise ValueError(f"Unknown provider: {config.provider_type}")
        return provider_class(config)
```

### Example Provider Implementation

```python
@ProviderFactory.register(ProviderType.OPENAI)
class OpenAIProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        from openai import OpenAI
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url or "https://api.openai.com/v1"
        )
    
    def create_completion(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> CompletionResponse:
        response = self._client.chat.completions.create(
            model=model or self.config.default_model or "gpt-5.2",
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return CompletionResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider=ProviderType.OPENAI,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            raw_response=response
        )
    
    def list_models(self) -> List[str]:
        return [m.id for m in self._client.models.list()]
```

### Agent Router

```python
from typing import Callable, Dict

@dataclass
class AgentConfig:
    name: str
    provider: ProviderType
    model: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2000
    criteria: Optional[Dict[str, Any]] = None  # For model selection

class AgentRouter:
    def __init__(self):
        self._providers: Dict[ProviderType, LLMProvider] = {}
        self._agents: Dict[str, AgentConfig] = {}
    
    def add_provider(self, config: ProviderConfig):
        self._providers[config.provider_type] = ProviderFactory.create(config)
    
    def add_agent(self, agent_config: AgentConfig):
        self._agents[agent_config.name] = agent_config
    
    def run_agent(
        self,
        agent_name: str,
        user_message: str
    ) -> CompletionResponse:
        agent = self._agents.get(agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        provider = self._providers.get(agent.provider)
        if not provider:
            raise ValueError(f"Provider not configured: {agent.provider}")
        
        messages = [
            Message(role="system", content=agent.system_prompt),
            Message(role="user", content=user_message)
        ]
        
        return provider.create_completion(
            messages=messages,
            model=agent.model,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens
        )
```

### Usage Example

```python
# Initialize router
router = AgentRouter()

# Add providers
router.add_provider(ProviderConfig(
    provider_type=ProviderType.OPENAI,
    api_key=os.environ["OPENAI_API_KEY"],
    default_model="gpt-5.2"
))

router.add_provider(ProviderConfig(
    provider_type=ProviderType.ANTHROPIC,
    api_key=os.environ["ANTHROPIC_API_KEY"],
    default_model="claude-sonnet-4-5-20250929"
))

router.add_provider(ProviderConfig(
    provider_type=ProviderType.GROQ,
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1"
))

# Define agents with different providers based on criteria
router.add_agent(AgentConfig(
    name="reasoning_agent",
    provider=ProviderType.ANTHROPIC,  # Best for complex reasoning
    model="claude-sonnet-4-5-20250929",
    system_prompt="You are an expert problem solver...",
    criteria={"task": "reasoning", "quality": "high"}
))

router.add_agent(AgentConfig(
    name="fast_agent",
    provider=ProviderType.GROQ,  # Fastest inference
    model="llama-3.3-70b-versatile",
    system_prompt="You are a quick assistant...",
    criteria={"task": "simple", "speed": "critical"}
))

router.add_agent(AgentConfig(
    name="code_agent",
    provider=ProviderType.OPENAI,  # Strong coding
    model="gpt-5.2-codex",
    system_prompt="You are an expert programmer...",
    criteria={"task": "coding", "quality": "high"}
))

# Run agents
response = router.run_agent("reasoning_agent", "Solve this complex problem...")
print(response.content)
```

### Environment Variables Summary

```bash
# Required API Keys
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
AZURE_OPENAI_API_KEY=xxx
GOOGLE_API_KEY=xxx
XAI_API_KEY=xai-xxx
DEEPSEEK_API_KEY=sk-xxx
HF_TOKEN=hf_xxx
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
TOGETHER_API_KEY=xxx
MISTRAL_API_KEY=xxx
GROQ_API_KEY=gsk_xxx

# Optional Configuration
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com
AWS_REGION=us-west-2
GOOGLE_CLOUD_PROJECT=xxx
```

---

## Model Selection Criteria

| Criteria | Recommended Provider | Model |
|----------|---------------------|-------|
| **Complex reasoning** | Anthropic | Claude Opus 4.5 |
| **Fastest response** | Groq | Llama 3.3 70B |
| **Best coding** | OpenAI | GPT-5.2 Codex |
| **Cost-effective** | DeepSeek | DeepSeek-Chat |
| **Multimodal** | Google | Gemini 2.5 Pro |
| **Real-time data** | xAI | Grok 4 |
| **Enterprise security** | Azure/Bedrock | Various |
| **Open source** | Together/Groq | Llama, Mixtral |
| **Unified access** | OpenRouter | Any model |

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: January 2026
- **Compatibility**: API versions as of late 2025

---

*This document is intended as a reference for building multi-provider LLM systems. Always consult official documentation for the latest API specifications and pricing.*
