# BarnabeeNet Project Context

> **This file is Copilot's "memory". Update it after each work session.**

## Last Updated
2026-01-18 (Typo Handling + Memory System Fixes)

## Current Phase
**Phase 1: Core Services** - FULL PIPELINE WORKING + COMPREHENSIVE LOGGING

## Development Workflow

**Hybrid Claude + Copilot workflow is active:**
- Claude (claude.ai): Planning, research, architecture decisions
- Copilot (VS Code): Execution, file creation, testing, SSH commands
- Session files: `.copilot/sessions/`

To continue: Read this file → Check next steps → Create/execute session plan.

---

## Project State

### What's Working
- [x] Development environment (WSL + VS Code)
- [x] BarnabeeNet VM running NixOS 24.11 (192.168.86.51)
- [x] Redis container on VM (auto-starting)
- [x] Redis container on Man-of-war (Docker, for local dev)
- [x] Docker installed on Man-of-war WSL
- [x] Basic project structure + FastAPI skeleton
- [x] **STT (Distil-Whisper)** - Working, ~2.4s latency (CPU fallback)
- [x] **TTS (Kokoro)** - Working, 232-537ms latency, voice: bm_fable
- [x] Pronunciation fixes (Viola→Vyola, Xander→Zander)
- [x] Copilot agent configuration validated
- [x] **GPU Worker (Parakeet TDT 0.6B v2)** - Working locally, **45ms latency!**
- [x] **STT Router** - GPU primary, CPU fallback, with tests
- [x] **WSL port forwarding** - VM can reach GPU worker at `192.168.86.61:8001`
- [x] **Deployment scripts** - start/stop GPU worker, deploy to VM, status check
- [x] **Tests for STT/TTS services** - 54 tests covering all services

- [x] Message bus (Redis Streams)
- [x] Voice pipeline integration
- [x] **LLM Provider Abstraction** - Pluggable providers: OpenRouter, OpenAI, Anthropic, Azure, Google, Grok, Hugging Face
- [x] **Signal logging system** - Every LLM call logged for dashboard visibility
- [x] **MetaAgent** - Intent classification, context/mood evaluation, memory query generation
- [x] **InstantAgent** - Zero-latency responses for time, date, greetings, math
- [x] **ActionAgent** - Device control parsing, rule-based + LLM fallback, HA service calls
- [x] **InteractionAgent** - Complex conversations with LLM (Claude/GPT-4), Barnabee persona
- [x] **MemoryAgent** - Memory storage/retrieval/generation, working memory, conversation extraction
- [x] **AgentOrchestrator** - Full pipeline: classify → memory retrieve → route to agent → store memories
- [x] **Voice Pipeline + Orchestrator Integration** - Full voice-to-voice with multi-agent AI
- [x] **Memory Storage System** - EmbeddingService (all-MiniLM-L6-v2), MemoryStorage with Redis + in-memory fallback, vector similarity search
- [x] **Home Assistant Integration** - HomeAssistantClient with REST API, EntityRegistry with fuzzy name matching, service call execution
- [x] **Home Assistant Extended Discovery** - Device registry, Area registry, Automation states, Integration (config entry) listing, Error log fetching. Models for Device, Area, Automation, Integration, LogEntry. HADataSnapshot for cache summary. Methods: refresh_devices(), refresh_areas(), refresh_automations(), refresh_integrations(), refresh_all(), get_error_log().
- [x] **Dashboard Phase 1** - Dashboard API endpoints (activity feed, signal details, stats), Prometheus metrics, Grafana + Prometheus compose config
- [x] **Dashboard Phase 2** - WebSocket endpoint (/ws/activity) for real-time signal streaming, ConnectionManager with filtering, SignalStreamer background task reading from Redis Streams
- [x] **VM Deployment** - BarnabeeNet running on VM (192.168.86.51:8000), NixOS firewall configured, all services healthy
- [x] **Web Dashboard UI** - SkyrimNet-style dark theme dashboard at http://192.168.86.51:8000/
- [x] **Pipeline Signal Logging** - Full request tracing with PipelineLogger, SignalType enum (25+ types), RequestTrace model
- [x] **Dashboard Trace Visualization** - Request traces list, expandable trace details showing complete data flow (input → classify → agent → response)
- [x] **Activity-Based LLM Configuration** - Granular model selection per activity (16+ activities like meta.classify_intent, interaction.respond, memory.generate). Configurable via YAML (config/llm.yaml), environment variables (LLM_ACTIVITY_*), or defaults. Different models for classification vs conversation vs memory tasks.
- [x] **E2E Testing Framework** - Complete end-to-end test suite with API endpoints, dashboard integration, signal logging. Tests for InstantAgent (time, date, math, greetings), ActionAgent (device control), InteractionAgent (LLM conversations). Results visible in dashboard activity feed and trace inspector.
- [x] **Text Process Endpoint** - `/api/v1/voice/process` for text-only pipeline testing without audio (used by dashboard and E2E tests)
- [x] **E2E Testing Deployed to VM** - E2E endpoints accessible at http://192.168.86.51:8000/api/v1/e2e/, quick test runs successfully, results show assertions and agent routing. Tests fail without LLM API key (expected behavior - MetaAgent needs key for intent classification).
- [x] **LLM Provider Configuration System** - Dashboard-based provider config (not hardcoded). Encrypted secrets storage (Fernet encryption with master key). Support for 12 providers: OpenRouter, OpenAI, Anthropic, Azure, Google, xAI, DeepSeek, HuggingFace, Bedrock, Together, Mistral, Groq. Each provider has setup instructions, docs links, API key generation URLs. Config persisted in Redis (AOF enabled). API at /api/v1/config/providers, /api/v1/config/secrets. Dashboard UI in Configuration page.
- [x] **Provider Config Deployed to VM** - Master key generated and stored in .env, app restarted with encryption enabled. All 12 providers visible in /api/v1/config/providers/status endpoint. Ready to configure API keys via dashboard.
- [x] **OpenRouter API Key Configured** - API key set via dashboard Configuration page. Test connection succeeded. Orchestrator reads API key from encrypted provider config (SecretsService).
- [x] **LLM Working End-to-End** - Barnabee responds with personality! InteractionAgent calls LLM successfully. E2E tests show LLM responses like "Today is Wednesday, January 3rd, 2024. *adjusts pocket watch* Lovely winter day we're having, isn't it?"
- [x] **MetaAgent Classification Fixed** - Orchestrator now calls MetaAgent.classify() directly (was incorrectly calling handle_input and missing the ClassificationResult). Intent routing should now work correctly for instant/action/memory intents.
- [x] **MetaAgent Classification Verified on VM** - Deployed and tested on VM. E2E tests confirm: time/date/greeting queries route to InstantAgent (instant intent), conversation queries route to InteractionAgent (conversation intent). LLM responses working with Barnabee personality. Fixed restart.sh to load .env for master key persistence.
- [x] **Dashboard Model Selection UI** - New "Model Selection" config section with searchable dropdowns for all 16+ activities. Live model list from OpenRouter (339+ models), shows pricing and context length, filter for free models. Persists selections to Redis. API endpoints: GET/PUT /api/v1/config/activities, GET /api/v1/config/models.
- [x] **Testing/Production Mode Toggle** - One-click switch between Testing mode (all free models - Gemini 2.0 Flash) and Production mode (quality models - Claude, GPT-4o, DeepSeek). Mode persists in Redis. API: GET/POST /api/v1/config/mode.
- [x] **Home Assistant Dashboard UI + API** - Full dashboard integration at `/api/v1/homeassistant/`. Endpoints for: connection status, overview, entities (with search/filter/pagination), devices, areas, automations, integrations, logs, service calls, entity toggle. Dashboard Entities page with real-time entity cards, domain icons, state badges, toggle controls. Configuration page with HA setup instructions.
- [x] **Home Assistant Config Management** - Dashboard-based HA configuration (URL + token). Config saved to Redis, token encrypted via SecretsService. Tab-based UI for HA views: Entities, Areas, Devices, Automations, Logs. Test connection before saving. Config can also fall back to env vars (HA_URL, HA_TOKEN) for backwards compatibility.
- [x] **Dashboard Infrastructure (Phase 1)** - DashboardService central hub for data aggregation. MetricsStore with rolling window latency storage (p50/p95/p99). Enhanced WebSocket (/ws/dashboard) for real-time push of metrics/activity/tests.
- [x] **Logging Dashboard (Phase 2)** - Logs page with Chart.js performance graphs (STT/TTS/LLM/Pipeline latency). Real-time log stream with filtering by level (ERROR/WARN/INFO/DEBUG) and text search. Metrics API endpoints (GET/POST /api/v1/dashboard/metrics/*).
- [x] **Agent Prompts Page (Phase 3)** - Extracted all agent prompts to text files in /src/barnabeenet/prompts/ (meta_agent, instant_agent, action_agent, interaction_agent, memory_agent). Prompts API with version history (/api/v1/prompts/*). Dashboard UI for viewing/editing prompts with syntax highlighting, Ctrl+S save, history viewer, version restore.
- [x] **HA Control Panel (Phase 4)** - Enhanced entity cards with brightness sliders, color temperature controls, climate temperature adjustment, cover position sliders, media player controls. Area quick actions (all lights on/off). Service call dialog for advanced control. Entity context menu with details view. Toast notifications.
- [x] **"What Barnabee Knows" Page (Phase 4 revision)** - Refocused HA page from direct control to read-only knowledge view. Shows what Barnabee understands about Home Assistant: discovery stats, entity counts by domain, area information, device registry. Activity log for HA interactions. Tabs: Overview, Entities, Areas, Devices, Activity Log. The dashboard is for VIEWING what Barnabee knows, not for controlling devices directly (users should use HA dashboard for control).
- [x] **Home Assistant WebSocket API** - Implemented WebSocket protocol for HA device/area/entity registries (REST API doesn't expose these). Added `_ws_command()` method to HomeAssistantClient that handles auth flow (auth_required → send token → auth_ok → command → result). Commands: `config/device_registry/list`, `config/area_registry/list`, `config/entity_registry/list`. Entity dataclass enriched with device_id. Data now loads correctly: 2288 entities, 238 devices, 20 areas.
- [x] **Real-time HA State Changes** - Persistent WebSocket subscription to Home Assistant `state_changed` events. Auto-subscribes on connect with exponential backoff reconnection. StateChangeEvent model with rolling buffer (500 events). `/api/v1/homeassistant/events` endpoint for activity log. Dashboard Activity Log tab shows live state changes with domain icons, friendly names, and state transitions. Filters "interesting" domains (lights, switches, etc.) for overview.
- [x] **Dashboard Chat Tab (Phase 5)** - Direct text conversation with Barnabee from the dashboard. Chat bubble UI with avatars, timestamps, thinking animation. Suggestion chips for quick actions (time, weather, lights, jokes). Connects to `/api/v1/voice/process` endpoint. Shows agent used and intent on each response. Clear conversation button. Fully styled dark theme matching dashboard.
- [x] **Home Assistant Action Execution** - AgentOrchestrator now executes ActionAgent commands via HomeAssistantClient. After parsing device control commands (turn on/off, set value, etc.), the orchestrator: (1) resolves entity names to entity_ids using EntityRegistry fuzzy matching, (2) calls HA service via REST API, (3) logs execution result to pipeline signals. Tested: "Turn on/off dining table light" successfully controls `light.dining_table_light`. State changes visible in `/api/v1/homeassistant/events`.
- [x] **Smart Entity Resolution** - SmartEntityResolver class for intelligent batch operations. Features: (1) Area/room aliases ("living room" → living_room), (2) Floor-based commands ("lights downstairs" → all first floor lights), (3) Area groups ("kids rooms" → boys_room + girls_room + playroom), (4) Device type synonyms (blinds → cover, lights → light), (5) Cross-domain matching (searches switch domain for light commands since many lights are controlled by switches), (6) Word boundary matching to prevent false positives. Supports commands like "turn off all the lights downstairs", "close all the blinds in the living room", "open blinds in the girls room".
- [x] **Model Health Check** - API endpoint `/api/v1/config/models/health-check/{model_id}` tests if a model actually works (makes minimal test call). Batch endpoint `/api/v1/config/models/health-check-free` checks top free models. Results cached for 10 minutes. Health status endpoint `/api/v1/config/models/health-status` returns all cached results. Dashboard button "🩺 Health Check" shows working vs failed models with latency. Helps identify broken models in OpenRouter's list.
- [x] **AI Model Auto-Selection** - AI-powered optimal model selection for all activities. Endpoint `/api/v1/config/activities/auto-select` uses AI to analyze each activity's priority (speed/accuracy/quality/balanced) and description, then recommends best available free model. `/api/v1/config/activities/auto-select/apply` applies recommendations to Redis. Dashboard button "🤖 Auto-Select" triggers AI selection with confirmation. Uses qwen/qwen3-coder:free for free-only mode.
- [x] **Enhanced Model Health & Multi-Provider** - Models failing health check are hidden from dropdowns by default. Model list fetches from ALL configured providers (not just OpenRouter). Provider badge shows which system each model comes from (OpenRouter, OpenAI, Anthropic, etc.). Hourly background health check runs automatically. Health status API shows next scheduled check time. Working models sorted to top of dropdown. Verified working count shown in model summary.
- [x] **Mode-Aware Auto-Select** - Auto-select respects testing/production mode. Uses free_only=True for testing mode. Per-mode persistence: auto-select choices stored separately for testing and production modes. Toggling mode restores previously saved auto-selections.
- [x] **Comprehensive Activity Logging System** - New ActivityLogger service (`/api/v1/activity/*`) with 30+ ActivityType enum values (user.input, meta.classify, action.execute, interaction.respond, ha.state_change, llm.request, etc.). Activity and ConversationTrace models track full agent decision chains. WebSocket integration pushes activities to dashboard in real-time. Orchestrator logs classification, memory retrieval, and agent routing steps. HA client logs service calls and toggle actions.
- [x] **Agent Chain Display in Chat** - After each chat response, fetches conversation trace and displays collapsible "Agent Chain" showing step-by-step agent decisions. Shows agent icons (🧠 meta, ⚡ instant, 🎯 action, 💬 interaction, 📝 memory), actions, summaries, and durations. Expandable/collapsible via click. CSS styled to match dark theme.
- [x] **Secrets Persistence Verified** - All API keys and HA tokens are encrypted (Fernet AES-128) and stored in Redis. Master key loaded from BARNABEENET_MASTER_KEY env var. Fixed bug in /homeassistant/status endpoint returning wrong URL. Added error logging for secret decryption failures. Secrets survive restarts: HA token, OpenRouter key, and 7 other provider keys all persist correctly.
- [x] **Dashboard Phase 2: SkyrimNet Parity** - (1) HA State Change Streaming: `_handle_state_change()` logs to ActivityLogger with domain icons (💡🔌🌡️🔒 etc.), broadcasts via WebSocket to dashboard. (2) Expandable LLM Request Cards: `showLLMInspector()` modal shows full LLM signal details (system prompt, messages, response, tokens, cost, latency). (3) Waterfall Timeline: `renderWaterfallTimeline()` visualizes request duration breakdown per component with colored bars. (4) Live Stats Bar: Real-time counters (events/sec, total, LLM calls, HA events) on Logs page. CSS for `.llm-inspector-modal`, `.waterfall-timeline`, `.activity-stats-bar`.
- [x] **Typo-Tolerant Voice Commands** - MetaAgent and ActionAgent patterns handle common typos: "trun", "tunr" → turn; "swtich", "swich" → switch; "of" → off. Mid-sentence patterns catch commands embedded in longer phrases. Tested: "trun off the office light" correctly executes `light.turn_off` on `light.office_light`.
- [x] **Memory System Fixed** - Orchestrator now passes memory operation (STORE/RETRIEVE/FORGET) from MetaAgent's sub_category to MemoryAgent. Binary Redis client for embedding storage (fixes UTF-8 decode errors with numpy arrays). Memory store/recall now working: "remember my favorite color is blue" stores, "do you remember my favorite color" retrieves.

### In Progress
- [ ] Dashboard Phase 6: Voice input in Chat tab (microphone)

### Not Started
- [ ] HA activity feed integration (filter by HA vs other activities)
- [ ] Home Assistant intelligent log filtering agent
- [ ] Family profile system

---

## Deployment Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| **BarnabeeNet App** | VM (192.168.86.51:8000) | Main runtime - agents, API, dashboard |
| **Redis** | VM (192.168.86.51:6379) | Message bus, signals, memory cache |
| **Prometheus** | VM (192.168.86.51:9090) | Metrics storage |
| **Grafana** | VM (192.168.86.51:3000) | Dashboard UI |
| **GPU STT Worker** | Man-of-war (192.168.86.61:8001) | Fast transcription via RTX 4070 Ti |

**Deployment flow:**
1. Develop & test locally on Man-of-war
2. `./scripts/deploy-vm.sh` pushes to VM and restarts services
3. VM runs production, Man-of-war provides GPU acceleration

---

## Environment Quick Reference

| Resource | Location |
|----------|----------|
| Dev workspace | `/home/thom/projects/barnabeenet` (WSL) |
| VM runtime | `thom@192.168.86.51:~/barnabeenet` |
| Redis (VM) | `192.168.86.51:6379` |
| Redis (local) | `localhost:6379` (Docker on Man-of-war) |
| GPU Worker | `localhost:8001` (WSL) / `192.168.86.61:8001` (from VM) |
| GPU venv | `.venv-gpu/` (separate from main `.venv/`) |
| Windows Host (LAN) | `192.168.86.61` |

---

## Next Steps (Ordered)

1. Dashboard Phase 5: AI Chat tab - text-to-Barnabee with real-time streaming ← NEXT
2. Dashboard Phase 6: Testing Dashboard enhancements - E2E runner, mock HA
3. Dashboard Phase 7: Memory Dashboard - view/search memories, conversation history
4. Dashboard Phase 8: Polish - loading states, error handling, responsive design
5. Dashboard Phase 9: Integration - tie everything together
6. Connect to actual Home Assistant instance - configure via dashboard
7. HA activity feed integration (filter by HA vs other activities)
8. Home Assistant intelligent log filtering agent
9. Family profile system

---

## STT/TTS Performance Baseline

| Service | Engine | Latency | Notes |
|---------|--------|---------|-------|
| STT (CPU) | Distil-Whisper | ~2,400ms | Fallback option |
| STT (GPU) | Parakeet TDT 0.6B v2 | **45ms** ✅ | 53x faster than CPU! |
| TTS | Kokoro-82M | 232-537ms | Working, voice: bm_fable |

### GPU Worker Details
- Location: `workers/gpu_stt_worker.py`
- Model: nvidia/parakeet-tdt-0.6b-v2
- GPU: RTX 4070 Ti (CUDA 12.4)
- Endpoints: `/health`, `/transcribe`
- Start: `screen -dmS gpu_worker python -m uvicorn workers.gpu_stt_worker:app --host 0.0.0.0 --port 8001`

---

## Recent Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-18 | Fix orchestrator to call MetaAgent.classify() | Bug: was calling handle_input() and missing ClassificationResult object |
| 2026-01-18 | Dashboard-based LLM provider config | Production-ready: no hardcoded keys, supports 12 providers, encrypted storage |
| 2026-01-18 | Fernet encryption for secrets | Master key from env var, secure at-rest storage in Redis |
| 2026-01-18 | E2E testing framework | Automated pipeline validation with dashboard visibility |
| 2026-01-18 | Activity-based LLM config | Granular control: fast/cheap models for classification, quality models for conversation |
| 2026-01-17 | OpenRouter for LLM API | Multi-model support, good pricing, reliable |
| 2026-01-17 | Multi-agent model config | Different models per agent type (SkyrimNet pattern) |
| 2026-01-17 | Signal logging to Redis | Full observability for dashboard request inspector |
| 2026-01-17 | Parakeet TDT 0.6B v2 for GPU STT | 45ms latency, 53x faster than CPU |
| 2026-01-17 | Separate .venv-gpu for GPU worker | Isolate heavy NeMo deps from main venv |
| 2026-01-17 | Hybrid Claude+Copilot workflow | Claude for planning, Copilot for execution |
| 2026-01-17 | Docker on Man-of-war for local dev | Redis needed locally during development |
| 2026-01-17 | Voice: bm_fable (British male) | Best fit for Barnabee persona |

---

## Blocking Issues

None currently.

### Resolved
- **WSL2 Network Access** (2026-01-17): Configured Windows port forwarding. VM reaches GPU worker at `192.168.86.61:8001`

---

## Session Notes

_Use this section for temporary notes during a session. Clear when done._

---

## Files Reference

| File | Purpose |
|------|---------|
| `CONTEXT.md` | This file - Copilot's memory |
| `barnabeenet-project-log.md` | Detailed project history |
| `claude-project-rules.md` | Rules for Claude sessions |
| `.github/copilot-instructions.md` | Rules for Copilot agent |
| `.copilot/sessions/` | Session plans and results |
