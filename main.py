import os
import time
import asyncio
import pyautogui
import pygetwindow as gw
import speech_recognition as sr

import scarlet_core

# ---------------------------------------------------------------------------
# Wake word & media-control configuration
# ---------------------------------------------------------------------------
WAKE_WORD       = "scarlet"
WAKE_VARIANTS   = ["scarlet", "scarlett", "skarlet", "skarlett", "escarlet"]

# Commands recognized without going through the full LLM pipeline
MEDIA_COMMANDS = {
    # Pause / resume
    "pausa":      "pause",
    "pausa la":   "pause",
    "parar":      "pause",
    "stop":       "pause",
    "para":       "pause",
    "reanuda":    "resume",
    "continua":   "resume",
    "continúa":   "resume",
    "play":       "resume",
    "reproduce":  "resume",
    # Skip / next
    "siguiente":  "next",
    "cambia":     "next",
    "otra":       "next",
    "skip":       "next",
    "salta":      "next",
    "próxima":    "next",
    "proxima":    "next",
    # Volume
    "sube":       "vol_up",
    "más alto":   "vol_up",
    "mas alto":   "vol_up",
    "baja":       "vol_down",
    "más bajo":   "vol_down",
    "mas bajo":   "vol_down",
    "silencio":   "mute",
    "mute":       "mute",
}

# YouTube keyboard shortcuts
MEDIA_KEYS = {
    "pause":    "space",        # Toggle pause/play
    "resume":   "space",
    "next":     ("shift", "n"), # Next video in queue
    "vol_up":   "up",           # Volume up
    "vol_down": "down",         # Volume down
    "mute":     "m",            # Mute
}

# Feedback messages spoken by Scarlet
MEDIA_MESSAGES = {
    "pause":    "Pausando.",
    "resume":   "Reanudando.",
    "next":     "Cambiando de canción.",
    "vol_up":   "Subiendo el volumen.",
    "vol_down": "Bajando el volumen.",
    "mute":     "Silenciando.",
}


# ---------------------------------------------------------------------------
# Media control helpers
# ---------------------------------------------------------------------------
def focus_browser() -> bool:
    """Brings the browser window to focus. Returns True if successful."""
    browser_titles = ["YouTube", "Chrome", "Edge", "Firefox", "Brave"]
    for title_fragment in browser_titles:
        windows = gw.getWindowsWithTitle(title_fragment)
        if windows:
            win = windows[0]
            try:
                win.activate()
                time.sleep(0.3)   # Give OS time to focus
                return True
            except Exception:
                pass
    return False


def send_media_key(command: str):
    """Sends the keyboard shortcut for the given media command to the browser."""
    key = MEDIA_KEYS.get(command)
    if not key:
        return
    if focus_browser():
        if isinstance(key, tuple):
            pyautogui.hotkey(*key)
        else:
            pyautogui.press(key)
        print(f"⌨️  Sent key: {key}")
    else:
        print("⚠️  No browser window found to control.")


async def handle_media_command(command_key: str):
    """Speaks the feedback and executes the keyboard command."""
    message = MEDIA_MESSAGES.get(command_key, "Hecho.")
    print(f"🎛️  Media command: {command_key} → '{message}'")

    # Speak first, then act (so TTS doesn't get cut off by focus change)
    tts_file = await scarlet_core.text_to_speech(message)
    if tts_file:
        scarlet_core.play_audio(tts_file)
        try:
            os.remove(tts_file)
        except Exception:
            pass

    send_media_key(command_key)


def detect_media_command(text: str):
    """
    Returns the media command key if the text matches a control phrase,
    or None if it's a regular query.
    """
    text_lower = text.lower().strip()
    # Check longest match first to avoid false positives (e.g. "más bajo" before "bajo")
    for phrase in sorted(MEDIA_COMMANDS.keys(), key=len, reverse=True):
        if phrase in text_lower:
            return MEDIA_COMMANDS[phrase]
    return None


# ---------------------------------------------------------------------------
# Wake word listener
# ---------------------------------------------------------------------------
def listen_for_wake_word(recognizer: sr.Recognizer, source: sr.AudioSource) -> bool:
    """Returns True if the wake word is detected."""
    try:
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
        text = recognizer.recognize_google(audio, language="es-ES").lower()
        print(f"   [Heard]: '{text}'", end="\r")

        for variant in WAKE_VARIANTS:
            if variant in text:
                return True
        return False

    except sr.WaitTimeoutError:
        return False
    except sr.UnknownValueError:
        return False
    except sr.RequestError as e:
        print(f"\n⚠️  Speech API error: {e}")
        return False


# ---------------------------------------------------------------------------
# Main cyclic loop
# ---------------------------------------------------------------------------
async def run_wake_word_loop():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold      = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold       = 0.6

    print("\n" + "=" * 52)
    print("🎙️  SCARLET — ALWAYS LISTENING MODE")
    print("👂 Say 'SCARLET' at any time to activate.")
    print("🎛️  While music plays: 'Scarlet pausa/cambia/sube'")
    print("   (Press Ctrl+C to stop)")
    print("=" * 52 + "\n")

    with sr.Microphone() as source:
        print("🔇 Calibrating for ambient noise (2 seconds)...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print("✅ Ready! Waiting for wake word...\n")

        while True:                                  # ← cyclic loop
            detected = listen_for_wake_word(recognizer, source)

            if not detected:
                continue

            # --- Wake word heard ---
            print("\n🔔 Wake word detected!")

            # Listen for the actual command phrase (short timeout)
            print("⚡ Quick-listening for command...")
            try:
                cmd_audio = recognizer.listen(source, timeout=4, phrase_time_limit=8)
                cmd_text  = recognizer.recognize_google(cmd_audio, language="es-ES")
                print(f"🗣️  Command heard: '{cmd_text}'")
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                # Nothing said — treat as general "wake" → greet and full cycle
                await scarlet_core.main()
                print("\n👂 Back to standby...\n")
                continue
            except sr.RequestError as e:
                print(f"⚠️  Speech API error: {e}")
                continue

            # --- Check if it's a media control command ---
            media_cmd = detect_media_command(cmd_text)
            if media_cmd:
                await handle_media_command(media_cmd)
                print("\n👂 Back to standby...\n")
                continue

            # --- Otherwise: full AI interaction with the transcribed command ---
            await scarlet_core.process_command(cmd_text)
            print("\n👂 Back to standby...\n")


def main():
    try:
        asyncio.run(run_wake_word_loop())
    except KeyboardInterrupt:
        print("\n\n🛑 Scarlet stopped. Goodbye!")


if __name__ == "__main__":
    main()
