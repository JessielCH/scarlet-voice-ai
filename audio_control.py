"""
audio_control.py
─────────────────
System-level audio mute/unmute using the Windows Core Audio API (pycaw).
This is used to silence the speakers BEFORE recording the user's voice command,
so background music doesn't bleed into the microphone — exactly like Alexa does.
"""
from pycaw.utils import AudioUtilities


def _get_volume():
    """Returns the Windows endpoint volume controller."""
    speakers = AudioUtilities.GetSpeakers()
    return speakers.EndpointVolume


def mute_system():
    """Silences the system audio output."""
    try:
        _get_volume().SetMute(1, None)
    except Exception as e:
        print(f"⚠️  Could not mute system audio: {e}")


def unmute_system():
    """Restores the system audio output."""
    try:
        _get_volume().SetMute(0, None)
    except Exception as e:
        print(f"⚠️  Could not unmute system audio: {e}")


def is_muted() -> bool:
    """Returns True if the system audio is currently muted."""
    try:
        return bool(_get_volume().GetMute())
    except Exception:
        return False
