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
import os
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from nemo.collections.asr.models import ASRModel

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
_model: ASRModel | None = None
_model_lock = asyncio.Lock()


def get_model() -> ASRModel:
    """Get or load the ASR model."""
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
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {e}") from e

    # Load audio - try soundfile first, fall back to ffmpeg for WebM/Opus
    audio_data = None
    sample_rate = 16000

    try:
        audio_buffer = io.BytesIO(audio_bytes)
        audio_data, sample_rate = sf.read(audio_buffer)
        logger.debug(f"Decoded audio with soundfile: {len(audio_data)} samples at {sample_rate}Hz")
    except Exception as sf_error:
        logger.debug(f"soundfile failed ({sf_error}), trying ffmpeg")
        # Try ffmpeg for WebM/Opus and other formats
        try:
            import subprocess
            import tempfile

            # Write input to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                input_path = f.name

            output_path = input_path.replace(".webm", ".wav")

            # Use ffmpeg to convert to WAV (16kHz mono)
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    input_path,
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-f",
                    "wav",
                    output_path,
                ],
                capture_output=True,
                timeout=5,
            )

            if result.returncode != 0:
                raise ValueError(f"ffmpeg failed: {result.stderr.decode()[:200]}")

            # Read the converted WAV
            audio_data, sample_rate = sf.read(output_path)
            logger.debug(f"Decoded audio with ffmpeg: {len(audio_data)} samples at {sample_rate}Hz")

            # Cleanup temp files
            os.unlink(input_path)
            os.unlink(output_path)

        except Exception as ffmpeg_error:
            raise HTTPException(
                status_code=400,
                detail=f"Could not decode audio: soundfile={sf_error}, ffmpeg={ffmpeg_error}",
            ) from ffmpeg_error

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

    # Save to temp file (NeMo requires file path)
    temp_file = f"/tmp/stt_input_{time.time_ns()}.wav"
    sf.write(temp_file, audio_data, sample_rate)

    # Transcribe
    try:
        async with _model_lock:
            model = get_model()
            # Run inference in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: model.transcribe([temp_file]))

        # Extract text from result
        if result and len(result) > 0:
            # Handle different result formats from NeMo
            first_result = result[0]
            if hasattr(first_result, "text"):
                text = first_result.text
            elif isinstance(first_result, str):
                text = first_result
            else:
                text = str(first_result)
        else:
            text = ""

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from e

    finally:
        # Cleanup temp file
        try:
            os.remove(temp_file)
        except OSError:
            pass

    latency_ms = (time.perf_counter() - start_time) * 1000

    logger.info(f"Transcribed {len(audio_data) / sample_rate:.2f}s audio in {latency_ms:.2f}ms")

    return TranscribeResponse(
        text=text,
        confidence=1.0,  # Parakeet doesn't return confidence scores
        latency_ms=latency_ms,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
