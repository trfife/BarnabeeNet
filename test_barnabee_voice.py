"""Generate Barnabee voice samples using bm_fable."""
import asyncio
from pathlib import Path

BARNABEE_PHRASES = [
    # Confirmations
    ("yes", "Yes."),
    ("no", "No."),
    ("ok", "Okay."),
    ("done", "Done."),
    ("sure", "Sure thing."),
    ("got_it", "Got it."),
    
    # Lights
    ("lights_on", "Turning on the lights."),
    ("lights_off", "Turning off the lights."),
    ("lights_dimmed", "I've dimmed the lights to fifty percent."),
    ("all_lights_off", "All lights have been turned off."),
    
    # Temperature
    ("temp_set", "I've set the temperature to seventy-two degrees."),
    ("temp_current", "It's currently sixty-eight degrees inside, and forty-five degrees outside."),
    
    # Errors and clarification
    ("not_found", "I can't find that. Could you try again?"),
    ("didnt_understand", "Sorry, I couldn't quite catch that. Could you please repeat?"),
    ("cant_do", "I'm sorry, I'm not able to do that."),
    ("no_device", "I couldn't find that device. Make sure it's connected."),
    
    # Greetings
    ("good_morning", "Good morning! It's a beautiful day. The temperature is eighteen degrees and sunny."),
    ("good_night", "Good night! I've locked the doors and turned off the downstairs lights."),
    ("welcome_home", "Welcome home! The house is set to twenty-one degrees and dinner should be ready soon."),
    
    # Family specific
    ("reminder_penelope", "Reminder: Penelope has soccer practice at four thirty."),
    ("reminder_xander", "Xander, don't forget your homework is due tomorrow."),
    ("bedtime_kids", "It's almost bedtime. You've got fifteen minutes to wrap up."),
    
    # Helpful responses
    ("checking", "Let me check on that for you."),
    ("one_moment", "One moment please."),
    ("here_you_go", "Here you go."),
    ("anything_else", "Is there anything else I can help you with?"),
    
    # Longer conversational
    ("weather_report", "Today will be partly cloudy with a high of twenty-three degrees. There's a thirty percent chance of rain this afternoon, so you might want to grab an umbrella."),
    ("schedule_summary", "You have three meetings today. The first one starts at nine with the product team, then lunch with Sarah at noon, and a dentist appointment at three thirty."),
]

async def generate_samples():
    from kokoro import KPipeline
    import soundfile as sf
    import numpy as np
    
    output_dir = Path("voice_samples/barnabee")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Loading Kokoro with British English...")
    pipeline = KPipeline(lang_code='b')
    
    print(f"Generating {len(BARNABEE_PHRASES)} Barnabee samples with bm_fable...\n")
    
    for name, text in BARNABEE_PHRASES:
        try:
            audio_chunks = []
            for _, _, audio in pipeline(text, voice='bm_fable', speed=1.0):
                audio_chunks.append(audio)
            
            if audio_chunks:
                full_audio = np.concatenate(audio_chunks)
                filename = output_dir / f"{name}.wav"
                sf.write(filename, full_audio, 24000)
                duration = len(full_audio) / 24000
                print(f"  ✓ {name}: \"{text[:50]}{'...' if len(text) > 50 else ''}\" ({duration:.1f}s)")
            else:
                print(f"  ✗ {name}: No audio")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    
    print(f"\n\nSamples saved to: {output_dir.absolute()}")
    print("Open in Windows: explorer.exe voice_samples/barnabee")

if __name__ == "__main__":
    asyncio.run(generate_samples())
