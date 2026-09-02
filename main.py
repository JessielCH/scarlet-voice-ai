import os
import time
import asyncio
import speech_recognition as sr
from dotenv import load_dotenv

import scarlet_core

# ---------------------------------------------------------------------------
# Wake word configuration
# ---------------------------------------------------------------------------
WAKE_WORD = "scarlet"
WAKE_VARIANTS = ["scarlet", "scarlett", "skarlet", "skarlett", "escarlet"]


def listen_for_wake_word(recognizer: sr.Recognizer, source: sr.AudioSource) -> bool:
    """
    Listens for the wake word using Google Speech Recognition.
    Returns True if the wake word is detected, False on timeout/error.
    """
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
        # If Google API is unavailable, silently skip
        print(f"\n⚠️  Speech API error: {e}")
        return False


async def run_wake_word_loop():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300          # Sensitivity (lower = more sensitive)
    recognizer.dynamic_energy_threshold = True  # Auto-adjusts to background noise
    recognizer.pause_threshold = 0.6           # Seconds of silence to consider phrase done

    print("\n" + "=" * 50)
    print("🎙️  SCARLET WAKE WORD ENGINE STARTED")
    print(f"👂 Listening continuously...")
    print(f"🗣️  Say '{WAKE_WORD.upper()}' to activate the assistant.")
    print("   (Press Ctrl+C to stop)")
    print("=" * 50 + "\n")

    with sr.Microphone() as source:
        print("🔇 Calibrating for ambient noise (2 seconds)...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print("✅ Ready! Waiting for wake word...\n")

        while True:
            detected = listen_for_wake_word(recognizer, source)

            if detected:
                print("\n🔔 Wake word detected! Activating Scarlet...")
                # Small audio cue feedback
                print("   *beep*")

                # Run the full Scarlet interaction cycle
                await scarlet_core.main()

                print("\n👂 Back to standby... Say 'SCARLET' to activate again.\n")


def main():
    try:
        asyncio.run(run_wake_word_loop())
    except KeyboardInterrupt:
        print("\n\n🛑 Scarlet stopped. Goodbye!")


if __name__ == "__main__":
    main()
