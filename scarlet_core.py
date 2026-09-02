import os
import io
import json
import wave
import time
import asyncio
import webbrowser
import urllib.parse

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame
import speech_recognition as sr
from dotenv import load_dotenv
from groq import Groq
import edge_tts

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
    print("❌ ERROR: Please set your GROQ_API_KEY in the .env file.")
    exit(1)

client = Groq(api_key=GROQ_API_KEY)
pygame.mixer.init()

# ---------------------------------------------------------------------------
# System prompt with tool instructions for the LLM
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Scarlet, a highly intelligent voice AI assistant created by Jessiel.
You communicate in Spanish by default, concisely and clearly (because your response will be read aloud).

You have the ability to control the user's computer browser. When the user asks you to open a website,
play a video, search YouTube, or any similar browser action, you MUST respond ONLY with a valid JSON
object in this exact format (no extra text, no markdown):
{"action": "open_url", "url": "<full_url>", "message": "<short confirmation in Spanish>"}

For YouTube searches use: https://www.youtube.com/results?search_query=<encoded_query>
For YouTube direct play (when user says play a specific song/video), use: https://www.youtube.com/results?search_query=<encoded_query>
For general web searches: https://www.google.com/search?q=<encoded_query>

Examples:
- User says "pon reggaeton en YouTube" -> {"action": "open_url", "url": "https://www.youtube.com/results?search_query=reggaeton", "message": "Abriendo YouTube con reggaeton."}
- User says "busca recetas de pasta" -> {"action": "open_url", "url": "https://www.google.com/search?q=recetas+de+pasta", "message": "Buscando recetas de pasta."}

For any other request that is NOT a browser action, respond in plain Spanish text (no JSON).
Keep plain text responses under 50 words for voice output."""


# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------
def record_audio(filename="temp_audio.wav"):
    """Records audio from the microphone and saves it to a file."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n🎤 Adjusting for ambient noise... Please wait.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("🟢 Listening... Speak now!")
        try:
            audio = recognizer.listen(source, timeout=7, phrase_time_limit=12)
            print("⏳ Processing audio...")
            with open(filename, "wb") as f:
                f.write(audio.get_wav_data())
            return filename
        except sr.WaitTimeoutError:
            print("⚠️ No speech detected.")
            return None
        except Exception as e:
            print(f"❌ Error recording audio: {e}")
            return None


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
def transcribe_audio(filename):
    """Transcribes audio using Groq Whisper API."""
    try:
        with open(filename, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
                response_format="text",
                language="es",
            )
        return transcription
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return None


# ---------------------------------------------------------------------------
# LLM response + action parsing
# ---------------------------------------------------------------------------
def generate_response(prompt):
    """Generates a response using Groq API. Returns (text_to_speak, action_dict_or_None)."""
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model="groq/compound",
            temperature=0.6,
            max_tokens=300,
        )
        raw = chat_completion.choices[0].message.content.strip()

        # Check if the response is a JSON action
        try:
            data = json.loads(raw)
            if data.get("action") == "open_url":
                return data.get("message", "Abriendo el navegador."), data
        except (json.JSONDecodeError, AttributeError):
            pass  # Not JSON, treat as plain text

        return raw, None

    except Exception as e:
        print(f"❌ LLM error: {e}")
        return "Hubo un error al conectar con mi cerebro.", None


# ---------------------------------------------------------------------------
# Action executor
# ---------------------------------------------------------------------------
def execute_action(action: dict):
    """Executes a browser/system action returned by the LLM."""
    if action.get("action") == "open_url":
        url = action.get("url")
        print(f"🌐 Opening: {url}")
        webbrowser.open(url)


# ---------------------------------------------------------------------------
# Text-to-speech
# ---------------------------------------------------------------------------
async def text_to_speech(text, output_file="response.mp3"):
    """Converts text to speech using Edge TTS."""
    try:
        communicate = edge_tts.Communicate(text, "es-MX-DaliaNeural")
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        print(f"❌ TTS error: {e}")
        return None


# ---------------------------------------------------------------------------
# Audio playback
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main interaction flow
# ---------------------------------------------------------------------------
async def main():
    """One full listen -> transcribe -> respond -> speak cycle."""
    audio_file = record_audio()
    tts_file = None

    if audio_file:
        print("🧠 Transcribing with Groq Whisper...")
        user_text = transcribe_audio(audio_file)
        print(f"🗣️  You said: {user_text}")

        if user_text:
            print("🧠 Thinking...")
            response_text, action = generate_response(user_text)
            print(f"🤖 Scarlet: {response_text}")

            # Execute browser/system action if present
            if action:
                execute_action(action)

            print("🔊 Generating Speech...")
            tts_file = await text_to_speech(response_text)

            if tts_file:
                print("▶️  Playing audio...")
                play_audio(tts_file)

    # Clean up temp files
    for f in [audio_file, tts_file]:
        if f and os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
