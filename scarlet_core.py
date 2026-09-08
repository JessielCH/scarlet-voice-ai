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

CRITICAL: The user speaks through a voice microphone. Transcription may have errors.
Be very lenient with spelling/typos. "pong", "pond", "pons" all mean "pon" (play).

You MUST respond with JSON whenever the user wants to:
- Play music or audio (words like: pon, pong, pond, pon me, reproduce, escuchar, oír, quiero escuchar, quiero oír, música de, canción de, coloca, dale play)
- Open YouTube or search for a video
- Search on Google
- Open a website

For music/YouTube use ONLY this exact JSON format (no markdown, no extra text):
{"action": "youtube_search", "query": "<what to search>", "message": "<confirmation in Spanish, max 10 words>"}

For Google search:
{"action": "google_search", "query": "<search terms>", "message": "<confirmation in Spanish, max 10 words>"}

For opening a URL:
{"action": "open_url", "url": "<full url>", "message": "<confirmation in Spanish, max 10 words>"}

Examples (ALWAYS return JSON for these):
- "pon reggaeton" -> {"action": "youtube_search", "query": "reggaeton", "message": "Reproduciendo reggaeton."}
- "música de Bad Bunny" -> {"action": "youtube_search", "query": "Bad Bunny", "message": "Poniendo Bad Bunny en YouTube."}
- "pong Bad Bunny" -> {"action": "youtube_search", "query": "Bad Bunny", "message": "Poniendo Bad Bunny."}
- "quiero escuchar salsa" -> {"action": "youtube_search", "query": "salsa", "message": "Reproduciendo salsa."}
- "pond musica de Shakira" -> {"action": "youtube_search", "query": "Shakira", "message": "Poniendo Shakira."}
- "busca el clima" -> {"action": "google_search", "query": "clima hoy", "message": "Buscando el clima."}

For anything else that is NOT a browser/media action, respond in plain Spanish (NO JSON).
Keep plain text responses under 40 words."""

# ---------------------------------------------------------------------------
# Transcript cleanup: fix common Whisper Spanish mistranscriptions
# ---------------------------------------------------------------------------
WHISPER_FIXES = [
    # Verb "pon" (play/put) often gets extra letters
    (r'\bpongs?\b', 'pon'),
    (r'\bponds?\b', 'pon'),
    (r'\bponer\b', 'pon'),
    (r'\bpones\b', 'pon'),
    # "abre" (open)
    (r'\bhabres?\b', 'abre'),
    (r'\babre\b', 'abre'),
    # "busca" (search)
    (r'\bbuscar\b', 'busca'),
    # "reproduce" variants
    (r'\breproduced?\b', 'reproduce'),
]

import re

def clean_transcript(text: str) -> str:
    """Fixes common Whisper mistranscriptions in Spanish voice commands."""
    if not text:
        return text
    cleaned = text
    for pattern, replacement in WHISPER_FIXES:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    if cleaned != text:
        print(f"🔧 Transcript corrected: '{text}' -> '{cleaned}'")
    return cleaned


# ---------------------------------------------------------------------------
# Keyword-based intent fallback (catches what the LLM misses)
# ---------------------------------------------------------------------------
# Trigger words that indicate the user wants to play something on YouTube
MUSIC_TRIGGERS = [
    r'\bpon\b', r'\bpong\b', r'\bpond\b', r'\bpons\b',
    r'\breproduce\b', r'\breprod[uo]cir\b',
    r'\bescuchar\b', r'\boír\b', r'\boir\b',
    r'\bquiero (escuchar|oir|oír|ver)\b',
    r'\bmúsica de\b', r'\bmusica de\b',
    r'\bcanción de\b', r'\bcancion de\b',
    r'\bdale play\b', r'\bcoloca\b',
]

def keyword_intent_fallback(text: str):
    """
    If the LLM didn't return a JSON action but the text looks like a
    play/search command, build the action directly from keywords.
    Returns an action dict or None.
    """
    text_lower = text.lower()
    for pattern in MUSIC_TRIGGERS:
        if re.search(pattern, text_lower):
            # Strip trigger words to extract the actual query
            query = re.sub(
                r'\b(pon|pong|pond|pons|reproduce|escuchar|oír|oir|música de|musica de|'
                r'canción de|cancion de|dale play|coloca|quiero|ver|ponme|me|la|el|una|un)\b',
                '', text_lower, flags=re.IGNORECASE
            ).strip()
            query = re.sub(r'\s+', ' ', query).strip()
            if query:
                print(f"🔀 Fallback intent detected: youtube_search -> '{query}'")
                return {
                    "action": "youtube_search",
                    "query": query,
                    "message": f"Reproduciendo {query} en YouTube."
                }
    return None

def record_audio(filename="temp_audio.wav"):
    """Records audio from the microphone and saves it to a file."""
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.4
    recognizer.non_speaking_duration = 0.3
    with sr.Microphone() as source:
        print("\n🎤 Adjusting for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
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
            model="groq/compound-mini",
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

        # LLM returned plain text — try keyword fallback to catch missed intents
        fallback_action = keyword_intent_fallback(prompt)
        if fallback_action:
            return fallback_action["message"], fallback_action

        return raw, None

    except Exception as e:
        print(f"❌ LLM error: {e}")
        # Even on LLM error, try keyword fallback
        fallback_action = keyword_intent_fallback(prompt)
        if fallback_action:
            return fallback_action["message"], fallback_action
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
            link = videos[0].get("link", "")
            title = videos[0].get("title", query)
            print(f"🎬 First result: '{title}'")
            print(f"🔗 URL: {link}")
            if link:
                return link
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
    """Converts text to speech using Edge TTS with a friendlier voice and speed."""
    try:
        communicate = edge_tts.Communicate(text, "es-CO-SalomeNeural", rate="+5%")
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
            # Fix common Whisper mis-transcriptions before sending to LLM
            user_text = clean_transcript(user_text)
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


async def process_command(user_text: str):
    """
    Runs the respond-and-speak pipeline on already-transcribed text.
    Called by main.py when the wake word listener captures the command
    phrase directly via Google STT (skipping Whisper to save time).
    """
    tts_file = None
    user_text = clean_transcript(user_text)
    print("🧠 Thinking...")
    response_text, action = generate_response(user_text)
    print(f"🤖 Scarlet: {response_text}")

    if action:
        execute_action(action)

    print("🔊 Generating Speech...")
    tts_file = await text_to_speech(response_text)
    if tts_file:
        print("▶️  Playing audio...")
        play_audio(tts_file)
        try:
            os.remove(tts_file)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
