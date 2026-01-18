"""BarnabeeNet Configuration Management.

Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None

    @property
    def url(self) -> str:
        """Build Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class STTSettings(BaseSettings):
    """Speech-to-Text settings."""

    model_config = SettingsConfigDict(env_prefix="STT_")

    # Primary engine selection
    primary_engine: Literal["parakeet", "distil-whisper"] = "parakeet"
    fallback_engine: Literal["distil-whisper"] = "distil-whisper"

    # Distil-Whisper settings (CPU fallback)
    whisper_model: str = "distil-small.en"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_beam_size: int = 1

    # GPU Worker settings (Parakeet on Man-of-war)
    gpu_worker_host: str = "192.168.86.100"
    gpu_worker_port: int = 8001
    gpu_worker_timeout_ms: int = 100
    gpu_worker_health_interval_sec: int = 3


class TTSSettings(BaseSettings):
    """Text-to-Speech settings (Kokoro)."""

    model_config = SettingsConfigDict(env_prefix="TTS_")

    engine: Literal["kokoro"] = "kokoro"
    voice: str = "bm_fable"
    speed: float = 1.0
    sample_rate: int = 24000


class AudioSettings(BaseSettings):
    """Audio processing settings."""

    model_config = SettingsConfigDict(env_prefix="AUDIO_")

    # Input format (what we expect from clients)
    input_sample_rate: int = 16000
    input_channels: int = 1

    # Output format (what we send to clients)
    output_sample_rate: int = 24000
    output_format: Literal["wav", "mp3", "ogg"] = "wav"

    # Voice Activity Detection
    vad_aggressiveness: int = Field(default=2, ge=0, le=3)
    vad_frame_duration_ms: Literal[10, 20, 30] = 30


class PerformanceSettings(BaseSettings):
    """Performance tuning settings."""

    model_config = SettingsConfigDict(env_prefix="PERF_")

    # Concurrency limits
    max_concurrent_stt: int = 4
    max_concurrent_tts: int = 4

    # Timeouts
    stt_timeout_ms: int = 5000
    tts_timeout_ms: int = 3000

    # Caching
    tts_cache_max_size: int = 100


class LLMSettings(BaseSettings):
    """LLM/OpenRouter settings for agent system."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    # OpenRouter API
    openrouter_api_key: str = ""
    openrouter_site_url: str = "https://barnabeenet.local"
    openrouter_site_name: str = "BarnabeeNet"

    # Model defaults per agent type (can be overridden in YAML config)
    meta_model: str = "deepseek/deepseek-chat"
    meta_temperature: float = 0.3
    meta_max_tokens: int = 200

    instant_model: str = "deepseek/deepseek-chat"
    instant_temperature: float = 0.5
    instant_max_tokens: int = 300

    action_model: str = "openai/gpt-4o-mini"
    action_temperature: float = 0.3
    action_max_tokens: int = 500

    interaction_model: str = "anthropic/claude-3.5-sonnet"
    interaction_temperature: float = 0.7
    interaction_max_tokens: int = 1500

    memory_model: str = "openai/gpt-4o-mini"
    memory_temperature: float = 0.3
    memory_max_tokens: int = 800

    # Signal logging
    signal_retention_days: int = 30
    signal_stream_max_len: int = 10000


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="BARNABEENET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    env: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # API Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Data directories
    data_dir: Path = Path.home() / "data" / "barnabeenet"
    models_dir: Path = Path.home() / "data" / "models"

    # Nested settings
    redis: RedisSettings = Field(default_factory=RedisSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @field_validator("data_dir", "models_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Expand ~ in paths."""
        return Path(v).expanduser()

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        (self.models_dir / "whisper").mkdir(exist_ok=True)
        (self.models_dir / "kokoro").mkdir(exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure settings are loaded once and reused.
    """
    settings = Settings()
    settings.ensure_directories()
    return settings
