"""Generate samples from all Kokoro voices for comparison."""
import asyncio
from pathlib import Path

TEST_TEXT = "Good morning! The temperature is twenty-two degrees and partly cloudy."

VOICES_TO_TEST = {
    'a': [
        'af_bella', 'af_heart', 'af_nicole', 'af_sarah', 'af_sky',
        'af_alloy', 'af_aoede', 'af_nova', 'af_river',
        'am_adam', 'am_echo', 'am_eric', 'am_michael', 'am_onyx', 'am_puck',
    ],
    'b': [
        'bf_alice', 'bf_emma', 'bf_isabella', 'bf_lily',
        'bm_daniel', 'bm_fable', 'bm_george', 'bm_lewis',
    ],
}

async def generate_samples():
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    
    output_dir = Path("voice_samples")
    output_dir.mkdir(exist_ok=True)
    
    print(f"Generating samples for: \"{TEST_TEXT}\"\n")
    
    for lang_code, voices in VOICES_TO_TEST.items():
        lang_name = "American" if lang_code == 'a' else "British"
        print(f"\n--- {lang_name} English ---")
        
        try:
            pipeline = KPipeline(lang_code=lang_code)
        except Exception as e:
            print(f"  Failed to load pipeline: {e}")
            continue
        
        for voice in voices:
            try:
                audio_chunks = []
                for _, _, audio in pipeline(TEST_TEXT, voice=voice, speed=1.0):
                    audio_chunks.append(audio)
                
                if audio_chunks:
                    full_audio = np.concatenate(audio_chunks)
                    filename = output_dir / f"{voice}.wav"
                    sf.write(filename, full_audio, 24000)
                    duration = len(full_audio) / 24000
                    print(f"  ✓ {voice}: {duration:.1f}s")
                else:
                    print(f"  ✗ {voice}: No audio generated")
            except Exception as e:
                print(f"  ✗ {voice}: {e}")
    
    print(f"\n\nSamples saved to: {output_dir.absolute()}")
    print("Open in Windows: explorer.exe .")

if __name__ == "__main__":
    asyncio.run(generate_samples())
