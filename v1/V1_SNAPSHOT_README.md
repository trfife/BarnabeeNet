# BarnabeeNet v1.0 Complete Snapshot

This folder contains a complete snapshot of BarnabeeNet v1.0 for reference during v2.0 development.

## Contents

| Folder/File | Description |
|-------------|-------------|
| `BARNABEENET_V1_COMPLETE_HANDOFF.md` | **Complete documentation** - 2,100+ lines covering architecture, build guide, troubleshooting |
| `src/` | All source code (~100 Python files) |
| `tests/` | Test suite (28 test files, ~690 tests) |
| `config/` | YAML configuration files |
| `prompts/` | LLM agent prompts |
| `scripts/` | Deployment and utility scripts |
| `infrastructure/` | Podman/Docker compose files |
| `ha-integration/` | Home Assistant custom component |
| `docs/` | Additional documentation |
| `workers/` | GPU worker code |
| `requirements.txt` | Python dependencies (VM) |
| `requirements-gpu.txt` | GPU worker dependencies (WSL) |
| `.env.example` | Environment variable template |

## How to Use This

1. **Read the handoff document first**: `BARNABEENET_V1_COMPLETE_HANDOFF.md`
2. **Reference specific implementations**: Browse `src/barnabeenet/`
3. **Check patterns**: `src/barnabeenet/agents/meta.py` has all 378 intent patterns
4. **Review configs**: `config/llm.yaml`, `config/routing.yaml`, `config/patterns.yaml`

## Key Files by Purpose

### Intent Classification
- `src/barnabeenet/agents/meta.py` - MetaAgent with all patterns
- `config/patterns.yaml` - Pattern definitions (YAML format)
- `tests/test_intent_coverage.py` - AI-generated test suite

### Device Control
- `src/barnabeenet/agents/action.py` - ActionAgent
- `src/barnabeenet/services/homeassistant/` - HA integration

### LLM Configuration
- `config/llm.yaml` - Model assignments per activity
- `src/barnabeenet/prompts/` - Agent system prompts

### Speech
- `workers/gpu_stt_worker.py` - Parakeet STT on GPU
- `src/barnabeenet/services/tts/` - Kokoro TTS

## Snapshot Date

January 23, 2026

## Repository

https://github.com/trfife/BarnabeeNet
