import os
import io
import wave
import time
import asyncio
import pygame
import speech_recognition as sr
from dotenv import load_dotenv
from groq import Groq
import edge_tts

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
    print("❌ ERROR: Please set your GROQ_API_KEY in the .env file.")
    exit(1)

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Initialize pygame mixer for audio playback
pygame.mixer.init()

def record_audio(filename="temp_audio.wav"):
    """Records audio from the microphone and saves it to a file."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n🎤 Adjusting for ambient noise... Please wait.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("🟢 Listening... Speak now!")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            print("⏳ Processing audio...")
            
            # Save audio to a WAV file
            with open(filename, "wb") as f:
                f.write(audio.get_wav_data())
            return filename
        except sr.WaitTimeoutError:
            print("⚠️ No speech detected.")
            return None
        except Exception as e:
            print(f"❌ Error recording audio: {e}")
            return None

def transcribe_audio(filename):
    """Transcribes audio using Groq Whisper API."""
    try:
        with open(filename, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
                response_format="text",
                language="es" # Set to 'en' for English
            )
        return transcription
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return None

def generate_response(prompt):
    """Generates a response using Groq LLaMA 3 API."""
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are Scarlet, a helpful and highly intelligent AI assistant created by JessielCH. You communicate clearly, concisely, and you are currently speaking in Spanish. Keep your answers brief for voice output."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192",
            temperature=0.7,
            max_tokens=256,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"❌ LLM error: {e}")
        return "Hubo un error al conectar con mi cerebro."

async def text_to_speech(text, output_file="response.mp3"):
    """Converts text to speech using Edge TTS and saves as MP3."""
    try:
        # 'es-MX-DaliaNeural' is a good Spanish female voice. 
        # For English, you can use 'en-US-AriaNeural'.
        communicate = edge_tts.Communicate(text, "es-MX-DaliaNeural")
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        print(f"❌ TTS error: {e}")
        return None

def play_audio(filename):
    """Plays the generated audio file."""
    try:
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()
    except Exception as e:
        print(f"❌ Audio playback error: {e}")

async def main():
    print("=======================================")
    print("🚀 Scarlet Voice AI - Core Engine Test")
    print("=======================================")
    
    audio_file = record_audio()
    if audio_file:
        print("🧠 Transcribing with Groq Whisper...")
        user_text = transcribe_audio(audio_file)
        print(f"🗣️ You said: {user_text}")
        
        if user_text:
            print("🧠 Thinking (Groq Llama 3)...")
            response_text = generate_response(user_text)
            print(f"🤖 Scarlet: {response_text}")
            
            print("🔊 Generating Speech (Edge TTS)...")
            tts_file = await text_to_speech(response_text)
            
            if tts_file:
                print("▶️ Playing audio...")
                play_audio(tts_file)
                
        # Clean up temporary files
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if 'tts_file' in locals() and tts_file and os.path.exists(tts_file):
            os.remove(tts_file)

if __name__ == "__main__":
    asyncio.run(main())
