"""STT (Speech-to-Text) services."""

from barnabeenet.services.stt.distil_whisper import DistilWhisperSTT
from barnabeenet.services.stt.router import STTBackend, STTResult, STTRouter

__all__ = ["DistilWhisperSTT", "STTBackend", "STTResult", "STTRouter"]
