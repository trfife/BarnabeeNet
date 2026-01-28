# Area 15: API Contracts & LLM Provider Abstraction

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** Area 01 (Core Data Layer)  
**Phase:** Infrastructure  

---

## 1. Overview

### 1.1 Purpose

This specification defines the API contracts for BarnabeeNet V2 and the LLM provider abstraction layer that allows switching between Azure OpenAI, OpenRouter, Anthropic Claude, OpenAI, Grok, and Google Gemini via the dashboard without code changes.

### 1.2 Design Principles

1. **Contract-first:** OpenAPI spec is the source of truth
2. **Provider-agnostic:** LLM calls go through abstraction layer
3. **Hot-swappable:** Provider switch requires no restart
4. **Versioned:** API versions in URL path for backward compatibility
5. **Observable:** Every endpoint emits metrics and traces

---

## 2. OpenAPI Specification

### 2.1 Base Configuration

```yaml
openapi: 3.1.0
info:
  title: BarnabeeNet V2 API
  version: 2.0.0
  description: Voice assistant backend API
  contact:
    name: Thom Vincent
    
servers:
  - url: https://barnabee.local/api/v2
    description: Production
  - url: http://localhost:8000/api/v2
    description: Development

tags:
  - name: voice
    description: Voice pipeline operations
  - name: memories
    description: Memory CRUD operations
  - name: conversations
    description: Conversation management
  - name: calendar
    description: Calendar integration
  - name: email
    description: Email integration
  - name: devices
    description: Device management
  - name: admin
    description: Admin operations
  - name: health
    description: Health and status
```

### 2.2 Core Endpoints

```yaml
paths:
  # =========================================================================
  # HEALTH
  # =========================================================================
  /health:
    get:
      tags: [health]
      summary: Health check
      operationId: healthCheck
      responses:
        '200':
          description: Service healthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthStatus'
        '503':
          description: Service unhealthy

  /health/detailed:
    get:
      tags: [health]
      summary: Detailed health with all dependencies
      operationId: healthCheckDetailed
      security:
        - bearerAuth: []
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DetailedHealthStatus'

  # =========================================================================
  # VOICE
  # =========================================================================
  /voice/process:
    post:
      tags: [voice]
      summary: Process voice command (non-streaming)
      operationId: processVoiceCommand
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/VoiceCommandRequest'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VoiceCommandResponse'

  /voice/session:
    post:
      tags: [voice]
      summary: Create voice session (for WebRTC)
      operationId: createVoiceSession
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/VoiceSessionRequest'
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VoiceSession'

  /voice/wake:
    post:
      tags: [voice]
      summary: Register wake word detection for arbitration
      operationId: registerWakeWord
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/WakeWordEvent'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ArbitrationResult'

  # =========================================================================
  # MEMORIES
  # =========================================================================
  /memories:
    get:
      tags: [memories]
      summary: List memories
      operationId: listMemories
      security:
        - bearerAuth: []
      parameters:
        - name: owner
          in: query
          schema:
            type: string
        - name: type
          in: query
          schema:
            $ref: '#/components/schemas/MemoryType'
        - name: query
          in: query
          description: Full-text search query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/MemoryList'

    post:
      tags: [memories]
      summary: Create memory
      operationId: createMemory
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MemoryCreate'
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Memory'

  /memories/{id}:
    get:
      tags: [memories]
      summary: Get memory by ID
      operationId: getMemory
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Memory'
        '404':
          $ref: '#/components/responses/NotFound'

    patch:
      tags: [memories]
      summary: Update memory
      operationId: updateMemory
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MemoryUpdate'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Memory'

    delete:
      tags: [memories]
      summary: Soft delete memory
      operationId: deleteMemory
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        '204':
          description: Memory deleted

  /memories/search:
    post:
      tags: [memories]
      summary: Semantic memory search
      operationId: searchMemories
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MemorySearchRequest'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/MemorySearchResult'

  # =========================================================================
  # CONVERSATIONS
  # =========================================================================
  /conversations:
    get:
      tags: [conversations]
      summary: List conversations
      operationId: listConversations
      security:
        - bearerAuth: []
      parameters:
        - name: speaker_id
          in: query
          schema:
            type: string
        - name: mode
          in: query
          schema:
            $ref: '#/components/schemas/ConversationMode'
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConversationList'

  /conversations/{id}:
    get:
      tags: [conversations]
      summary: Get conversation with turns
      operationId: getConversation
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConversationDetail'

  # =========================================================================
  # CALENDAR
  # =========================================================================
  /calendar/events:
    get:
      tags: [calendar]
      summary: List calendar events
      operationId: listCalendarEvents
      security:
        - bearerAuth: []
      parameters:
        - name: start
          in: query
          required: true
          schema:
            type: string
            format: date-time
        - name: end
          in: query
          required: true
          schema:
            type: string
            format: date-time
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CalendarEventList'

    post:
      tags: [calendar]
      summary: Create calendar event
      operationId: createCalendarEvent
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CalendarEventCreate'
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CalendarEvent'

  # =========================================================================
  # DEVICES
  # =========================================================================
  /devices:
    get:
      tags: [devices]
      summary: List registered devices
      operationId: listDevices
      security:
        - bearerAuth: []
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeviceList'

  /devices/register:
    post:
      tags: [devices]
      summary: Register device
      operationId: registerDevice
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DeviceRegistration'
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Device'

  /devices/{id}/heartbeat:
    post:
      tags: [devices]
      summary: Device heartbeat
      operationId: deviceHeartbeat
      security:
        - bearerAuth: []
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeviceStatus'

  # =========================================================================
  # ADMIN
  # =========================================================================
  /admin/llm/providers:
    get:
      tags: [admin]
      summary: List configured LLM providers
      operationId: listLLMProviders
      security:
        - bearerAuth: []
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LLMProviderList'

  /admin/llm/active:
    get:
      tags: [admin]
      summary: Get active LLM provider
      operationId: getActiveLLMProvider
      security:
        - bearerAuth: []
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ActiveLLMProvider'

    put:
      tags: [admin]
      summary: Set active LLM provider
      operationId: setActiveLLMProvider
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SetLLMProviderRequest'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ActiveLLMProvider'

  /admin/llm/test:
    post:
      tags: [admin]
      summary: Test LLM provider connection
      operationId: testLLMProvider
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TestLLMProviderRequest'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LLMTestResult'
```

### 2.3 Schema Definitions

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    # =========================================================================
    # HEALTH
    # =========================================================================
    HealthStatus:
      type: object
      required: [status, timestamp]
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        timestamp:
          type: string
          format: date-time

    DetailedHealthStatus:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        checks:
          type: object
          additionalProperties:
            type: string
        timestamp:
          type: string
          format: date-time

    # =========================================================================
    # VOICE
    # =========================================================================
    VoiceCommandRequest:
      type: object
      required: [text, session_id]
      properties:
        text:
          type: string
          description: Transcribed user utterance
        session_id:
          type: string
        device_id:
          type: string
        speaker_id:
          type: string

    VoiceCommandResponse:
      type: object
      properties:
        text:
          type: string
          description: Response text to speak
        intent:
          type: string
        entities:
          type: object
        actions_taken:
          type: array
          items:
            type: object
        latency_ms:
          type: integer

    WakeWordEvent:
      type: object
      required: [event_id, device_id, timestamp, wake_confidence]
      properties:
        event_id:
          type: string
          format: uuid
        device_id:
          type: string
        timestamp:
          type: number
        wake_confidence:
          type: number
          minimum: 0
          maximum: 1
        audio_energy:
          type: number
        location:
          type: string

    ArbitrationResult:
      type: object
      properties:
        event_id:
          type: string
        winner_device_id:
          type: string
        reason:
          type: string
        should_respond:
          type: boolean

    # =========================================================================
    # MEMORY
    # =========================================================================
    MemoryType:
      type: string
      enum: [fact, preference, decision, event, person, project, meeting, journal]

    Memory:
      type: object
      properties:
        id:
          type: string
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
        summary:
          type: string
        content:
          type: string
        keywords:
          type: array
          items:
            type: string
        memory_type:
          $ref: '#/components/schemas/MemoryType'
        source_type:
          type: string
        owner:
          type: string
        visibility:
          type: string

    MemoryCreate:
      type: object
      required: [summary, content, memory_type, owner]
      properties:
        summary:
          type: string
          maxLength: 500
        content:
          type: string
        memory_type:
          $ref: '#/components/schemas/MemoryType'
        owner:
          type: string
        keywords:
          type: array
          items:
            type: string

    MemoryUpdate:
      type: object
      properties:
        summary:
          type: string
        content:
          type: string
        keywords:
          type: array
          items:
            type: string

    MemoryList:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/Memory'
        total:
          type: integer
        limit:
          type: integer
        offset:
          type: integer

    MemorySearchRequest:
      type: object
      required: [query]
      properties:
        query:
          type: string
        owner:
          type: string
        types:
          type: array
          items:
            $ref: '#/components/schemas/MemoryType'
        limit:
          type: integer
          default: 10

    MemorySearchResult:
      type: object
      properties:
        items:
          type: array
          items:
            type: object
            properties:
              memory:
                $ref: '#/components/schemas/Memory'
              score:
                type: number
        query:
          type: string
        total:
          type: integer

    # =========================================================================
    # LLM PROVIDERS
    # =========================================================================
    LLMProvider:
      type: string
      enum: [azure_openai, openai, anthropic, openrouter, google, xai]

    LLMProviderConfig:
      type: object
      properties:
        provider:
          $ref: '#/components/schemas/LLMProvider'
        name:
          type: string
        enabled:
          type: boolean
        models:
          type: array
          items:
            type: string
        default_model:
          type: string

    LLMProviderList:
      type: object
      properties:
        providers:
          type: array
          items:
            $ref: '#/components/schemas/LLMProviderConfig'

    ActiveLLMProvider:
      type: object
      properties:
        provider:
          $ref: '#/components/schemas/LLMProvider'
        model:
          type: string
        updated_at:
          type: string
          format: date-time

    SetLLMProviderRequest:
      type: object
      required: [provider]
      properties:
        provider:
          $ref: '#/components/schemas/LLMProvider'
        model:
          type: string

    TestLLMProviderRequest:
      type: object
      required: [provider]
      properties:
        provider:
          $ref: '#/components/schemas/LLMProvider'
        model:
          type: string

    LLMTestResult:
      type: object
      properties:
        success:
          type: boolean
        latency_ms:
          type: integer
        error:
          type: string
        response_preview:
          type: string

  responses:
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            type: object
            properties:
              error:
                type: string
              detail:
                type: string
```

---

## 3. LLM Provider Abstraction

### 3.1 Provider Configuration Schema

```sql
-- =============================================================================
-- LLM PROVIDER CONFIGURATION
-- =============================================================================

CREATE TABLE llm_providers (
    id TEXT PRIMARY KEY,                        -- azure_openai, openai, anthropic, etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- Provider info
    name TEXT NOT NULL,                         -- Display name
    enabled INTEGER NOT NULL DEFAULT 0,
    
    -- Credentials (encrypted)
    api_key_encrypted BLOB,
    api_endpoint TEXT,                          -- For Azure, custom endpoints
    
    -- Models
    available_models TEXT NOT NULL DEFAULT '[]', -- JSON array
    default_model TEXT,
    
    -- Rate limiting
    requests_per_minute INTEGER DEFAULT 60,
    tokens_per_minute INTEGER DEFAULT 100000,
    
    -- Cost tracking
    cost_per_1k_input_tokens REAL,
    cost_per_1k_output_tokens REAL
);

CREATE TABLE llm_active_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),      -- Single row table
    provider_id TEXT NOT NULL REFERENCES llm_providers(id),
    model TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by TEXT
);

-- Seed default providers
INSERT INTO llm_providers (id, name, available_models, default_model) VALUES
('azure_openai', 'Azure OpenAI', '["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]', 'gpt-4o'),
('openai', 'OpenAI', '["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-preview"]', 'gpt-4o'),
('anthropic', 'Anthropic Claude', '["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]', 'claude-3-5-sonnet-20241022'),
('openrouter', 'OpenRouter', '["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "google/gemini-pro-1.5"]', 'anthropic/claude-3.5-sonnet'),
('google', 'Google Gemini', '["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"]', 'gemini-1.5-pro'),
('xai', 'xAI Grok', '["grok-2", "grok-2-mini"]', 'grok-2');
```

### 3.2 Provider Interface

```python
# src/barnabee/llm/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional

@dataclass
class LLMMessage:
    role: str  # system, user, assistant
    content: str

@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict  # input_tokens, output_tokens
    latency_ms: int

@dataclass  
class LLMStreamChunk:
    content: str
    done: bool


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""
        pass
    
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """Non-streaming completion."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Streaming completion."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test provider connectivity."""
        pass
```

### 3.3 Provider Implementations

```python
# src/barnabee/llm/providers/azure_openai.py
from openai import AsyncAzureOpenAI

class AzureOpenAIProvider(LLMProvider):
    provider_id = "azure_openai"
    
    def __init__(self, config: LLMProviderConfig):
        self.client = AsyncAzureOpenAI(
            api_key=decrypt(config.api_key_encrypted),
            api_version="2024-02-01",
            azure_endpoint=config.api_endpoint,
        )
        self.default_model = config.default_model
    
    async def complete(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        start = time.perf_counter()
        
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        latency_ms = int((time.perf_counter() - start) * 1000)
        
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            latency_ms=latency_ms,
        )
    
    async def stream(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncIterator[LLMStreamChunk]:
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield LLMStreamChunk(
                    content=chunk.choices[0].delta.content,
                    done=False,
                )
        
        yield LLMStreamChunk(content="", done=True)


# src/barnabee/llm/providers/anthropic.py
from anthropic import AsyncAnthropic

class AnthropicProvider(LLMProvider):
    provider_id = "anthropic"
    
    def __init__(self, config: LLMProviderConfig):
        self.client = AsyncAnthropic(
            api_key=decrypt(config.api_key_encrypted),
        )
        self.default_model = config.default_model
    
    async def complete(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        start = time.perf_counter()
        
        # Anthropic uses separate system parameter
        system = next((m.content for m in messages if m.role == "system"), None)
        chat_messages = [
            {"role": m.role, "content": m.content}
            for m in messages if m.role != "system"
        ]
        
        response = await self.client.messages.create(
            model=model or self.default_model,
            system=system,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        latency_ms = int((time.perf_counter() - start) * 1000)
        
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            latency_ms=latency_ms,
        )


# src/barnabee/llm/providers/openrouter.py
class OpenRouterProvider(LLMProvider):
    """OpenRouter - unified API for multiple providers."""
    provider_id = "openrouter"
    
    def __init__(self, config: LLMProviderConfig):
        self.client = AsyncOpenAI(
            api_key=decrypt(config.api_key_encrypted),
            base_url="https://openrouter.ai/api/v1",
        )
        self.default_model = config.default_model
    
    # Implementation similar to OpenAI...


# src/barnabee/llm/providers/google.py
import google.generativeai as genai

class GoogleGeminiProvider(LLMProvider):
    provider_id = "google"
    
    def __init__(self, config: LLMProviderConfig):
        genai.configure(api_key=decrypt(config.api_key_encrypted))
        self.default_model = config.default_model
    
    async def complete(
        self,
        messages: list[LLMMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        start = time.perf_counter()
        
        model_instance = genai.GenerativeModel(model or self.default_model)
        
        # Convert messages to Gemini format
        chat = model_instance.start_chat(history=[])
        
        # Add system message as first user message if present
        system = next((m.content for m in messages if m.role == "system"), None)
        if system:
            chat.send_message(f"System instructions: {system}")
        
        # Get response to last user message
        user_message = next(m.content for m in reversed(messages) if m.role == "user")
        response = await asyncio.to_thread(chat.send_message, user_message)
        
        latency_ms = int((time.perf_counter() - start) * 1000)
        
        return LLMResponse(
            content=response.text,
            model=model or self.default_model,
            usage={
                "input_tokens": response.usage_metadata.prompt_token_count,
                "output_tokens": response.usage_metadata.candidates_token_count,
            },
            latency_ms=latency_ms,
        )


# src/barnabee/llm/providers/xai.py
class XAIGrokProvider(LLMProvider):
    """xAI Grok provider."""
    provider_id = "xai"
    
    def __init__(self, config: LLMProviderConfig):
        self.client = AsyncOpenAI(
            api_key=decrypt(config.api_key_encrypted),
            base_url="https://api.x.ai/v1",
        )
        self.default_model = config.default_model
    
    # Implementation similar to OpenAI...
```

### 3.4 Provider Registry

```python
# src/barnabee/llm/registry.py

class LLMRegistry:
    """Registry for LLM providers with hot-swap support."""
    
    _providers: dict[str, type[LLMProvider]] = {
        "azure_openai": AzureOpenAIProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "openrouter": OpenRouterProvider,
        "google": GoogleGeminiProvider,
        "xai": XAIGrokProvider,
    }
    
    _instances: dict[str, LLMProvider] = {}
    _active: Optional[LLMProvider] = None
    _active_model: Optional[str] = None
    
    @classmethod
    async def initialize(cls, db):
        """Load provider configs and initialize active provider."""
        configs = await db.fetch_all("SELECT * FROM llm_providers WHERE enabled = 1")
        
        for config in configs:
            provider_class = cls._providers.get(config.id)
            if provider_class:
                cls._instances[config.id] = provider_class(config)
        
        # Load active config
        active = await db.fetch_one("SELECT * FROM llm_active_config WHERE id = 1")
        if active and active.provider_id in cls._instances:
            cls._active = cls._instances[active.provider_id]
            cls._active_model = active.model
    
    @classmethod
    def get_active(cls) -> LLMProvider:
        """Get currently active provider."""
        if not cls._active:
            raise LLMNotConfiguredError("No LLM provider configured")
        return cls._active
    
    @classmethod
    def get_active_model(cls) -> str:
        """Get currently active model."""
        return cls._active_model
    
    @classmethod
    async def set_active(cls, provider_id: str, model: str, db, user_id: str):
        """Hot-swap active provider."""
        if provider_id not in cls._instances:
            raise LLMProviderNotFoundError(provider_id)
        
        # Test connection before switching
        provider = cls._instances[provider_id]
        if not await provider.test_connection():
            raise LLMConnectionError(f"Cannot connect to {provider_id}")
        
        # Update database
        await db.execute("""
            INSERT OR REPLACE INTO llm_active_config (id, provider_id, model, updated_at, updated_by)
            VALUES (1, ?, ?, datetime('now'), ?)
        """, provider_id, model, user_id)
        
        # Update in-memory
        cls._active = provider
        cls._active_model = model
        
        logger.info("llm_provider_switched", provider=provider_id, model=model, by=user_id)
```

### 3.5 Unified LLM Interface

```python
# src/barnabee/llm/client.py

class LLMClient:
    """High-level LLM client used throughout the application."""
    
    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Simple completion interface."""
        provider = LLMRegistry.get_active()
        model = LLMRegistry.get_active_model()
        
        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]
        
        response = await provider.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Track usage for cost monitoring
        await self._track_usage(provider.provider_id, model, response.usage)
        
        return response.content
    
    async def stream(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncIterator[str]:
        """Streaming completion interface."""
        provider = LLMRegistry.get_active()
        model = LLMRegistry.get_active_model()
        
        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]
        
        async for chunk in provider.stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if not chunk.done:
                yield chunk.content


# Global instance
llm = LLMClient()

# Usage anywhere in codebase:
# response = await llm.complete(system="...", user="...")
```

---

## 4. Dashboard Provider Management

### 4.1 API Endpoints

```python
@router.get("/admin/llm/providers")
async def list_llm_providers(
    user: User = Depends(require_super_user)
) -> LLMProviderList:
    """List all configured providers."""
    providers = await db.fetch_all("SELECT * FROM llm_providers")
    return LLMProviderList(providers=[
        LLMProviderConfig(
            provider=p.id,
            name=p.name,
            enabled=bool(p.enabled),
            models=json.loads(p.available_models),
            default_model=p.default_model,
        )
        for p in providers
    ])


@router.get("/admin/llm/active")
async def get_active_llm_provider(
    user: User = Depends(require_super_user)
) -> ActiveLLMProvider:
    """Get currently active provider."""
    active = await db.fetch_one("SELECT * FROM llm_active_config WHERE id = 1")
    return ActiveLLMProvider(
        provider=active.provider_id,
        model=active.model,
        updated_at=active.updated_at,
    )


@router.put("/admin/llm/active")
async def set_active_llm_provider(
    request: SetLLMProviderRequest,
    user: User = Depends(require_super_user),
) -> ActiveLLMProvider:
    """Set active LLM provider."""
    await LLMRegistry.set_active(
        provider_id=request.provider,
        model=request.model,
        db=db,
        user_id=user.id,
    )
    return await get_active_llm_provider(user)


@router.post("/admin/llm/test")
async def test_llm_provider(
    request: TestLLMProviderRequest,
    user: User = Depends(require_super_user),
) -> LLMTestResult:
    """Test LLM provider connection."""
    provider = LLMRegistry._instances.get(request.provider)
    if not provider:
        return LLMTestResult(success=False, error="Provider not found")
    
    try:
        start = time.perf_counter()
        response = await provider.complete(
            messages=[
                LLMMessage(role="user", content="Say 'hello' and nothing else.")
            ],
            model=request.model,
            max_tokens=10,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        
        return LLMTestResult(
            success=True,
            latency_ms=latency_ms,
            response_preview=response.content[:100],
        )
    except Exception as e:
        return LLMTestResult(success=False, error=str(e))


@router.put("/admin/llm/providers/{provider_id}/credentials")
async def update_provider_credentials(
    provider_id: str,
    request: UpdateCredentialsRequest,
    user: User = Depends(require_super_user),
):
    """Update API key for a provider."""
    encrypted = encrypt(request.api_key)
    
    await db.execute("""
        UPDATE llm_providers 
        SET api_key_encrypted = ?, api_endpoint = ?, enabled = 1, updated_at = datetime('now')
        WHERE id = ?
    """, encrypted, request.api_endpoint, provider_id)
    
    # Reinitialize provider
    config = await db.fetch_one("SELECT * FROM llm_providers WHERE id = ?", provider_id)
    provider_class = LLMRegistry._providers.get(provider_id)
    if provider_class:
        LLMRegistry._instances[provider_id] = provider_class(config)
    
    return {"status": "updated"}
```

---

## 5. Implementation Checklist

### OpenAPI Spec
- [ ] Full OpenAPI 3.1 spec complete
- [ ] All schemas defined
- [ ] Authentication documented
- [ ] Error responses standardized

### LLM Abstraction
- [ ] Base provider interface
- [ ] Azure OpenAI provider
- [ ] OpenAI provider
- [ ] Anthropic provider
- [ ] OpenRouter provider
- [ ] Google Gemini provider
- [ ] xAI Grok provider
- [ ] Provider registry with hot-swap

### Dashboard Integration
- [ ] Provider list endpoint
- [ ] Active provider get/set endpoints
- [ ] Credential update endpoint
- [ ] Connection test endpoint
- [ ] Dashboard UI for provider management

### Observability
- [ ] Usage tracking per provider
- [ ] Cost tracking
- [ ] Latency metrics per provider/model

---

## 6. Acceptance Criteria

1. **OpenAPI spec validates:** No errors in spec validation
2. **Hot-swap works:** Provider change takes effect without restart
3. **All providers functional:** Test endpoint passes for all configured providers
4. **Dashboard control:** Provider can be changed from dashboard UI
5. **Metrics flowing:** Provider/model latency visible in Grafana

---

**End of Area 15: API Contracts & LLM Provider Abstraction**
