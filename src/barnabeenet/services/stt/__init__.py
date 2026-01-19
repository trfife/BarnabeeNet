"""STT (Speech-to-Text) services."""

from barnabeenet.services.stt.azure_stt import AzureSTT, AzureSTTConfig, get_azure_stt
from barnabeenet.services.stt.distil_whisper import DistilWhisperSTT
from barnabeenet.services.stt.router import (
    StreamingSTTResult,
    STTBackend,
    STTResult,
    STTRouter,
)

__all__ = [
    "AzureSTT",
    "AzureSTTConfig",
    "DistilWhisperSTT",
    "STTBackend",
    "STTResult",
    "STTRouter",
    "StreamingSTTResult",
    "get_azure_stt",
]
