# Session: GPU Worker Setup (Parakeet TDT)

**Date:** 2026-01-18
**Goal:** Set up Parakeet TDT 0.6B v2 GPU worker on Man-of-war WSL
**Output:** `.copilot/sessions/session-2026-01-18-gpu-worker-results.md`

---

## Current State

- STT (CPU): Working, ~2.4s latency (too slow for real-time)
- TTS: Working, 232-537ms latency
- GPU Worker: **NOT SET UP** ← This session
- Target: <50ms STT latency with GPU

## Environment

| Machine | Role | IP |
|---------|------|-----|
| Man-of-war (WSL) | GPU Worker host | 192.168.86.100 |
| BarnabeeNet VM | Runtime server | 192.168.86.51 |

---

## Phase A: Environment Discovery

**Goal:** Understand current CUDA/GPU state before installing anything.

### Tasks

1. [ ] Check Windows NVIDIA driver version:
   ```bash
   nvidia-smi
   ```
   Record: Driver version, CUDA version shown, GPU model

2. [ ] Check if CUDA toolkit is installed in WSL:
   ```bash
   nvcc --version 2>/dev/null || echo "CUDA toolkit not installed"
   ls /usr/local/cuda* 2>/dev/null || echo "No CUDA directories found"
   ```

3. [ ] Check Python version:
   ```bash
   python3 --version
   ```

4. [ ] Check if PyTorch with CUDA is already available:
   ```bash
   python3 -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}')" 2>/dev/null || echo "PyTorch not installed or no CUDA"
   ```

5. [ ] Check existing venvs in project:
   ```bash
   ls -la ~/projects/barnabeenet/.venv* 2>/dev/null || echo "No venvs found"
   ```

### ⏸️ PAUSE POINT 1
**Stop and report findings to user.** The installation path depends on what's already present.

Format your report as:
```
## Environment Discovery Results

| Check | Result |
|-------|--------|
| nvidia-smi Driver | X.X |
| nvidia-smi CUDA | X.X |
| GPU Model | RTX 4070 Ti (expected) |
| nvcc installed | Yes/No |
| CUDA toolkit path | /path or None |
| Python version | 3.X.X |
| PyTorch installed | Yes/No |
| PyTorch CUDA | Yes/No |
| Existing venv | path or None |

**Recommended next steps:** [based on findings]
```

---

## Phase B: CUDA Toolkit Setup (if needed)

**Skip this phase if `nvcc --version` already works with CUDA 12.x**

### Tasks

6. [ ] Install CUDA Toolkit for WSL-Ubuntu:
   ```bash
   # Download and install CUDA toolkit (WSL-Ubuntu specific)
   # Check https://developer.nvidia.com/cuda-downloads for latest
   # Select: Linux > x86_64 > WSL-Ubuntu > 2.0 > deb (network)
   
   wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
   sudo dpkg -i cuda-keyring_1.1-1_all.deb
   sudo apt-get update
   sudo apt-get -y install cuda-toolkit-12-6
   ```
   
   **IMPORTANT:** Do NOT install cuda-drivers - WSL uses Windows drivers.

7. [ ] Add CUDA to PATH (add to ~/.bashrc):
   ```bash
   echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
   echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
   source ~/.bashrc
   ```

8. [ ] Verify CUDA installation:
   ```bash
   nvcc --version
   ```

---

## Phase C: Python Environment Setup

### Tasks

9. [ ] Create dedicated GPU venv:
   ```bash
   cd ~/projects/barnabeenet
   python3 -m venv .venv-gpu
   source .venv-gpu/bin/activate
   pip install --upgrade pip wheel setuptools
   ```

10. [ ] Install PyTorch with CUDA:
    ```bash
    # Check https://pytorch.org/get-started/locally/ for latest command
    # For CUDA 12.x:
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
    ```

11. [ ] Verify PyTorch CUDA:
    ```bash
    python -c "
    import torch
    print(f'PyTorch version: {torch.__version__}')
    print(f'CUDA available: {torch.cuda.is_available()}')
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\"}')
    "
    ```
    
    **Expected:** CUDA available: True, GPU: NVIDIA GeForce RTX 4070 Ti

### ⏸️ PAUSE POINT 2 (if PyTorch CUDA fails)
If `torch.cuda.is_available()` returns False, stop and report the error.

---

## Phase D: NeMo + Parakeet Installation

### Tasks

12. [ ] Install system dependencies:
    ```bash
    sudo apt-get update
    sudo apt-get install -y libsndfile1 ffmpeg
    ```

13. [ ] Install NeMo ASR toolkit:
    ```bash
    source ~/projects/barnabeenet/.venv-gpu/bin/activate
    pip install Cython packaging
    pip install nemo_toolkit['asr']
    ```
    
    **Note:** This may take 5-10 minutes and download ~1GB of dependencies.

14. [ ] Download and test Parakeet model:
    ```bash
    python -c "
    import nemo.collections.asr as nemo_asr
    print('Loading Parakeet TDT 0.6B v2...')
    model = nemo_asr.models.ASRModel.from_pretrained('nvidia/parakeet-tdt-0.6b-v2')
    print(f'Model loaded successfully!')
    print(f'Model type: {type(model).__name__}')
    "
    ```
    
    **Note:** First run downloads ~600MB model file.

15. [ ] Run inference test with timing:
    ```bash
    python -c "
    import nemo.collections.asr as nemo_asr
    import time
    import numpy as np
    import soundfile as sf
    
    # Load model
    print('Loading model...')
    model = nemo_asr.models.ASRModel.from_pretrained('nvidia/parakeet-tdt-0.6b-v2')
    model = model.cuda()
    
    # Create test audio (5 seconds of silence + tone)
    sample_rate = 16000
    duration = 5.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
    test_file = '/tmp/test_audio.wav'
    sf.write(test_file, audio, sample_rate)
    
    # Warm-up run
    print('Warm-up inference...')
    _ = model.transcribe([test_file])
    
    # Timed run
    print('Timed inference...')
    start = time.perf_counter()
    result = model.transcribe([test_file])
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f'Transcription: {result[0]}')
    print(f'Latency: {elapsed_ms:.2f}ms')
    print(f'Target: <50ms')
    print(f'Status: {\"✅ PASS\" if elapsed_ms < 50 else \"⚠️ Above target but may be acceptable\"}')"
    ```

### ⏸️ PAUSE POINT 3
**Report latency results to user.** If latency is >100ms, there may be an issue.

---

## Phase E: FastAPI GPU Worker

### Tasks

16. [ ] Install FastAPI dependencies in GPU venv:
    ```bash
    source ~/projects/barnabeenet/.venv-gpu/bin/activate
    pip install fastapi uvicorn python-multipart httpx
    ```

17. [ ] Create GPU worker file at `workers/gpu_stt_worker.py`:

```python
"""
GPU STT Worker - Parakeet TDT 0.6B v2
Runs on Man-of-war (RTX 4070 Ti) for fast speech-to-text.

Usage:
    source .venv-gpu/bin/activate
    uvicorn workers.gpu_stt_worker:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranscribeRequest(BaseModel):
    """Request model for transcription."""
    audio_base64: str
    language: str = "en"


class TranscribeResponse(BaseModel):
    """Response model for transcription."""
    text: str
    confidence: float
    latency_ms: float
    model: str = "nvidia/parakeet-tdt-0.6b-v2"


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    model_loaded: bool
    gpu_available: bool
    gpu_name: str | None
    gpu_memory_used_mb: float | None
    gpu_memory_total_mb: float | None


# Global model instance
_model = None
_model_lock = asyncio.Lock()


def get_model():
    """Get or load the ASR model."""
    global _model
    if _model is None:
        raise RuntimeError("Model not loaded. Wait for startup to complete.")
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, cleanup on shutdown."""
    global _model
    
    logger.info("Starting GPU STT Worker...")
    logger.info(f"PyTorch version: {torch.__version__}")
    logger.info(f"CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA version: {torch.version.cuda}")
    
    # Load model
    logger.info("Loading Parakeet TDT 0.6B v2...")
    start = time.perf_counter()
    
    import nemo.collections.asr as nemo_asr
    _model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
    
    if torch.cuda.is_available():
        _model = _model.cuda()
        logger.info("Model moved to GPU")
    
    load_time = time.perf_counter() - start
    logger.info(f"Model loaded in {load_time:.2f}s")
    
    # Warm-up inference
    logger.info("Running warm-up inference...")
    sample_rate = 16000
    dummy_audio = np.zeros(sample_rate, dtype=np.float32)  # 1 second silence
    dummy_file = "/tmp/warmup.wav"
    sf.write(dummy_file, dummy_audio, sample_rate)
    _ = _model.transcribe([dummy_file])
    logger.info("Warm-up complete. Ready to serve requests.")
    
    yield
    
    # Cleanup
    logger.info("Shutting down GPU STT Worker...")
    _model = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = FastAPI(
    title="BarnabeeNet GPU STT Worker",
    description="Parakeet TDT 0.6B v2 speech-to-text service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint for routing decisions."""
    gpu_available = torch.cuda.is_available()
    gpu_name = None
    gpu_memory_used = None
    gpu_memory_total = None
    
    if gpu_available:
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory_used = torch.cuda.memory_allocated(0) / 1024 / 1024
        gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / 1024 / 1024
    
    return HealthResponse(
        status="healthy" if _model is not None else "loading",
        model_loaded=_model is not None,
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        gpu_memory_used_mb=gpu_memory_used,
        gpu_memory_total_mb=gpu_memory_total,
    )


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(request: TranscribeRequest) -> TranscribeResponse:
    """Transcribe audio using Parakeet TDT."""
    start_time = time.perf_counter()
    
    # Decode audio
    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {e}")
    
    # Load audio
    try:
        audio_buffer = io.BytesIO(audio_bytes)
        audio_data, sample_rate = sf.read(audio_buffer)
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)
        
        # Ensure float32
        audio_data = audio_data.astype(np.float32)
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            import torchaudio.functional as F
            audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
            audio_tensor = F.resample(audio_tensor, sample_rate, 16000)
            audio_data = audio_tensor.squeeze().numpy()
            sample_rate = 16000
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio format: {e}")
    
    # Save to temp file (NeMo requires file path)
    temp_file = f"/tmp/stt_input_{time.time_ns()}.wav"
    sf.write(temp_file, audio_data, sample_rate)
    
    # Transcribe
    try:
        async with _model_lock:
            model = get_model()
            # Run inference in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: model.transcribe([temp_file])
            )
        
        text = result[0] if result else ""
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    
    finally:
        # Cleanup temp file
        import os
        try:
            os.remove(temp_file)
        except:
            pass
    
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    logger.info(f"Transcribed {len(audio_data)/sample_rate:.2f}s audio in {latency_ms:.2f}ms")
    
    return TranscribeResponse(
        text=text,
        confidence=1.0,  # Parakeet doesn't return confidence scores
        latency_ms=latency_ms,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

18. [ ] Create `workers/__init__.py`:
    ```bash
    touch ~/projects/barnabeenet/workers/__init__.py
    ```

19. [ ] Test the worker locally:
    ```bash
    cd ~/projects/barnabeenet
    source .venv-gpu/bin/activate
    
    # Start worker in background
    uvicorn workers.gpu_stt_worker:app --host 0.0.0.0 --port 8001 &
    WORKER_PID=$!
    
    # Wait for startup
    sleep 30
    
    # Test health endpoint
    curl http://localhost:8001/health
    
    # Test transcription (using test file if available, or create one)
    python -c "
    import base64
    import httpx
    import numpy as np
    import soundfile as sf
    import io
    
    # Create test audio
    sample_rate = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
    
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format='WAV')
    audio_b64 = base64.b64encode(buffer.getvalue()).decode()
    
    response = httpx.post(
        'http://localhost:8001/transcribe',
        json={'audio_base64': audio_b64},
        timeout=60.0
    )
    print(response.json())
    "
    
    # Stop worker
    kill $WORKER_PID
    ```

---

## Phase F: Network Accessibility Test

### Tasks

20. [ ] Start worker and test from another machine:
    ```bash
    cd ~/projects/barnabeenet
    source .venv-gpu/bin/activate
    
    # Start worker (foreground for logs)
    uvicorn workers.gpu_stt_worker:app --host 0.0.0.0 --port 8001
    ```

21. [ ] From BarnabeeNet VM (192.168.86.51), test connectivity:
    ```bash
    ssh thom@192.168.86.51 "curl -s http://192.168.86.100:8001/health | jq"
    ```

### ⏸️ PAUSE POINT 4 (if network test fails)
If the VM cannot reach Man-of-war:8001, check:
- Windows Firewall rules
- WSL network configuration
- Verify Man-of-war's IP is still 192.168.86.100

---

## Phase G: Commit and Update Context

### Tasks

22. [ ] Run validation:
    ```bash
    cd ~/projects/barnabeenet
    ./scripts/validate.sh
    ```

23. [ ] Git commit:
    ```bash
    git add workers/
    git commit -m "feat: Add GPU STT worker with Parakeet TDT 0.6B v2

- FastAPI worker at workers/gpu_stt_worker.py
- Runs on Man-of-war RTX 4070 Ti via WSL
- Endpoints: /health, /transcribe
- Target latency: <50ms (vs 2400ms CPU fallback)"
    
    git push
    ```

24. [ ] Update CONTEXT.md:
    - Change GPU Worker status from "NOT YET SET UP" to "Working"
    - Add latency measurement to STT/TTS Performance Baseline
    - Update Next Steps (remove GPU worker, add STT Router as next)

25. [ ] Write results file to `.copilot/sessions/session-2026-01-18-gpu-worker-results.md`

---

## Success Criteria

- [ ] `nvidia-smi` shows GPU during inference
- [ ] Transcription latency <50ms for 5s audio
- [ ] Health endpoint returns `{"status": "healthy", "model_loaded": true}`
- [ ] Worker accessible from 192.168.86.51
- [ ] Code committed to GitHub
- [ ] CONTEXT.md updated

---

## Troubleshooting

### "CUDA out of memory"
```bash
# Check GPU memory usage
nvidia-smi

# Clear cache
python -c "import torch; torch.cuda.empty_cache()"
```

### Worker not accessible from VM
```bash
# On Man-of-war, check if port is listening
netstat -tlnp | grep 8001

# Check Windows Firewall (in PowerShell as Admin)
New-NetFirewallRule -DisplayName "WSL GPU Worker" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow
```

### NeMo installation fails
```bash
# Try installing in a fresh venv
rm -rf .venv-gpu
python3 -m venv .venv-gpu
source .venv-gpu/bin/activate
pip install --upgrade pip wheel setuptools
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install nemo_toolkit['asr']
```

### Model download fails
```bash
# Manual download
huggingface-cli download nvidia/parakeet-tdt-0.6b-v2

# Or set cache directory
export HF_HOME=~/projects/barnabeenet/.cache/huggingface
```
