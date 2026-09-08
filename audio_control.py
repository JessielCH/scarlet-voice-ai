"""
audio_control.py
─────────────────
Audio ducking using the Windows Core Audio API (pycaw).
Lowers the volume of browsers (YouTube, etc.) to 10% when Scarlet listens
and speaks, instead of muting the whole system. This prevents stuttering
and audio overlaps.
"""
from pycaw.utils import AudioUtilities
from pycaw.api.audioclient import ISimpleAudioVolume

BROWSER_PROCESSES = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"]

def get_browser_sessions():
    """Yields pycaw audio sessions that belong to known browsers."""
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name() in BROWSER_PROCESSES:
            yield session

def mute_system():
    """
    Actually 'ducks' the audio: lowers browser volumes to 10% 
    instead of fully muting the system.
    """
    try:
        for session in get_browser_sessions():
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            # Store the current volume to a custom attribute if not stored yet
            if not hasattr(session, "original_volume"):
                session.original_volume = volume.GetMasterVolume()
            # Set to 10% so the user can still hear it faintly in the background
            volume.SetMasterVolume(0.1, None)
    except Exception as e:
        print(f"⚠️  Could not duck audio: {e}")

def unmute_system():
    """Restores the browser volumes back to 100%."""
    try:
        for session in get_browser_sessions():
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            # Restore to 100%
            volume.SetMasterVolume(1.0, None)
    except Exception as e:
        print(f"⚠️  Could not restore audio: {e}")

def is_muted() -> bool:
    """Returns True if any browser is currently ducked to 10%."""
    try:
        for session in get_browser_sessions():
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            if volume.GetMasterVolume() <= 0.15: # roughly 10%
                return True
        return False
    except Exception:
        return False
