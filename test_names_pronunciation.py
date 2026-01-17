"""Test different pronunciations of Viola and Xander."""
import asyncio
from pathlib import Path

PRONUNCIATION_TESTS = [
    # Viola variations
    ("viola_v1", "Good morning, Viola."),
    ("viola_v2", "Good morning, Vyola."),
    ("viola_v3", "Good morning, Vy-ola."),
    ("viola_v4", "Good morning, Vye-ola."),
    ("viola_v5", "Good morning, Vyeola."),
    ("viola_v6", "Good morning, Vaiola."),
    
    # Xander variations
    ("xander_v1", "Good morning, Xander."),
    ("xander_v2", "Good morning, Zander."),
    ("xander_v3", "Good morning, Ksander."),
    ("xander_v4", "Good morning,Eksander."),
    ("xander_v5", "Good morning, X-ander."),
]

async def generate_samples():
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    
    output_dir = Path("voice_samples/pronunciation_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pipeline = KPipeline(lang_code='b')
    
    print("Testing pronunciations with bm_fable...\n")
    
    for name, text in PRONUNCIATION_TESTS:
        try:
            audio_chunks = []
            for _, _, audio in pipeline(text, voice='bm_fable', speed=1.0):
                audio_chunks.append(audio)
            
            if audio_chunks:
                full_audio = np.concatenate(audio_chunks)
                filename = output_dir / f"{name}.wav"
                sf.write(filename, full_audio, 24000)
                print(f"  ✓ {name}: \"{text}\"")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    
    print(f"\nOpen: explorer.exe voice_samples/pronunciation_test")

if __name__ == "__main__":
    asyncio.run(generate_samples())
