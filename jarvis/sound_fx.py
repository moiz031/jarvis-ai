
import winsound
import threading
import time

class SoundFX:
    """Provides sci-fi style sound effects using Windows native checking."""
    
    @staticmethod
    def play_wake():
        """Plays a 'listening' chime."""
        def _play():
            # Ascending tone (Sci-fi activation)
            winsound.Beep(400, 100)
            winsound.Beep(600, 100)
            winsound.Beep(1000, 200)
        threading.Thread(target=_play, daemon=True).start()

    @staticmethod
    def play_processing():
        """Plays a 'processing' sound (subtle)."""
        def _play():
            winsound.Beep(200, 50)
            time.sleep(0.05)
            winsound.Beep(200, 50)
        threading.Thread(target=_play, daemon=True).start()

    @staticmethod
    def play_error():
        """Plays an error buzzer."""
        def _play():
            winsound.Beep(150, 400)
        threading.Thread(target=_play, daemon=True).start()

    @staticmethod
    def play_success():
        """Plays a success chime."""
        def _play():
            winsound.Beep(800, 150)
            winsound.Beep(1200, 300)
        threading.Thread(target=_play, daemon=True).start()
