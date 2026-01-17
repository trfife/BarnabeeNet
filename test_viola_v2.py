"""More Viola pronunciation variations."""
import asyncio
from pathlib import Path

VIOLA_TESTS = [
    # More V variations
    ("viola_01", "Good morning, Viola."),
    ("viola_02", "Good morning, Vyola."),
    ("viola_03", "Good morning, Veye-ola."),
    ("viola_04", "Good morning, V-eye-ola."),
    ("viola_05", "Good morning, Viyola."),
    ("viola_06", "Good morning, Vie-ola."),
    ("viola_07", "Good morning, Vee-eye-ola."),
    ("viola_08", "Good morning, Vai-ola."),
    ("viola_09", "Good morning, Vai-oh-la."),
    ("viola_10", "Good morning, Vy-oh-la."),
    
    # Different sentence contexts
    ("viola_11", "Vyola, dinner is ready."),
    ("viola_12", "Hey Vyola!"),
    ("viola_13", "Time for bed, Vyola."),
    ("viola_14", "I love you, Vyola."),
    
    # Emphasize the V with a pause
    ("viola_15", "Good morning. Vyola."),
    ("viola_16", "Hello, Vyola dear."),
]

async def generate_samples():
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    
    output_dir = Path("voice_samples/viola_test2")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pipeline = KPipeline(lang_code='b')
    
    print("Testing more Viola pronunciations...\n")
    
    for name, text in VIOLA_TESTS:
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
    
    print(f"\nOpen: explorer.exe voice_samples/viola_test2")

if __name__ == "__main__":
    asyncio.run(generate_samples())
