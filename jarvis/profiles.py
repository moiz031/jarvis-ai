# profiles.py - Performance profiles for Jarvis

class PerformanceProfile:
    def __init__(self, name, llm_model, whisper_model, tts_speed, buffer_size):
        self.name = name
        self.llm_model = llm_model
        self.whisper_model = whisper_model
        self.tts_speed = tts_speed
        self.buffer_size = buffer_size

PROFILES = {
    "low_ram": PerformanceProfile(
        name="Low-RAM",
        llm_model="llama3.2:1b",
        whisper_model="tiny",
        tts_speed=1.2,
        buffer_size=512
    ),
    "balanced": PerformanceProfile(
        name="Balanced",
        llm_model="llama3.2:3b",
        whisper_model="base",
        tts_speed=1.0,
        buffer_size=1024
    ),
    "high_quality": PerformanceProfile(
        name="High-Quality",
        llm_model="llama3.1:8b-instruct",
        whisper_model="medium",
        tts_speed=0.9,
        buffer_size=2048
    )
}

def get_profile(name):
    """Retrieve a profile by name, defaulting to balanced."""
    return PROFILES.get(name.lower(), PROFILES["balanced"])
