"""Test how Barnabee says family names."""
import asyncio
from pathlib import Path

NAME_PHRASES = [
    ("thom", "Good morning, Thom."),
    ("elizabeth", "Good morning, Elizabeth."),
    ("penelope", "Good morning, Penelope."),
    ("viola", "Good morning, Viola."),
    ("xander", "Good morning, Xander."),
    ("zachary", "Good morning, Zachary."),
    ("thom_long", "Thom, you have a meeting at nine o'clock."),
    ("elizabeth_long", "Elizabeth, dinner will be ready in twenty minutes."),
    ("penelope_long", "Penelope, don't forget your soccer practice at four thirty."),
    ("viola_long", "Viola, it's time to start your homework."),
    ("xander_long", "Xander, your friend is at the front door."),
    ("zachary_long", "Zachary, you need to brush your teeth before bed."),
]

async def generate_samples():
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    
    output_dir = Path("voice_samples/names")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Loading Kokoro with British English...")
    pipeline = KPipeline(lang_code='b')
    
    print(f"Generating name samples with bm_fable...\n")
    
    for name, text in NAME_PHRASES:
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
    
    print(f"\nSamples saved to: {output_dir.absolute()}")
    print("Open in Windows: explorer.exe voice_samples/names")

if __name__ == "__main__":
    asyncio.run(generate_samples())
