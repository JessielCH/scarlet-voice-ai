import os
import json
import pyaudio
import asyncio
from vosk import Model, KaldiRecognizer
from dotenv import load_dotenv

import scarlet_core

async def run_wake_word_loop():
    print("⏳ Initializing offline Vosk model... (This takes a few seconds)")
    # Loads the small English model we just downloaded automatically
    model = Model(lang="en-us")
    recognizer = KaldiRecognizer(model, 16000)
    
    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=4000
    )
    
    print("\n" + "="*50)
    print("🎙️  SCARLET WAKE WORD ENGINE STARTED")
    print("👂 Listening continuously in background (No API Key needed)...")
    print("🗣️  Say 'Scarlet' to wake up the assistant.")
    print("="*50 + "\n")
    
    audio_stream.start_stream()
    
    try:
        while True:
            data = audio_stream.read(4000, exception_on_overflow=False)
            
            # When AcceptWaveform returns True, a sentence was fully spoken
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower()
                
                if "scarlet" in text:
                    print(f"\n🔔 Wake word detected! You said: '{text}'")
                    
                    # Pause background listening
                    audio_stream.stop_stream()
                    
                    # Hand over control to Scarlet's main logic
                    await scarlet_core.main()
                    
                    # After Scarlet finishes, reset the recognizer and resume
                    recognizer.Reset()
                    print("\n👂 Resuming background listening... Say 'Scarlet' again.")
                    audio_stream.start_stream()
                    
    except KeyboardInterrupt:
        print("\nStopping Scarlet...")
    finally:
        audio_stream.close()
        pa.terminate()

if __name__ == "__main__":
    asyncio.run(run_wake_word_loop())
