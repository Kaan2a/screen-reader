"""
@ai-context: Handles continuous, non-blocking background microphone
listening using threading/callbacks to prevent GUI freezes.
"""

from collections.abc import Callable

import speech_recognition as sr


class BackgroundVoiceListener:
    """
    Non-blocking background voice listener that passes raw audio
    to a provided callback function without freezing the main thread.
    """

    def __init__(self) -> None:
        """Initializes the recognizer and microphone."""
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self._stopper: Callable[[bool], None] | None = None

    def start_listening(
        self,
        on_audio_received: Callable[[sr.Recognizer, sr.AudioData], None],
    ) -> None:
        """Starts listening in the background. Non-blocking."""
        if self._stopper is not None:
            return

        print("Mikrofon ortam gurultusune gore ayarlaniyor... (1 sn)")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)

        print("Arka planda dinleme baslatildi.")

        def audio_callback(recognizer: sr.Recognizer, audio_data: sr.AudioData) -> None:
            try:
                on_audio_received(recognizer, audio_data)
            except Exception as e:
                print(f"[Arka Plan Dinleyici] Callback hatasi: {e}")

        self._stopper = self.recognizer.listen_in_background(self.microphone, audio_callback)

    def stop_listening(self) -> None:
        """Stops the background listening process securely."""
        if self._stopper is not None:
            print("Arka planda dinleme durduruluyor...")
            self._stopper(False)
            self._stopper = None
            print("Dinleme durduruldu.")


if __name__ == "__main__":
    import time

    print("Initializing BackgroundVoiceListener...")
    bg_listener: BackgroundVoiceListener = BackgroundVoiceListener()

    def my_callback(recognizer: sr.Recognizer, audio_data: sr.AudioData) -> None:
        print("\n[Callback] Ses alindi (AudioData).")

    print("\nTest: 10 saniye dinlenecek.")
    bg_listener.start_listening(on_audio_received=my_callback)

    print("Dinleniyor... (main thread bloklanmadi!)")
    for i in range(10):
        print(f"Ana dongu calisiyor... ({10 - i} sn kaldi)")
        time.sleep(1)

    bg_listener.stop_listening()
    print("Test tamamlandi.")
