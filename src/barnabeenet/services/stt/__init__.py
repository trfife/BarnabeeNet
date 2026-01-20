"""STT (Speech-to-Text) services."""

from barnabeenet.services.stt.azure_stt import AzureSTT, AzureSTTConfig, get_azure_stt
from barnabeenet.services.stt.router import (
    StreamingSTTResult,
    STTBackend,
    STTResult,
    STTRouter,
)

# Lazy import for DistilWhisperSTT to avoid numpy import at module load time
# This allows the server to start even on systems where numpy fails
_distil_whisper_stt = None


def get_distil_whisper_class():
    """Lazily import DistilWhisperSTT."""
    global _distil_whisper_stt
    if _distil_whisper_stt is None:
        try:
            from barnabeenet.services.stt.distil_whisper import DistilWhisperSTT

            _distil_whisper_stt = DistilWhisperSTT
        except ImportError as e:
            import logging

            logging.warning(f"DistilWhisperSTT not available: {e}")
            _distil_whisper_stt = None
    return _distil_whisper_stt


# For backwards compatibility, provide DistilWhisperSTT as a lazy attribute
def __getattr__(name):
    if name == "DistilWhisperSTT":
        return get_distil_whisper_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AzureSTT",
    "AzureSTTConfig",
    "DistilWhisperSTT",
    "STTBackend",
    "STTResult",
    "STTRouter",
    "StreamingSTTResult",
    "get_azure_stt",
    "get_distil_whisper_class",
]
