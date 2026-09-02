import os
import json
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
from youtubesearchpython import VideosSearch

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
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Scarlet, a highly intelligent voice AI assistant created by Jessiel.
You communicate in Spanish by default, concisely and clearly (your response will be read aloud).

You can control the user's computer browser. When the user asks to play music,
open YouTube, search for a video, or any similar browser action, respond ONLY with a
valid JSON object in this exact format (no extra text, no markdown, no code blocks):
{"action": "youtube_search", "query": "<search terms>", "message": "<short confirmation in Spanish under 12 words>"}

For general Google searches:
{"action": "google_search", "query": "<search terms>", "message": "<short confirmation in Spanish under 12 words>"}

For opening a specific URL:
{"action": "open_url", "url": "<full_url>", "message": "<short confirmation in Spanish under 12 words>"}

Examples:
- User: "pon reggaeton" -> {"action": "youtube_search", "query": "reggaeton", "message": "Reproduciendo reggaeton en YouTube."}
- User: "pon Bad Bunny" -> {"action": "youtube_search", "query": "Bad Bunny", "message": "Poniendo Bad Bunny en YouTube."}
- User: "busca el clima de hoy" -> {"action": "google_search", "query": "clima hoy", "message": "Buscando el clima de hoy."}

For anything else, respond in plain conversational Spanish (NO JSON).
Keep plain text responses under 40 words."""


# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------
def record_audio(filename="temp_audio.wav"):
    """Records audio from the microphone and saves it to a file."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n🎤 Adjusting for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("🟢 Listening... Speak now!")
        try:
            audio = recognizer.listen(source, timeout=7, phrase_time_limit=12)
            print("⏳ Processing audio...")
            with open(filename, "wb") as f:
                f.write(audio.get_wav_data())
            return filename
        except sr.WaitTimeoutError:
            print("⚠️  No speech detected.")
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
    """Returns (text_to_speak, action_dict_or_None)."""
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model="groq/compound",
            temperature=0.5,
            max_tokens=200,
        )
        raw = chat_completion.choices[0].message.content.strip()
        
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        # Try to parse as JSON action
        try:
            data = json.loads(raw)
            if data.get("action") in ("youtube_search", "google_search", "open_url"):
                return data.get("message", "Hecho."), data
        except (json.JSONDecodeError, AttributeError):
            pass

        return raw, None

    except Exception as e:
        print(f"❌ LLM error: {e}")
        return "Hubo un error al conectar con mi cerebro.", None


# ---------------------------------------------------------------------------
# YouTube: get first result URL
# ---------------------------------------------------------------------------
def get_first_youtube_url(query: str) -> str:
    """Searches YouTube and returns the direct watch URL of the first result."""
    try:
        search = VideosSearch(query, limit=1)
        results = search.result()
        videos = results.get("result", [])
        if videos:
            video_id = videos[0].get("id")
            title = videos[0].get("title", query)
            print(f"🎬 First result: '{title}'")
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        print(f"⚠️  YouTube search error: {e}")
    # Fallback to search results page
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"


# ---------------------------------------------------------------------------
# Action executor
# ---------------------------------------------------------------------------
def execute_action(action: dict):
    """Executes a browser/system action returned by the LLM."""
    kind = action.get("action")

    if kind == "youtube_search":
        query = action.get("query", "")
        url = get_first_youtube_url(query)
        print(f"🌐 Opening YouTube: {url}")
        webbrowser.open(url)

    elif kind == "google_search":
        query = action.get("query", "")
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        print(f"🌐 Opening Google: {url}")
        webbrowser.open(url)

    elif kind == "open_url":
        url = action.get("url", "")
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
# Greeting
# ---------------------------------------------------------------------------
async def speak_greeting():
    """Plays the wake-up greeting."""
    greeting = "Hola, soy Scarlet. ¿En qué puedo ayudarte?"
    print(f"🤖 Scarlet: {greeting}")
    tts_file = await text_to_speech(greeting, output_file="greeting.mp3")
    if tts_file:
        play_audio(tts_file)
        try:
            os.remove(tts_file)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main interaction flow
# ---------------------------------------------------------------------------
async def main():
    """One full listen -> transcribe -> respond -> speak cycle."""
    # Greet the user after wake word
    await speak_greeting()

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
