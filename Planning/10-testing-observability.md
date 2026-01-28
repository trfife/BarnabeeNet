# Area 10: Testing & Observability

**Version:** 1.0  
**Status:** Implementation Ready  
**Dependencies:** All areas (parallel implementation)  
**Phase:** Parallel (all phases)  

---

## 1. Overview

### 1.1 Purpose

Testing & Observability runs parallel to all implementation phases. It ensures system correctness during development and provides visibility into production behavior. Without this layer, you're flying blind.

### 1.2 V1 Gaps

| V1 Problem | V2 Solution |
|------------|-------------|
| No structured testing | pytest suite with 80%+ coverage requirement |
| No latency visibility | OpenTelemetry traces for every request |
| Debugging via print statements | Structured logging with correlation IDs |
| No alerting | Prometheus + Alertmanager for threshold breaches |
| "It works on my machine" | Docker-based reproducible environments |
| No load testing | k6 scripts for latency validation |

### 1.3 Design Principles

1. **Observability is not optional.** Every component must emit metrics, traces, and logs.
2. **Test at boundaries.** Unit tests for logic, integration tests for contracts, E2E for user flows.
3. **Correlation everywhere.** Single request ID traces from wake word to TTS completion.
4. **Alerts must be actionable.** No alert without a runbook.
5. **Performance budgets are tests.** Latency regression fails CI.

---

## 2. Testing Strategy

### 2.1 Test Pyramid

```
                    ┌─────────────┐
                    │    E2E      │  ← 10% of tests
                    │  (Slow)     │     Full voice pipeline
                    ├─────────────┤
                    │ Integration │  ← 30% of tests
                    │  (Medium)   │     Component boundaries
                    ├─────────────┤
                    │    Unit     │  ← 60% of tests
                    │   (Fast)    │     Pure logic
                    └─────────────┘
```

### 2.2 Coverage Requirements

| Component | Min Coverage | Critical Paths |
|-----------|--------------|----------------|
| Intent Classification | 90% | Cascade stages, entity extraction |
| Response Generation | 85% | All response paths, persona injection |
| Memory System | 90% | CRUD, search, embedding |
| HA Integration | 80% | Entity cache, command execution |
| Self-Improvement | 95% | Tier checks, shadow testing, rollback |
| Voice Pipeline | 75% | State machine, error handling |

### 2.3 Test Types

```python
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --cov=src/barnabee --cov-report=html --cov-fail-under=80
markers =
    unit: Unit tests (fast, no I/O)
    integration: Integration tests (may use DB, Redis)
    e2e: End-to-end tests (full system)
    slow: Slow tests (>1s)
    gpu: Requires GPU
```

---

## 3. Unit Testing

### 3.1 Structure

```
tests/
├── unit/
│   ├── classification/
│   │   ├── test_preprocessor.py
│   │   ├── test_fast_pattern.py
│   │   ├── test_embedding_classifier.py
│   │   ├── test_entity_extraction.py
│   │   └── test_entity_resolution.py
│   ├── response/
│   │   ├── test_path_selector.py
│   │   ├── test_template_generator.py
│   │   ├── test_voice_optimizer.py
│   │   └── test_persona_checker.py
│   ├── memory/
│   │   ├── test_explicit_creator.py
│   │   ├── test_retriever.py
│   │   ├── test_deleter.py
│   │   └── test_progressive_search.py
│   ├── ha/
│   │   ├── test_entity_cache.py
│   │   ├── test_context_injection.py
│   │   └── test_command_executor.py
│   ├── improvement/
│   │   ├── test_signal_collector.py
│   │   ├── test_analyzer.py
│   │   ├── test_shadow_runner.py
│   │   └── test_deployer.py
│   └── voice/
│       ├── test_smart_turn.py
│       ├── test_sentence_buffer.py
│       └── test_state_machine.py
```

### 3.2 Example Unit Tests

```python
# tests/unit/classification/test_preprocessor.py
import pytest
from barnabee.classification.preprocessor import Preprocessor

class TestPreprocessor:
    @pytest.fixture
    def preprocessor(self):
        return Preprocessor()
    
    @pytest.mark.unit
    def test_removes_wake_word(self, preprocessor):
        """Wake word variants should be stripped."""
        cases = [
            ("barnabee turn on the lights", "turn on the lights"),
            ("hey barnabee what time is it", "what time is it"),
            ("BARNABEE help", "help"),
        ]
        for input_text, expected in cases:
            assert preprocessor.normalize(input_text) == expected
    
    @pytest.mark.unit
    def test_removes_politeness(self, preprocessor):
        """Politeness phrases should be stripped."""
        cases = [
            ("please turn on the lights", "turn on the lights"),
            ("can you turn on the lights please", "turn on the lights"),
            ("could you help me", "help me"),
        ]
        for input_text, expected in cases:
            assert preprocessor.normalize(input_text) == expected
    
    @pytest.mark.unit
    def test_expands_contractions(self, preprocessor):
        """Contractions should be expanded."""
        cases = [
            ("what's the time", "what is the time"),
            ("i'm hungry", "i am hungry"),
            ("it's cold", "it is cold"),
        ]
        for input_text, expected in cases:
            assert preprocessor.normalize(input_text) == expected
    
    @pytest.mark.unit
    def test_normalizes_whitespace(self, preprocessor):
        """Multiple spaces should collapse."""
        assert preprocessor.normalize("turn   on   lights") == "turn on lights"
    
    @pytest.mark.unit
    def test_handles_empty_input(self, preprocessor):
        """Empty input should return empty string."""
        assert preprocessor.normalize("") == ""
        assert preprocessor.normalize("   ") == ""


# tests/unit/response/test_voice_optimizer.py
import pytest
from barnabee.response.processing.voice_optimizer import VoiceOptimizer

class TestVoiceOptimizer:
    @pytest.fixture
    def optimizer(self):
        return VoiceOptimizer()
    
    @pytest.mark.unit
    def test_removes_markdown_bold(self, optimizer):
        assert optimizer.optimize("This is **bold** text") == "This is bold text"
    
    @pytest.mark.unit
    def test_removes_markdown_bullets(self, optimizer):
        text = "Here are items:\n- Item 1\n- Item 2"
        result = optimizer.optimize(text)
        assert "-" not in result
    
    @pytest.mark.unit
    def test_simplifies_large_numbers(self, optimizer):
        assert "thousand" in optimizer.optimize("There are 5,000 items")
    
    @pytest.mark.unit
    def test_expands_temperature(self, optimizer):
        assert "degrees" in optimizer.optimize("It's 72°F outside")
    
    @pytest.mark.unit
    def test_enforces_max_length(self, optimizer):
        long_text = " ".join(["word"] * 100)
        result = optimizer.optimize(long_text)
        assert len(result.split()) <= 75
    
    @pytest.mark.unit
    def test_preserves_short_text(self, optimizer):
        text = "The lights are on."
        assert optimizer.optimize(text) == text


# tests/unit/improvement/test_deployer.py
import pytest
from barnabee.improvement.deployment.deployer import ImprovementDeployer
from barnabee.improvement.models import Improvement

class TestImprovementDeployer:
    @pytest.mark.unit
    def test_rejects_tier_3_improvements(self, deployer, tier_3_improvement):
        """Tier 3 improvements must be blocked."""
        with pytest.raises(ForbiddenImprovementError):
            await deployer.deploy(tier_3_improvement)
    
    @pytest.mark.unit
    def test_requires_approval_for_tier_2(self, deployer, tier_2_improvement):
        """Tier 2 without approval must fail."""
        tier_2_improvement.approved_by = None
        with pytest.raises(ApprovalRequiredError):
            await deployer.deploy(tier_2_improvement)
    
    @pytest.mark.unit
    def test_requires_shadow_test_pass(self, deployer, tier_1_improvement):
        """Must pass shadow test before deploy."""
        tier_1_improvement.shadow_test_passed = False
        with pytest.raises(ValidationError):
            await deployer.deploy(tier_1_improvement)
    
    @pytest.mark.unit
    def test_creates_backup_before_deploy(self, deployer, tier_1_improvement, mock_db):
        """Backup must be created before applying."""
        await deployer.deploy(tier_1_improvement)
        mock_db.execute.assert_any_call(
            pytest.matches("INSERT INTO improvement_backups"),
            pytest.any()
        )
```

---

## 4. Integration Testing

### 4.1 Structure

```
tests/
├── integration/
│   ├── conftest.py              # Shared fixtures (test DB, Redis)
│   ├── test_classification_pipeline.py
│   ├── test_memory_lifecycle.py
│   ├── test_ha_integration.py
│   ├── test_improvement_pipeline.py
│   └── test_response_pipeline.py
```

### 4.2 Test Fixtures

```python
# tests/integration/conftest.py
import pytest
import asyncio
from sqlalchemy import create_engine
from redis import Redis

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_db():
    """Create test database."""
    # Use in-memory SQLite for speed
    engine = create_engine("sqlite:///:memory:")
    
    # Run migrations
    from barnabee.data.migrations import run_migrations
    run_migrations(engine)
    
    yield engine
    
    engine.dispose()

@pytest.fixture(scope="session")
def test_redis():
    """Create test Redis connection."""
    # Use fakeredis for isolation
    import fakeredis
    return fakeredis.FakeRedis()

@pytest.fixture
def db_session(test_db):
    """Create database session with rollback."""
    connection = test_db.connect()
    transaction = connection.begin()
    
    yield connection
    
    transaction.rollback()
    connection.close()

@pytest.fixture
def memory_repo(db_session, test_redis):
    """Create memory repository with test DB."""
    from barnabee.memory.repository import MemoryRepository
    return MemoryRepository(db=db_session, cache=test_redis)

@pytest.fixture
def classifier(db_session):
    """Create classifier with test DB."""
    from barnabee.classification.classifier import IntentClassifier
    return IntentClassifier(db=db_session, use_gpu=False)
```

### 4.3 Example Integration Tests

```python
# tests/integration/test_classification_pipeline.py
import pytest

class TestClassificationPipeline:
    @pytest.mark.integration
    async def test_fast_pattern_to_result(self, classifier):
        """Fast pattern match should return high confidence."""
        result = await classifier.classify("what time is it")
        
        assert result.intent == "time_query"
        assert result.confidence > 0.95
        assert result.stage == "fast_pattern"
    
    @pytest.mark.integration
    async def test_embedding_fallback(self, classifier):
        """Novel phrasing should use embedding stage."""
        result = await classifier.classify("tell me the current hour")
        
        assert result.intent == "time_query"
        assert result.stage in ("embedding", "local_classifier")
    
    @pytest.mark.integration
    async def test_entity_extraction_and_resolution(self, classifier, ha_cache):
        """Entities should be extracted and resolved."""
        result = await classifier.classify("turn on the kitchen lights")
        
        assert result.intent == "light_control"
        assert "kitchen" in str(result.entities.get("locations", []))
        assert result.entities.get("devices")  # Should resolve to entity IDs


# tests/integration/test_memory_lifecycle.py
class TestMemoryLifecycle:
    @pytest.mark.integration
    async def test_create_retrieve_delete(self, memory_repo):
        """Full memory lifecycle should work."""
        # Create
        memory = await memory_repo.create(
            summary="Test memory",
            content="This is test content",
            memory_type="fact",
            source_type="explicit",
            owner="test_user",
        )
        
        assert memory.id is not None
        
        # Retrieve
        retrieved = await memory_repo.get(memory.id)
        assert retrieved.summary == "Test memory"
        
        # Delete
        await memory_repo.soft_delete(memory.id, "test_user")
        
        # Verify soft deleted
        deleted = await memory_repo.get(memory.id)
        assert deleted.status == "deleted"
    
    @pytest.mark.integration
    async def test_search_returns_relevant(self, memory_repo, embedding_service):
        """Search should return semantically relevant memories."""
        # Create test memories
        await memory_repo.create(
            summary="Favorite color is blue",
            content="User's favorite color is blue",
            memory_type="preference",
            source_type="explicit",
            owner="test_user",
        )
        await memory_repo.create(
            summary="Works at Microsoft",
            content="User works at Microsoft",
            memory_type="fact",
            source_type="explicit",
            owner="test_user",
        )
        
        # Search
        results = await memory_repo.search(
            query="what color do they like",
            owner="test_user",
        )
        
        assert len(results) > 0
        assert "blue" in results[0].content.lower()


# tests/integration/test_improvement_pipeline.py
class TestImprovementPipeline:
    @pytest.mark.integration
    async def test_tier_1_auto_deploy(
        self, 
        signal_collector,
        analyzer,
        shadow_runner,
        deployer,
    ):
        """Tier 1 improvements should auto-deploy after passing tests."""
        # Record signals
        for _ in range(5):
            await signal_collector.record_llm_fallback(
                utterance="switch on the lights",
                classification_result=ClassificationResult(
                    intent="light_control",
                    confidence=0.92,
                    stage="llm",
                ),
            )
        
        # Analyze
        improvements = await analyzer.analyze_pending_signals()
        assert len(improvements) > 0
        
        improvement = improvements[0]
        assert improvement.tier == 1
        
        # Shadow test
        passed, results = await shadow_runner.test_improvement(improvement)
        assert passed
        
        # Deploy
        await deployer.deploy(improvement)
        
        # Verify applied
        assert improvement.status == "applied"
```

---

## 5. End-to-End Testing

### 5.1 E2E Test Structure

```
tests/
├── e2e/
│   ├── conftest.py              # Full system setup
│   ├── test_voice_commands.py   # Command flow
│   ├── test_conversations.py    # Multi-turn
│   ├── test_memory_operations.py
│   └── test_meeting_mode.py
```

### 5.2 E2E Test Framework

```python
# tests/e2e/conftest.py
import pytest
import docker
import asyncio
import httpx

@pytest.fixture(scope="session")
def barnabee_system():
    """Start full Barnabee system in Docker."""
    client = docker.from_env()
    
    # Start containers
    compose_file = "docker-compose.test.yml"
    # ... docker compose up
    
    # Wait for health
    async def wait_for_health():
        async with httpx.AsyncClient() as client:
            for _ in range(30):
                try:
                    r = await client.get("http://localhost:8080/health")
                    if r.status_code == 200:
                        return
                except:
                    pass
                await asyncio.sleep(1)
            raise TimeoutError("System did not become healthy")
    
    asyncio.run(wait_for_health())
    
    yield {
        "api_url": "http://localhost:8080",
        "ws_url": "ws://localhost:8080/ws",
    }
    
    # Cleanup
    # ... docker compose down


@pytest.fixture
def api_client(barnabee_system):
    """HTTP client for API calls."""
    return httpx.AsyncClient(base_url=barnabee_system["api_url"])


@pytest.fixture
def voice_simulator(barnabee_system):
    """Simulate voice input/output."""
    return VoiceSimulator(ws_url=barnabee_system["ws_url"])


class VoiceSimulator:
    """Simulate voice pipeline for testing."""
    
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
    
    async def connect(self, speaker_id: str = "test_user"):
        """Connect to voice WebSocket."""
        import websockets
        self.ws = await websockets.connect(
            f"{self.ws_url}/voice?speaker_id={speaker_id}"
        )
    
    async def send_utterance(self, text: str) -> dict:
        """Send text as if it were transcribed speech."""
        await self.ws.send(json.dumps({
            "type": "utterance",
            "text": text,
            "timestamp": datetime.utcnow().isoformat(),
        }))
        
        # Wait for response
        response = await asyncio.wait_for(
            self.ws.recv(),
            timeout=5.0
        )
        
        return json.loads(response)
    
    async def disconnect(self):
        if self.ws:
            await self.ws.close()
```

### 5.3 Example E2E Tests

```python
# tests/e2e/test_voice_commands.py
import pytest

class TestVoiceCommands:
    @pytest.mark.e2e
    async def test_light_control_command(self, voice_simulator, ha_mock):
        """Voice command should control lights."""
        await voice_simulator.connect()
        
        response = await voice_simulator.send_utterance(
            "turn on the kitchen lights"
        )
        
        assert response["type"] == "response"
        assert response["intent"] == "light_control"
        assert "kitchen" in response["text"].lower() or "done" in response["text"].lower()
        
        # Verify HA was called
        ha_mock.assert_service_called("light", "turn_on", entity_id="light.kitchen")
        
        await voice_simulator.disconnect()
    
    @pytest.mark.e2e
    async def test_time_query_fast_path(self, voice_simulator):
        """Time query should use template path (<100ms)."""
        await voice_simulator.connect()
        
        start = time.perf_counter()
        response = await voice_simulator.send_utterance("what time is it")
        latency = (time.perf_counter() - start) * 1000
        
        assert response["intent"] == "time_query"
        assert latency < 100  # Fast path target
        
        await voice_simulator.disconnect()
    
    @pytest.mark.e2e
    async def test_latency_budget_standard_path(self, voice_simulator):
        """Standard path should complete within latency budget."""
        await voice_simulator.connect()
        
        latencies = []
        test_utterances = [
            "turn on the lights",
            "what's the weather",
            "set a timer for 5 minutes",
        ]
        
        for utterance in test_utterances:
            start = time.perf_counter()
            await voice_simulator.send_utterance(utterance)
            latencies.append((time.perf_counter() - start) * 1000)
        
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 1200  # Standard path P95 target
        
        await voice_simulator.disconnect()


# tests/e2e/test_conversations.py
class TestConversations:
    @pytest.mark.e2e
    async def test_multi_turn_conversation(self, voice_simulator):
        """Multi-turn conversation should maintain context."""
        await voice_simulator.connect()
        
        # Turn 1
        r1 = await voice_simulator.send_utterance("let's talk")
        assert "conversation" in r1.get("mode", "")
        
        # Turn 2
        r2 = await voice_simulator.send_utterance(
            "I'm thinking about getting chickens"
        )
        
        # Turn 3 - should have context
        r3 = await voice_simulator.send_utterance(
            "how many eggs do they lay?"
        )
        
        # Response should understand "they" refers to chickens
        assert "chicken" in r3["text"].lower() or "egg" in r3["text"].lower()
        
        await voice_simulator.disconnect()
    
    @pytest.mark.e2e
    async def test_memory_creation_flow(self, voice_simulator, memory_repo):
        """Explicit memory creation should persist."""
        await voice_simulator.connect()
        
        response = await voice_simulator.send_utterance(
            "remember that my favorite color is green"
        )
        
        assert "remember" in response["text"].lower() or "got it" in response["text"].lower()
        
        # Verify memory was created
        memories = await memory_repo.search(
            query="favorite color",
            owner="test_user",
        )
        
        assert len(memories) > 0
        assert "green" in memories[0].content.lower()
        
        await voice_simulator.disconnect()
```

---

## 6. Performance Testing

### 6.1 k6 Load Tests

```javascript
// tests/load/latency_test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const latencyTrend = new Trend('response_latency');
const errorRate = new Rate('errors');

// Test configuration
export const options = {
  stages: [
    { duration: '1m', target: 10 },   // Ramp up
    { duration: '5m', target: 10 },   // Steady state
    { duration: '1m', target: 50 },   // Spike
    { duration: '2m', target: 50 },   // Sustained high
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    'response_latency': ['p95<1200'],  // P95 must be under 1200ms
    'errors': ['rate<0.01'],           // Error rate under 1%
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8080';

const TEST_UTTERANCES = [
  'what time is it',
  'turn on the kitchen lights',
  'set a timer for 5 minutes',
  'what is the weather',
  'remember that I have a meeting tomorrow',
];

export default function() {
  const utterance = TEST_UTTERANCES[Math.floor(Math.random() * TEST_UTTERANCES.length)];
  
  const payload = JSON.stringify({
    utterance: utterance,
    speaker_id: 'load_test_user',
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const start = Date.now();
  const res = http.post(`${BASE_URL}/api/process`, payload, params);
  const latency = Date.now() - start;
  
  latencyTrend.add(latency);
  
  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'has response text': (r) => r.json().text !== undefined,
    'latency under 2s': () => latency < 2000,
  });
  
  if (!success) {
    errorRate.add(1);
  }
  
  sleep(1);
}
```

### 6.2 Performance Test CI Integration

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start test environment
        run: docker-compose -f docker-compose.test.yml up -d
      
      - name: Wait for health
        run: |
          for i in {1..30}; do
            curl -s http://localhost:8080/health && break
            sleep 2
          done
      
      - name: Run k6 load test
        uses: grafana/k6-action@v0.3.0
        with:
          filename: tests/load/latency_test.js
          flags: --out json=results.json
        env:
          API_URL: http://localhost:8080
      
      - name: Check thresholds
        run: |
          # Parse results and fail if thresholds breached
          python scripts/check_perf_thresholds.py results.json
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: results.json
```

---

## 7. Observability Stack

### 7.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITY STACK                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  APPLICATION                                                                 │
│  ═══════════                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     BARNABEE SERVICES                                │   │
│  │                                                                      │   │
│  │  Instrumented with:                                                 │   │
│  │  • OpenTelemetry SDK (traces)                                       │   │
│  │  • Prometheus client (metrics)                                      │   │
│  │  • structlog (structured logs)                                      │   │
│  └──────────────┬────────────────────────────────────────┬─────────────┘   │
│                 │                                        │                  │
│        ┌────────┴────────┐                    ┌─────────┴─────────┐       │
│        │                 │                    │                   │       │
│        ▼                 ▼                    ▼                   ▼       │
│  ┌───────────┐    ┌───────────┐       ┌───────────┐      ┌───────────┐  │
│  │  OTLP     │    │Prometheus │       │  stdout   │      │  Loki     │  │
│  │ Exporter  │    │  /metrics │       │   logs    │      │ (future)  │  │
│  └─────┬─────┘    └─────┬─────┘       └─────┬─────┘      └───────────┘  │
│        │                │                   │                            │
│        ▼                ▼                   ▼                            │
│  ┌───────────┐    ┌───────────┐       ┌───────────┐                     │
│  │  Jaeger   │    │Prometheus │       │   File    │                     │
│  │  (traces) │    │  Server   │       │ (rotate)  │                     │
│  └─────┬─────┘    └─────┬─────┘       └───────────┘                     │
│        │                │                                                │
│        │                ├──────────────────────┐                        │
│        │                │                      │                        │
│        ▼                ▼                      ▼                        │
│  ┌───────────────────────────────┐    ┌───────────────┐                │
│  │          GRAFANA              │    │ Alertmanager  │                │
│  │                               │    │               │                │
│  │  • Trace visualization        │    │ • Thresholds  │                │
│  │  • Metrics dashboards         │    │ • Routing     │                │
│  │  • Alerting rules             │    │ • Notifications│               │
│  └───────────────────────────────┘    └───────────────┘                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Tracing

```python
# src/barnabee/observability/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

def setup_tracing(service_name: str = "barnabee"):
    """Initialize OpenTelemetry tracing."""
    
    # Create provider
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service_name,
            "service.version": get_version(),
        })
    )
    
    # Add OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTLP_ENDPOINT", "localhost:4317"),
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set global provider
    trace.set_tracer_provider(provider)
    
    # Auto-instrument libraries
    FastAPIInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
    
    return trace.get_tracer(service_name)


# Usage in code
tracer = trace.get_tracer("barnabee")

class IntentClassifier:
    async def classify(self, text: str) -> ClassificationResult:
        with tracer.start_as_current_span("classify") as span:
            span.set_attribute("input.text", text)
            span.set_attribute("input.length", len(text))
            
            # Stage 1: Fast pattern
            with tracer.start_as_current_span("fast_pattern"):
                result = await self._fast_pattern_match(text)
                if result:
                    span.set_attribute("classification.stage", "fast_pattern")
                    return result
            
            # Stage 2: Embedding
            with tracer.start_as_current_span("embedding"):
                result = await self._embedding_classify(text)
                if result.confidence > 0.85:
                    span.set_attribute("classification.stage", "embedding")
                    return result
            
            # ... continue cascade
```

### 7.3 Metrics

```python
# src/barnabee/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Request metrics
REQUEST_COUNT = Counter(
    'barnabee_requests_total',
    'Total requests processed',
    ['intent', 'stage', 'status']
)

REQUEST_LATENCY = Histogram(
    'barnabee_request_latency_seconds',
    'Request latency in seconds',
    ['intent', 'stage'],
    buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 5.0]
)

# Classification metrics
CLASSIFICATION_CONFIDENCE = Histogram(
    'barnabee_classification_confidence',
    'Classification confidence distribution',
    ['intent'],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]
)

LLM_FALLBACK_RATE = Counter(
    'barnabee_llm_fallback_total',
    'LLM fallback occurrences',
    ['intent']
)

# Memory metrics
MEMORY_OPERATIONS = Counter(
    'barnabee_memory_operations_total',
    'Memory operations',
    ['operation', 'memory_type']
)

MEMORY_SEARCH_LATENCY = Histogram(
    'barnabee_memory_search_latency_seconds',
    'Memory search latency',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)

# HA metrics
HA_COMMAND_LATENCY = Histogram(
    'barnabee_ha_command_latency_seconds',
    'Home Assistant command latency',
    ['domain', 'service'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

HA_CONNECTION_STATUS = Gauge(
    'barnabee_ha_connected',
    'Home Assistant connection status'
)

# Self-improvement metrics
IMPROVEMENT_SIGNALS = Counter(
    'barnabee_improvement_signals_total',
    'Improvement signals collected',
    ['signal_type']
)

IMPROVEMENTS_DEPLOYED = Counter(
    'barnabee_improvements_deployed_total',
    'Improvements deployed',
    ['improvement_type', 'tier']
)

IMPROVEMENTS_ROLLED_BACK = Counter(
    'barnabee_improvements_rolled_back_total',
    'Improvements rolled back',
    ['improvement_type', 'reason']
)


# Metrics endpoint
from fastapi import FastAPI, Response

app = FastAPI()

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

### 7.4 Structured Logging

```python
# src/barnabee/observability/logging.py
import structlog
from structlog.processors import JSONRenderer, TimeStamper, add_log_level

def setup_logging():
    """Configure structured logging."""
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_log_level,
            TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.INFO if not DEBUG else logging.DEBUG
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage
logger = structlog.get_logger()

async def process_request(request_id: str, utterance: str):
    # Bind context for all logs in this request
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        utterance=utterance[:50],  # Truncate for logs
    )
    
    logger.info("processing_started")
    
    try:
        result = await classifier.classify(utterance)
        logger.info(
            "classification_complete",
            intent=result.intent,
            confidence=result.confidence,
            stage=result.stage,
        )
        
    except Exception as e:
        logger.error(
            "classification_failed",
            error=str(e),
            exc_info=True,
        )
        raise
```

### 7.5 Correlation IDs

```python
# src/barnabee/observability/correlation.py
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar('request_id', default='')

class CorrelationMiddleware(BaseHTTPMiddleware):
    """Add correlation ID to all requests."""
    
    async def dispatch(self, request, call_next):
        # Get or generate request ID
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        
        # Set in context
        request_id_var.set(request_id)
        
        # Add to structlog context
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # Add to OpenTelemetry span
        span = trace.get_current_span()
        span.set_attribute("request.id", request_id)
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers['X-Request-ID'] = request_id
        
        return response
```

---

## 8. Alerting

### 8.1 Alert Rules

```yaml
# alerting/rules.yml
groups:
  - name: barnabee
    rules:
      # Latency alerts
      - alert: HighP95Latency
        expr: histogram_quantile(0.95, rate(barnabee_request_latency_seconds_bucket[5m])) > 1.2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency above 1.2s"
          description: "P95 latency is {{ $value }}s, above 1.2s threshold"
          runbook: "https://wiki/runbooks/high-latency"
      
      - alert: CriticalP99Latency
        expr: histogram_quantile(0.99, rate(barnabee_request_latency_seconds_bucket[5m])) > 2.0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "P99 latency critical"
          description: "P99 latency is {{ $value }}s"
          runbook: "https://wiki/runbooks/critical-latency"
      
      # Error rate alerts
      - alert: HighErrorRate
        expr: rate(barnabee_requests_total{status="error"}[5m]) / rate(barnabee_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Error rate above 5%"
          runbook: "https://wiki/runbooks/high-errors"
      
      # LLM fallback rate
      - alert: HighLLMFallbackRate
        expr: rate(barnabee_llm_fallback_total[1h]) / rate(barnabee_requests_total[1h]) > 0.15
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "LLM fallback rate above 15%"
          description: "Classifier may need retraining"
          runbook: "https://wiki/runbooks/llm-fallback"
      
      # HA connection
      - alert: HADisconnected
        expr: barnabee_ha_connected == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Home Assistant disconnected"
          runbook: "https://wiki/runbooks/ha-disconnect"
      
      # Self-improvement rollback
      - alert: ImprovementRolledBack
        expr: increase(barnabee_improvements_rolled_back_total[1h]) > 0
        labels:
          severity: warning
        annotations:
          summary: "Self-improvement was rolled back"
          description: "Check dashboard for details"
          runbook: "https://wiki/runbooks/improvement-rollback"
```

### 8.2 Alertmanager Config

```yaml
# alerting/alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      repeat_interval: 15m

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://barnabee:8080/api/internal/alert'
        # Barnabee can announce alerts via voice
  
  - name: 'critical'
    webhook_configs:
      - url: 'http://barnabee:8080/api/internal/alert'
    # Add SMS/push notification for critical
```

---

## 9. Grafana Dashboards

### 9.1 Main Dashboard

```json
{
  "dashboard": {
    "title": "Barnabee Overview",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(barnabee_requests_total[5m])",
            "legendFormat": "{{intent}}"
          }
        ]
      },
      {
        "title": "Latency P50/P95/P99",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(barnabee_request_latency_seconds_bucket[5m]))",
            "legendFormat": "P50"
          },
          {
            "expr": "histogram_quantile(0.95, rate(barnabee_request_latency_seconds_bucket[5m]))",
            "legendFormat": "P95"
          },
          {
            "expr": "histogram_quantile(0.99, rate(barnabee_request_latency_seconds_bucket[5m]))",
            "legendFormat": "P99"
          }
        ]
      },
      {
        "title": "Classification Stage Distribution",
        "type": "piechart",
        "targets": [
          {
            "expr": "sum(rate(barnabee_requests_total[1h])) by (stage)"
          }
        ]
      },
      {
        "title": "LLM Fallback Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(barnabee_llm_fallback_total[1h]) / rate(barnabee_requests_total[1h]) * 100"
          }
        ],
        "unit": "percent"
      },
      {
        "title": "HA Command Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(barnabee_ha_command_latency_seconds_bucket[5m]))",
            "legendFormat": "{{domain}}.{{service}}"
          }
        ]
      },
      {
        "title": "Memory Operations",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(barnabee_memory_operations_total[5m])",
            "legendFormat": "{{operation}}"
          }
        ]
      }
    ]
  }
}
```

---

## 10. CI/CD Integration

### 10.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install ruff black mypy
      - name: Lint
        run: |
          ruff check src tests
          black --check src tests
          mypy src

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run unit tests
        run: pytest tests/unit -v --cov=src/barnabee --cov-fail-under=80
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run integration tests
        run: pytest tests/integration -v
        env:
          REDIS_URL: redis://localhost:6379

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - uses: actions/checkout@v3
      - name: Start test environment
        run: docker-compose -f docker-compose.test.yml up -d
      - name: Wait for health
        run: |
          for i in {1..60}; do
            curl -s http://localhost:8080/health && break
            sleep 2
          done
      - name: Run E2E tests
        run: pytest tests/e2e -v
      - name: Cleanup
        run: docker-compose -f docker-compose.test.yml down

  performance-check:
    runs-on: ubuntu-latest
    needs: [e2e-tests]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - name: Start test environment
        run: docker-compose -f docker-compose.test.yml up -d
      - name: Run performance tests
        uses: grafana/k6-action@v0.3.0
        with:
          filename: tests/load/latency_test.js
      - name: Verify thresholds
        run: python scripts/check_perf_thresholds.py
```

---

## 11. File Structure

```
barnabeenet-v2/
├── src/
│   └── barnabee/
│       └── observability/
│           ├── __init__.py
│           ├── tracing.py          # OpenTelemetry setup
│           ├── metrics.py          # Prometheus metrics
│           ├── logging.py          # Structured logging
│           └── correlation.py      # Request correlation
├── tests/
│   ├── unit/                       # Unit tests by component
│   ├── integration/                # Integration tests
│   ├── e2e/                        # End-to-end tests
│   └── load/                       # k6 performance tests
├── alerting/
│   ├── rules.yml                   # Prometheus alert rules
│   └── alertmanager.yml            # Alertmanager config
├── dashboards/
│   └── grafana/
│       ├── overview.json
│       ├── latency.json
│       └── classification.json
├── docker-compose.test.yml         # Test environment
├── pytest.ini                      # pytest configuration
└── .github/
    └── workflows/
        ├── ci.yml                  # CI pipeline
        └── performance.yml         # Scheduled perf tests
```

---

## 12. Implementation Checklist

### Testing

- [ ] pytest configuration
- [ ] Unit test structure for all components
- [ ] Integration test fixtures (DB, Redis)
- [ ] E2E test framework with Docker
- [ ] Voice simulator for E2E
- [ ] k6 load test scripts
- [ ] Golden dataset (500+ examples)
- [ ] Coverage thresholds enforced

### Tracing

- [ ] OpenTelemetry SDK setup
- [ ] Span creation for all stages
- [ ] Auto-instrumentation (FastAPI, httpx, SQLAlchemy)
- [ ] Jaeger deployment
- [ ] Trace visualization in Grafana

### Metrics

- [ ] Prometheus client setup
- [ ] Request metrics (count, latency)
- [ ] Classification metrics (confidence, stage)
- [ ] Memory metrics (operations, latency)
- [ ] HA metrics (command latency, connection)
- [ ] Self-improvement metrics
- [ ] Grafana dashboards

### Logging

- [ ] structlog configuration
- [ ] JSON log format
- [ ] Correlation ID propagation
- [ ] Log rotation
- [ ] Log search in dashboard

### Alerting

- [ ] Prometheus alert rules
- [ ] Alertmanager configuration
- [ ] Notification routing
- [ ] Runbook links
- [ ] Voice announcement integration

### CI/CD

- [ ] Lint job (ruff, black, mypy)
- [ ] Unit test job with coverage
- [ ] Integration test job
- [ ] E2E test job
- [ ] Performance test job
- [ ] Deploy pipeline

### Validation

- [ ] 80%+ code coverage
- [ ] All alerts have runbooks
- [ ] Traces visible in Grafana
- [ ] Performance thresholds enforced in CI
- [ ] Dashboard loads in <2s

---

## 13. Handoff Notes for Implementation Agent

### Critical Points

1. **Observability is not optional.** Every component must emit metrics, traces, and logs from day one. Adding it later is 10x harder.

2. **Correlation IDs are essential.** Without them, debugging production issues is impossible. Thread request_id through everything.

3. **Test at boundaries.** Unit tests for pure logic, integration tests for component contracts, E2E for user flows. Don't over-index on any one layer.

4. **Performance budgets are tests.** If P95 regresses, CI should fail. Bake latency requirements into the pipeline.

5. **Alerts must be actionable.** Every alert needs a runbook. If you can't write a runbook, the alert is useless.

### Common Pitfalls

- Not propagating correlation ID to async tasks
- Testing implementation details instead of behavior
- Alert fatigue from noisy thresholds
- Forgetting to instrument async code paths
- Not testing the unhappy paths

### Performance Targets (Reference)

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Fast path P95 | 600ms | 800ms |
| Standard path P95 | 1200ms | 1500ms |
| Classification accuracy | >95% | <93% |
| LLM fallback rate | <10% | >15% |
| HA command latency P95 | 500ms | 1000ms |
| Error rate | <1% | >5% |

---

**End of Area 10: Testing & Observability**

---

# BarnabeeNet V2 Implementation Complete

All 10 implementation specification documents are now complete:

| # | Area | Phase | Status |
|---|------|-------|--------|
| 00 | V2 Summary | - | ✅ |
| 01 | Core Data Layer | Infrastructure | ✅ |
| 02 | Voice Pipeline | Infrastructure | ✅ |
| 03 | Intent Classification | Backbone | ✅ |
| 04 | Home Assistant Integration | Backbone | ✅ |
| 05 | Memory System | Data | ✅ |
| 06 | Response Generation | Core Functionality | ✅ |
| 07 | Meeting/Scribe System | Extended | ✅ |
| 08 | Self-Improvement Pipeline | Extended | ✅ |
| 09 | Dashboard & Admin | Extended | ✅ |
| 10 | Testing & Observability | Parallel | ✅ |

**Total specification:** ~3,500 lines of implementation guidance across 10 documents.

Ready for implementation handoff.
