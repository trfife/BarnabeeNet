# BarnabeeNet Project Context

> **This file is Copilot's "memory". Update it after each work session.**

## Last Updated
2026-01-21 (Self-Improvement Dashboard Logging & Notifications)

## Current Phase
**Phases 1–4 done; 5–6 partial; Phase 7 complete (Logic + AI Correction + Diagnostics).** Full pipeline (STT/TTS/agents/HA/memory), dashboard, E2E, VM deploy. Next: mobile client, Proactive Agent.

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
- [x] **Detailed Error Messages** - InteractionAgent now tracks structured error info (agent, model, status_code, type, message) and returns user-friendly messages for HTTP errors (401=auth, 402=payment, 403=forbidden, 404=model unavailable, 429=rate limit, 5xx=server error). Error details propagated to conversation traces.
- [x] **HA Auto-Reconnect** - HomeAssistantClient `ensure_connected()` method pings HA before actions and auto-reconnects if stale. Orchestrator calls this before executing HA service calls. Connection marked failed on network/auth errors.
- [x] **Secrets Singleton Pattern** - Orchestrator uses `get_secrets_service()` singleton to ensure consistent encryption across all callers. Fixed issue where HA token was encrypted with random key before stable master key existed.
- [x] **Dashboard Voice Input (Phase 6)** - Microphone button in Chat tab for voice-to-voice conversations. Hold-to-record interaction with visual recording indicator (animated wave). WebM/Opus audio capture at 16kHz, sent to `/api/v1/voice/pipeline` for full STT→Agent→TTS processing. Auto-plays audio response when available. Mobile touch event support. Graceful fallback for unsupported browsers.
- [x] **Anti-Hallucination for Memory** - Updated InteractionAgent persona to NEVER make up personal information or past conversations. Explicit system prompt warning when no memories retrieved. MemoryAgent returns clearer "I don't have that information stored" response. Prevents LLM from fabricating facts when asked about things it wasn't told.
- [x] **Memory Dashboard (Phase 7)** - Full memory management UI: Memory API endpoints (list, search, store, delete, stats), tabbed interface (All Memories, Facts/Knowledge, Conversations, Diary, Search, Add Memory). Features: semantic search with similarity scores, memory type badges (semantic/episodic/procedural/working), participant/tag display, pagination, filter by type. Real-time stats (total memories, 24h/7d counts, storage backend). Add memory form with type, importance, participants, tags. Diary entries view for daily summaries.
- [x] **LLM-Generated Diary Summaries** - New "diary.generate" LLM activity for AI-powered diary creation. POST `/api/v1/memory/diary/generate?date=YYYY-MM-DD` endpoint uses LLM to write natural language diary entries from Barnabee's perspective. Summarizes memories for a specific date with warm, personal tone. Dashboard "Generate Today's Entry" button with date picker. Enhanced diary entry display showing mood badge (positive/neutral/concerned), highlights list, participants mentioned. Fallback to simple summary if no LLM API key configured. Mood detection from memory content heuristics.
- [x] **HA Activity Feed Filtering** - Enhanced activity filter dropdown with category-based filtering. New filter groups: "🏠 Home Assistant Only" (all ha.* types), "🤖 LLM Only", "🧠 Agents Only", "📝 Memory Only". Improved filter groupings with optgroups (Pipeline, Agents, LLM, Home Assistant, System). Fixed Logs page component filter to use "homeassistant" source value. Smart category matching supports both dot and underscore-separated activity types.
- [x] **HA Log Analysis Agent** - AI-powered Home Assistant log analysis. New LLM activity `ha.log_analyze` (openai/gpt-4o-mini, accuracy priority). POST `/api/v1/homeassistant/logs/analyze` endpoint fetches HA error logs and uses LLM to identify important issues (integration failures, automation errors, config problems, security warnings, resource issues). Returns structured issues with severity (high/medium/low), category, description, affected entities, and recommendations. Dashboard UI: new "Log Analysis" tab in HA page with "Analyze Logs" button. Results display with severity color-coding, issue cards with recommendations. Fallback to simple rule-based analysis when no LLM API key configured.
- [x] **Memory Classification Fix** - Fixed MetaAgent MEMORY_PATTERNS to handle natural phrasing like "can you remember...", "could you store...", "make a note...", "don't forget...". Previously these were caught by heuristic classifier as QUERY intent and routed to InteractionAgent (which would just pretend to store). New patterns match memory operations regardless of prefix. 591 tests pass.
- [x] **Chat Conversation History** - Dashboard chat now maintains conversation context across messages. Added `chatConversationId` tracking in app.js, passed to `/api/v1/voice/process` endpoint. Endpoint now returns orchestrator-generated conversation_id (was only echoing request). InteractionAgent uses conversation history for multi-turn conversations. Clear button resets conversation_id for fresh starts.
- [x] **Chat Processing Flow Display** - Enhanced chat UI shows detailed processing flow for each message. Visible by default (collapsible). Shows: Input → MetaAgent classification (intent) → Memory retrieval (if any) → Agent routing with model name, tokens, LLM latency → Actions executed (if any) → Memory storage (if any) → Response. Color-coded steps (blue=input, purple=classify, orange=memory, green=agent, red=action, teal=response). Click header to collapse/expand.
- [x] **Family Profile System** - Complete implementation based on SkyrimNet's NPC biography pattern. (1) Profile Models: `models/profiles.py` with FamilyMemberProfile, PublicProfileBlock (communication style, interests, preferences), PrivateProfileBlock (personal notes, goals, topics to avoid), ProfileDiff for LLM-generated updates. (2) ProfileService: CRUD operations, Redis storage with `profile:` prefix, event tracking with significance scores, version history (last 10), pending update management, privacy-aware context injection. (3) ProfileAgent: LLM-based profile generation and updates via `profile.generate` activity, diff creation with before/after preview. (4) Profile API: REST endpoints at `/api/v1/profiles/` (list, create, get, update, delete, events, generate-update, approve-update, reject-update, history, context, guests). (5) Dashboard Family Page: Tabs for Members/Pending Updates/Add Member, profile cards with avatars and stats, detailed profile modal, diff preview modal with approve/reject, event significance tracking. (6) Orchestrator Integration: `_get_profile_context()` retrieves speaker profile, injects into `agent_context["profile"]`, maps rooms to privacy zones (bedroom/office = private, others = common). (7) InteractionAgent: `_build_profile_section()` formats profile for system prompt with communication style, interests, preferences, and private context when appropriate. Profiles enable personalized responses based on family member preferences.
- [x] **HA Native Area Targeting (Phase 1)** - New HATopologyService (`services/homeassistant/topology.py`) that loads HA's floor/area registry via WebSocket API. Floor dataclass and HATopology dataclass for in-memory caching. FLOOR_TERM_MAPPINGS for natural language ("downstairs", "upstairs", "first floor" → floor_ids). Methods: `resolve_area(text)` returns area_id, `resolve_floor(text)` returns list of area_ids, `refresh()` reloads from HA, `get_areas_on_floor()`. No longer pre-resolving entities - uses HA's native area targeting for more reliable batch operations.
- [x] **HATarget Models (Phase 2)** - New ha_commands.py with HATarget dataclass (area_id, device_id, entity_id) preferring area_id over entity_id. HAServiceCall model combines service, target, and data. CommandSegment for parsed command parts (action, target, location, value). ParsedCommand groups multiple segments for compound commands.
- [x] **Compound Command Parser (Phase 3)** - CompoundCommandParser in `agents/parsing/compound_parser.py` that splits "X and Y" commands into multiple service calls. Splits on conjunctions ("and", "then", "also", "plus"). Extracts action/target/location/value from each segment. TARGET_NOUN_TO_DOMAIN and ACTION_VERB_TO_SERVICE mappings for deterministic parsing. Handles typos ("trun", "tunr" → turn). No LLM needed for simple commands - regex-based parsing is fast and reliable.
- [x] **Timer System (Phase 4)** - TimerManager service (`services/timers.py`) using HA timer helper entities. Three timer types: ALARM (wake me up in X), DEVICE_DURATION (turn off X in Y), DELAYED_ACTION (do X in Y minutes). Pool of timer.barnabee_1 through timer.barnabee_10 entities. ActiveTimer model tracks type, duration, action callback, entity_id. parse_duration() handles "5 minutes", "30 seconds", "1 hour". parse_timer_command() extracts timer intent from text. Timer service calls: timer.start, timer.cancel, timer.pause, timer.finish.
- [x] **Enhanced Observability (Phase 5)** - PipelineTrace model (`models/pipeline_trace.py`) with RoutingDecision for capturing full decision chain. generate_routing_reason() creates human-readable explanations of agent routing. TraceDetails schema added to TextProcessResponse with: routing_reason, pattern_matched, meta_processing_time_ms, context_evaluation, memory_queries, memories_data, parsed_segments, resolved_targets, service_calls, timer_info. Dashboard showProcessingFlow() enhanced to display: routing reason after classification, parsed segments for compound commands, service calls with area/entity targets, timer info when present. New CSS classes for trace details styling.
- [x] **Compound Command Fixes (Jan 2026)** - Multiple fixes to ensure compound commands like "turn on the office light and turn on the office fan" work correctly: (1) SSH restart script on VM (`~/barnabeenet/start.sh`) with proper `</dev/null` to prevent hanging. (2) HA token hardcoded as fallback constant in homeassistant.py. (3) Compound parser no longer extracts embedded location from target phrases ("office light" stays as target, not "light" + "office" location). (4) Orchestrator uses raw_text directly for segments, not re-adding location. (5) SmartEntityResolver ranks entities by device type word match. (6) HA URL fallback now skips the default "homeassistant.local" to use hardcoded IP.
- [x] **Tiered STT Input System** - Complete multi-engine STT architecture: (1) **STT Modes**: COMMAND (single utterance, default), REALTIME (streaming with word-by-word results), AMBIENT (batch every 30-60s). (2) **STT Engines**: AUTO (intelligent selection), PARAKEET (GPU, ~45ms), WHISPER (CPU fallback, ~2400ms), AZURE (cloud, for mobile/remote). (3) **Azure STT Integration**: New `azure_stt.py` with Azure Cognitive Services Speech SDK support for both batch and streaming modes. Config via AZURE_SPEECH_KEY/AZURE_SPEECH_REGION env vars. (4) **Enhanced STT Router**: `router.py` updated with engine selection logic (AUTO = GPU → Azure → CPU), `_select_engine()` method, `transcribe_streaming()` async generator for real-time results. (5) **WebSocket Streaming Endpoint**: `/ws/transcribe` for real-time audio streaming. Binary audio in, JSON partial/final results out. Config message for engine/language selection. (6) **Quick Input Endpoints**: `POST /input/text` for simple text input, `POST /input/audio` for file upload with transcription + response. (7) **Dashboard STT Settings**: Mode/engine selector in Chat tab, live STT status indicator showing engine availability, engine badge on transcribed messages. (8) **Mobile Client Architecture**: Placeholder docs at `docs/future/MOBILE_STT_CLIENT.md` with Android BT audio capture, Silero VAD, WebSocket streaming, offline buffering design.
- [x] **Mock HA Service for E2E Testing** - New `mock_ha.py` service that simulates Home Assistant for E2E action tests without requiring a real HA instance. Features: (1) MockEntity/EntityState models with common attributes (brightness, position, temperature). (2) 20 predefined mock entities across 7 rooms (living room, kitchen, bedroom, office, bathroom, garage, backyard). (3) MockHomeAssistant class with service call simulation (turn_on/off, toggle, open/close covers, set temperature). (4) Service call history tracking for test verification. (5) Singleton pattern with enable/disable/reset controls. (6) Mock HA API endpoints at `/api/v1/e2e/mock-ha/*` for status, enable, disable, reset, entities, history. Enables comprehensive E2E testing of device control commands without HA connectivity.
- [x] **Test Infrastructure Fixes** - Fixed multiple pre-existing test issues: (1) HA client now catches HTTPStatusError for 404s on error_log endpoint (was only catching RequestError). (2) Voice pipeline orchestrator tests patched correct module path (`barnabeenet.main.app_state` instead of `barnabeenet.services.voice_pipeline.app_state`). (3) HA API tests now reset global _ha_client between tests via autouse fixture to prevent event loop closure issues. All 617 tests now pass.
- [x] **Mock HA Client Adapter for E2E Testing** - MockHAClient adapter class provides HomeAssistantClient interface for mock HA. MockEntityRegistry with find_by_name(), get_by_domain(), get_by_area() methods for entity resolution. E2E test runner wires mock client into orchestrator when use_mock_ha=True (default). New ENTITY_STATE assertion type verifies entity state after action commands. Enhanced ACTION_TESTS with entity state verification (turn on light → verify entity state is "on"). Orchestrator now has set_ha_client() method and reset_orchestrator() for testing. 628 tests pass.
- [x] **Dashboard Polish** - Comprehensive UI improvements: (1) Loading skeletons with shimmer animation for cards/stats while data loads. (2) Error states with retry buttons for failed API calls. (3) Toast notification system with success/error/warning/info variants, auto-dismiss with progress bar. (4) Improved mobile navigation with horizontal scrolling nav links. (5) Offline detection banner with auto-reconnect. (6) WebSocket exponential backoff reconnection (max 30s delay). (7) Empty states for no-data scenarios. (8) Button loading states. (9) Accessibility focus states. (10) Print styles and reduced-motion support.
- [x] **Home Assistant Connected** - HA integration fully working on VM. URL: http://192.168.86.60:8123, Version 2026.1.2. Stats: 2291 entities, 238 devices, 20 areas, 6 automations, 64 integrations. Dashboard configuration page allows setting URL + token (encrypted). State change streaming active.
- [x] **Simple Chat API** - Dead-simple `/api/v1/chat` endpoint for HA/ViewAssist integration. POST or GET with just `text` parameter, returns `{"response": "..."}`. Integration guide at `docs/INTEGRATION.md` with examples for HA rest_command, shell_command, and ViewAssist.
- [x] **HA Custom Conversation Agent** - Full Home Assistant custom integration at `ha-integration/custom_components/barnabeenet/`. Registers as a conversation agent in HA's Voice assistants. Auto-detects speaker from logged-in HA user (via person entity). Auto-detects room from device area. Config flow with URL setup. Works with HA Cloud STT on phones.
- [x] **NixOS Auto-Start Service** - BarnabeeNet now auto-starts on VM boot via systemd. NixOS module at `/etc/nixos/barnabeenet.nix` defines `barnabeenet.service`: Type=simple, User=thom, auto-restarts on failure (RestartSec=5). Service is enabled and running, survives reboots. Uses existing Redis instance on VM.
- [x] **Logic Browser System (Phase 7.1)** - Complete externalization of BarnabeeNet's decision logic: (1) **YAML Config Files**: `config/patterns.yaml` (all pattern definitions by group: emergency, instant, action, memory, query, gesture), `config/routing.yaml` (intent→agent routing, priority rules, confidence thresholds), `config/overrides.yaml` (user/room/time-based behavior modifications, entity aliases). (2) **LogicRegistry** (`core/logic_registry.py`): Loads/manages YAML patterns, hot-reload support, pattern matching, change tracking with reason logging, API for runtime updates. (3) **DecisionRegistry** (`core/decision_registry.py`): Captures every decision point (pattern match, routing, override) with context manager for tracing, rolling buffer storage, trace_id correlation. (4) **Logic API** (`api/routes/logic.py`): REST endpoints for browsing/editing patterns (GET/PUT /patterns/{group}/{name}), routing rules, overrides, entity aliases, pattern testing (POST /patterns/test), change history. (5) **Dashboard Logic Page**: Stats cards (patterns/routing/overrides/aliases), tabbed UI (Patterns/Routing/Overrides/Aliases/Test), collapsible pattern groups, edit modal with regex/confidence/enabled fields, pattern tester for live classification testing. (6) **MetaAgent Integration**: Backward-compatible - tries LogicRegistry first, falls back to hardcoded patterns. 628 tests pass.
- [x] **Pipeline Trace Visualization (Phase 7.2 partial)** - Enhanced Logic Browser with: (1) **Waterfall Timeline**: Visual timeline showing timing of each pipeline signal with colored bars per component type (meta=purple, action=orange, interaction=blue, llm=indigo, etc.), relative positioning based on timestamps, duration labels. (2) **History Filters**: Agent type filter (instant/action/interaction/memory), success/error status filter, text search with debounce, filter results count display. (3) **Trace Detail Modal**: Shows full pipeline info including waterfall, input/output, classification, HA actions, LLM usage, signals list, raw JSON.
- [x] **AI Correction Assistant (Phase 7.3-7.4)** - Complete AI-assisted pattern correction system: (1) **"Mark as Wrong" Button**: Added to trace detail modal header, opens correction flow modal. (2) **Correction Modal UI**: Two-step flow - Step 1: select issue type (wrong_entity, wrong_action, wrong_routing, clarification_needed, tone_content) and describe expected result. Step 2: AI analysis results with suggestions. (3) **AICorrectionService** (`services/ai_correction.py`): Analyzes traces using LLM to diagnose root cause, generates fix suggestions (pattern_modify, entity_alias, routing_change, prompt_edit), test/apply methods for suggestions. (4) **Correction API**: POST `/api/v1/logic/corrections/analyze` analyzes trace and returns suggestions, POST `/api/v1/logic/corrections/{analysis_id}/suggestions/{suggestion_id}/test` tests a suggestion against historical data, POST `/api/v1/logic/corrections/{analysis_id}/suggestions/{suggestion_id}/apply` applies fix. (5) **Suggestion Cards**: Styled cards showing suggestion type, title, description, impact level (low/medium/high), confidence score, diff preview (before/after), reasoning. (6) **JavaScript Functions**: `openCorrectionModal()`, `analyzeCorrection()`, `renderCorrectionAnalysis()`, `testSuggestion()`, `applySuggestion()`, `markAsWrongOnly()`. 628 tests pass.
- [x] **ViewAssist Integration Documentation** - Complete ViewAssist integration guide at `docs/VIEWASSIST_INTEGRATION.md`. Documents full setup: (1) Install BarnabeeNet HA custom component. (2) Create Assist Pipeline with BarnabeeNet as conversation agent. (3) Install ViewAssist Companion App (VACA) on tablet. (4) Configure VACA to use BarnabeeNet Assist Pipeline. Architecture diagram shows flow: Tablet → VACA → HA Assist Pipeline → HA Cloud STT → BarnabeeNet Agent → Response. Direct API endpoints documented for advanced users (`/api/v1/chat`, `/api/v1/input/audio`). Updated `docs/INTEGRATION.md` with complete HA custom component instructions.
- [x] **Logic Diagnostics System (Phase 7.5)** - Deep pattern matching diagnostics for self-diagnosis: (1) **LogicDiagnosticsService** (`services/logic_diagnostics.py`): Analyzes why patterns match/don't match with detailed failure reasons. MatchFailureReason enum: NO_MATCH, CASE_MISMATCH, PARTIAL_MATCH, ANCHOR_FAIL, WORD_ORDER, MISSING_KEYWORD, EXTRA_WORDS, TYPO, DISABLED. (2) **PatternDiagnostics** dataclass: Full diagnostic report with near_misses (similar patterns above 0.6 threshold), suggested_patterns (auto-generated regex for new patterns), suggested_modifications (fixes for existing patterns). (3) **Edit Distance Calculation**: Levenshtein distance for typo detection, identifies single-character errors like "trun" → "turn". (4) **Keyword Extraction**: Extracts meaningful words from regex patterns, identifies missing keywords in input. (5) **MetaAgent Integration**: ClassificationResult extended with classification_method (pattern/heuristic/llm), patterns_checked count, near_miss_patterns, failure_diagnosis, diagnostics_summary. (6) **Diagnostics API Endpoints**: POST `/diagnostics/diagnose` for pattern analysis, GET `/diagnostics/stats` for diagnostic statistics, GET `/diagnostics/failures` for recent classification failures, POST `/diagnostics/classify` for full classification with diagnostics. (7) **AI Correction Enhancement**: `_get_pattern_diagnostics()` method provides near-miss info to AI correction for smarter suggestions. 645 tests pass (17 new for diagnostics).
- [x] **Logic Health Monitor (Phase 7.6)** - Tracks classification consistency and detects system health issues: (1) **LogicHealthMonitor** (`services/logic_health.py`): Records every classification for consistency analysis. Tracks classification history by normalized input hash. (2) **Consistency Detection**: Same normalized input should produce same classification. Detects when an input gets different results over time. (3) **Near-Miss Tracking**: Counts how often patterns almost match specific inputs - suggests pattern gaps. (4) **Failure Tracking**: Tracks which failure reasons are most common. (5) **Method Rate Tracking**: Monitors pattern_match vs heuristic vs llm fallback rates. (6) **Health Report Generation**: `generate_health_report()` returns HealthReport with consistency_score, avg_confidence, method rates, detected issues. (7) **Health Issues**: HealthIssue dataclass with types: INCONSISTENT_CLASSIFICATION, FREQUENT_NEAR_MISS, HIGH_FAILURE_RATE, CONFIDENCE_DRIFT. Severity levels (info/warning/error/critical). (8) **MetaAgent Integration**: `enable_health_monitoring` parameter, automatically records to health monitor after each classification. (9) **Health API Endpoints**: GET `/health` for full report, GET `/health/stats` for summary, GET `/health/inconsistent` for problematic inputs, GET `/health/near-misses` for pattern gaps, POST `/health/clear` to reset. 658 tests pass (13 new for health monitor).
- [x] **HA Person Entity Integration for Location Tracking** - Family profiles now integrate with HA person entities for real-time location: (1) **ha_person_entity Field**: Added to FamilyMemberProfile to link with HA person entities (e.g., "person.thom"). (2) **PersonLocation Model**: New model in `models/profiles.py` with state (home/not_home/zone), is_home bool, zone name, lat/lon coordinates, gps_accuracy, last_changed timestamp, source (device_tracker). (3) **ProfileService Location Methods**: `get_person_location(ha_person_entity)` fetches state from HA, parses attributes into PersonLocation. `get_all_family_locations()` returns locations for all profiles with HA entities. `get_profile_context()` now includes real-time location data. (4) **InteractionAgent Enhancement**: `_build_profile_section()` now displays location (Home/Away/zone) and arrival time ("just now", "X minutes ago"). `_build_mentioned_profiles_section()` includes location for family members mentioned in queries. (5) **Orchestrator Integration**: Passes HA client to profile service, `_get_mentioned_profiles()` fetches location context for mentioned family members. Enables "Where is X?", "Is X home?", and location-aware personalized responses.
- [x] **Self-Improvement Agent** - Autonomous code improvement system using Claude Code CLI: (1) **SelfImprovementAgent** (`agents/self_improvement.py`): Spawns Claude Code sessions in headless mode, manages git feature branches, streams progress to dashboard via Redis, tracks token usage for API cost comparison. (2) **Safety Boundaries**: Forbidden paths (secrets/, .env), forbidden operations (rm -rf, sudo), safety validation on all operations. (3) **Session Workflow**: Create branch → diagnose issue → propose plan (PLAN block parsing) → await approval → implement → test → await final approval → merge. (4) **Interactive Control**: approve_plan/reject_plan, send_user_input for course correction, stop_session for immediate halt. (5) **Cost Tracking**: TokenUsage class calculates API-equivalent costs for Sonnet/Opus, generates cost comparison reports showing subscription savings. (6) **API Routes** (`/api/v1/self-improve/`): POST /improve (start session), GET /sessions (list), POST /sessions/{id}/approve (commit), POST /sessions/{id}/reject, POST /sessions/{id}/stop, GET /cost-report. (7) **Debug Script** (`scripts/debug-logs.sh`): Shell helper for Claude Code to query activity logs, traces, errors, LLM calls, journal, HA errors. (8) **SSH to Man-of-war**: For GPU service management (Parakeet, Kokoro restart). (9) **Two-Phase Approval**: Phase 1 (diagnosis) runs with DIAGNOSIS_SYSTEM_PROMPT then pauses for plan approval, Phase 2 (implementation) runs IMPLEMENTATION_SYSTEM_PROMPT after approval. (10) **Simplified Dashboard UI**: Single-column layout with status bar, plan approval section, CLI output, commit section - removed sessions sidebar, cost tracking, split thinking/operations views. 690 tests pass (32 new for self-improvement).
- [x] **Self-Improvement Dashboard Logging & Notifications** - Enhanced self-improvement agent with dashboard visibility and HA notifications: (1) **Activity Logging**: New ActivityType enum values (self_improve.start, .diagnosing, .plan_proposed, .plan_approved, .implementing, .testing, .awaiting_approval, .committed, .failed, .stopped). All session lifecycle events now log to ActivityLogger for dashboard conversation log visibility. (2) **Safety Scoring**: SafetyScore dataclass evaluates plan risk (0.0-1.0 scale) based on files affected, safe/risky paths, config-only changes, test inclusion. (3) **Auto-Approve Threshold**: Plans with safety score ≥ 0.80 and no forbidden paths can be auto-approved without user confirmation. Safe paths now include: config/, docs/, prompts/, tests/, .copilot/, __init__.py, .md, .yaml, .yml, pyproject.toml. Single-file changes get +0.1 bonus. Risky paths: main.py, api/routes/, services/homeassistant/, agents/. (4) **HA Notifications**: Sends notifications to `mobile_app_thomphone` when: plan is ready (with safety score), plan is auto-approved, changes are ready to commit, commit is successful. Improved error logging when HA client unavailable. (5) **Lazy HA Client Loading**: Uses `get_ha_client()` from homeassistant routes to avoid import cycles. 690 tests pass.

### In Progress
None

### Not Started (Deferred)

- **Mobile client** — Placeholder at `docs/future/MOBILE_STT_CLIENT.md`
- **Proactive Agent** — Spec only
- **Evolver Agent** — Spec only
- **Speaker ID from voice (ECAPA-TDNN)** — Speaker is from HA user, request, or family profiles
- **Override system** — `config/overrides/` (user, room, schedule); spec only
- **AR, Wearables, ThinkSmart** — Spec / future

> **Docs synced to as-built:** `README.md`, `barnabeenet-project-log.md`, `docs/QUICK_REFERENCE.md`, `docs/architecture.md`, `docs/BarnabeeNet_README_v3.2.md` (roadmap + as-built deviations).

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

1. Mobile app / remote access — Android client with BT audio capture, WebSocket streaming
2. Proactive Agent — Time-based notifications, context-aware suggestions

## Voice Architecture Decision

**Wake word is NOT handled by BarnabeeNet.** Input sources:
- **Phones**: HA built-in assistant → HA Cloud STT → text → BarnabeeNet
- **Tablets/Dashboards**: ViewAssist Companion App (forked) → wake word + audio → BarnabeeNet
- **Dashboard Chat**: Direct text input via web UI (already working)

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
| `barnabeenet-project-log.md` | Phases, decisions, deferred; synced to as-built |
| `docs/QUICK_REFERENCE.md` | Stack, config, latency |
| `docs/architecture.md` | As-built architecture |
| `docs/BarnabeeNet_Pipeline_Management_Dashboard.md` | Pipeline Management Dashboard spec (Phase 7, after HA) |
| `claude-project-rules.md` | Rules for Claude sessions |
| `.github/copilot-instructions.md` | Rules for Copilot agent |
| `.copilot/sessions/` | Session plans and results |
