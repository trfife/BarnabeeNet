# Session Results: GPU Worker Setup (Parakeet TDT)

**Date:** 2026-01-17
**Duration:** ~45 minutes
**Status:** ✅ COMPLETE (with network limitation noted)

---

## Summary

Successfully set up Parakeet TDT 0.6B v2 GPU worker on Man-of-war WSL with RTX 4070 Ti. Achieved **45ms latency** (target was <50ms) - a **53x speedup** over CPU-based Distil-Whisper (2,400ms).

---

## Environment Discovery Results

| Check | Result |
|-------|--------|
| nvidia-smi Driver | 591.74 (Windows) |
| nvidia-smi CUDA | 13.1 |
| GPU Model | NVIDIA GeForce RTX 4070 Ti ✅ |
| nvcc installed | No (not needed) |
| Python version | 3.12.3 |
| PyTorch installed | Now yes (2.6.0+cu124) |
| PyTorch CUDA | Yes, CUDA 12.4 |

---

## Installation Summary

### Phase B: CUDA Toolkit
**SKIPPED** - Not needed. PyTorch bundles its own CUDA runtime.

### Phase C: Python Environment
- Created `.venv-gpu/` (separate from main `.venv/`)
- Installed PyTorch 2.6.0+cu124 (~2.8GB)
- Verified `torch.cuda.is_available() == True`

### Phase D: NeMo + Parakeet
- Installed system deps: `libsndfile1`, `ffmpeg`
- Installed `nemo_toolkit[asr]` (~5GB with dependencies)
- Downloaded Parakeet TDT 0.6B v2 model (~2.5GB)

### Phase E: FastAPI Worker
- Created `workers/gpu_stt_worker.py`
- Created `workers/__init__.py`
- Endpoints:
  - `GET /health` - Returns GPU status, memory usage
  - `POST /transcribe` - Accepts base64-encoded audio, returns text

---

## Performance Results

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| STT Latency (GPU) | **45ms** | <50ms | ✅ PASS |
| STT Latency (CPU) | 2,400ms | N/A | Baseline |
| Speedup | **53x** | N/A | Excellent |
| Model Load Time | ~9s | N/A | Acceptable |
| Warm-up Time | ~3s | N/A | First inference |
| GPU Memory | ~2.4GB | <12GB | ✅ OK |

---

## Network Accessibility

| Test | Result |
|------|--------|
| localhost:8001 | ✅ Working |
| VM → WSL (172.31.x.x) | ❌ Failed (NAT) |
| VM → Windows (192.168.86.100:8001) | ❌ Needs port forwarding |

**Root Cause:** WSL2 uses NAT networking. The GPU worker binds to WSL's internal network (172.31.x.x) which is not directly accessible from the LAN.

**Solution:** Configure Windows port forwarding (documented in CONTEXT.md).

---

## Files Created/Modified

### Created
- `workers/__init__.py` - Package init
- `workers/gpu_stt_worker.py` - FastAPI GPU STT service (~200 lines)
- `.copilot/sessions/session-2026-01-18-gpu-worker-results.md` - This file

### Modified
- `CONTEXT.md` - Updated with GPU worker status, performance, next steps

---

## How to Use

### Start the GPU Worker
```bash
cd ~/projects/barnabeenet
source .venv-gpu/bin/activate
screen -dmS gpu_worker python -m uvicorn workers.gpu_stt_worker:app --host 0.0.0.0 --port 8001
```

### Check Status
```bash
curl http://localhost:8001/health | python3 -m json.tool
```

### Transcribe Audio
```python
import base64
import httpx

# audio_bytes = your WAV file bytes
audio_b64 = base64.b64encode(audio_bytes).decode()
response = httpx.post(
    'http://localhost:8001/transcribe',
    json={'audio_base64': audio_b64},
    timeout=60.0
)
print(response.json())  # {'text': '...', 'latency_ms': 45.2, ...}
```

---

## Next Steps

1. **Configure WSL2 port forwarding** for VM access
2. **Implement STT Router** (GPU primary, CPU fallback)
3. Add startup script for GPU worker
4. Integration tests

---

## Lessons Learned

1. **PyTorch bundles CUDA** - No need to install CUDA toolkit separately for inference
2. **WSL2 NAT networking** - External access requires Windows port forwarding
3. **NeMo warm-up** - First inference is slow (~3s), subsequent are fast (~45ms)
4. **Separate venvs** - GPU worker has heavy deps, isolate from main project
