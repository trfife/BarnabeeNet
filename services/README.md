# Services

This directory contains the microservices that make up BarnabeeNet:

- `core/` - Main BarnabeeNet orchestration service
- `stt/` - Speech-to-text service (Faster-Whisper)
- `tts/` - Text-to-speech service (Piper)
- `speaker-id/` - Speaker recognition service (Pyannote)

Each service is independently deployable as a container.
