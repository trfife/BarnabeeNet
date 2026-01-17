# Services

This directory contains the microservices that make up BarnabeeNet:

- `core/` - Main BarnabeeNet orchestration service (includes Kokoro TTS in-process)
- `stt/` - Speech-to-text service
  - **CPU (Beelink)**: Distil-Whisper via faster-whisper
  - **GPU (Man-of-war)**: Parakeet TDT 0.6B v2
- `speaker-id/` - Speaker recognition service (ECAPA-TDNN via SpeechBrain)

Each service is independently deployable. TTS (Kokoro) runs in-process with core for lower latency.
