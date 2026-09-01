import os
import struct
import pyaudio
import pvporcupine
import asyncio
from dotenv import load_dotenv

# Import our core logic
import scarlet_core

def setup_porcupine():
    load_dotenv()
    access_key = os.getenv("PICOVOICE_API_KEY")
    
    if not access_key or access_key == "your_picovoice_api_key_here":
        print("❌ ERROR: Please set your PICOVOICE_API_KEY in the .env file.")
        print("Get a free key at https://console.picovoice.ai")
        exit(1)
        
    try:
        # We use "jarvis" as the default built-in wake word for now.
        # You can create a custom "Scarlet" model at console.picovoice.ai 
        # and load it here by replacing keyword_paths with your custom .ppn file.
        porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=["jarvis"] 
        )
        return porcupine
    except Exception as e:
        print(f"❌ Failed to initialize Porcupine: {e}")
        exit(1)

async def run_wake_word_loop():
    porcupine = setup_porcupine()
    
    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )
    
    print("\n" + "="*50)
    print("🎙️  SCARLET WAKE WORD ENGINE STARTED")
    print("👂 Listening continuously in background (0% CPU)...")
    print("🗣️  Say 'Jarvis' to wake up Scarlet.")
    print("="*50 + "\n")
    
    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            
            keyword_index = porcupine.process(pcm)
            
            if keyword_index >= 0:
                print("\n🔔 Wake word detected! Waking up Scarlet...")
                
                # Stop listening for wake word temporarily
                audio_stream.stop_stream()
                
                # Run Scarlet interaction
                await scarlet_core.main()
                
                print("\n👂 Resuming background listening... Say 'Jarvis' again.")
                audio_stream.start_stream()
                
    except KeyboardInterrupt:
        print("\nStopping Scarlet...")
    finally:
        audio_stream.close()
        pa.terminate()
        porcupine.delete()

if __name__ == "__main__":
    asyncio.run(run_wake_word_loop())
