"""TTS (Text-to-Speech) services."""

from barnabeenet.services.tts.kokoro_tts import KokoroTTS
from barnabeenet.services.tts.pronunciation import PRONUNCIATION_MAP, preprocess_text

__all__ = ["KokoroTTS", "PRONUNCIATION_MAP", "preprocess_text"]
