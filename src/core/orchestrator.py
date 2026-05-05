"""
@ai-context: Main entry point and orchestrator. Ties Voice (STT), Vision (OCR/CLIP),
API, OS and Router into a single cohesive autonomous loop.

DÜZELTMELER (v2):
- max_workers: 2 → 3 (screen_future + intent + olası fallback)
- is_processing: bool → threading.Event (thread-safe, race condition yok)
- screen_future.cancel() sonrası gereksiz bekleme kaldırıldı
"""

import concurrent.futures
import threading
import time
from collections.abc import Callable

import numpy as np
import speech_recognition as sr

from src.api_control.api_layer import APILayer
from src.core.intent_router import IntentRouter
from src.os_control.action_controller import ActionController
from src.os_control.os_layer import OSLayer
from src.utils.scaler import CoordinateScaler
from src.vision.ocr_analyzer import OcrAnalyzer
from src.vision.screen_capture import ScreenCapturer
from src.vision.semantic_matcher import SemanticVision
from src.vision.moondream_analyzer import MoondreamAnalyzer
from src.vision.vision_controller import VisionController
from src.voice.background_listener import BackgroundVoiceListener
from src.voice.stt_engine import STTEngine


class AgentOrchestrator:
    """
    Central brain of the Autonomous Screen Reader.
    Manages the lifecycle and routes natural language commands.
    """

    def __init__(self) -> None:
        print("[Orchestrator] Sistem baslatiliyor. Moduller yukleniyor...")

        # 1. Ses ve Görüntü Temel Bileşenleri
        self.bg_listener = BackgroundVoiceListener()
        self.stt_engine = STTEngine(language="tr-TR")
        self.capturer = ScreenCapturer()

        # 2. Vision Katmanı
        self.ocr = OcrAnalyzer()
        self.semantic = SemanticVision()
        self.moondream = MoondreamAnalyzer()
        self.vision = VisionController(self.ocr, self.semantic, self.moondream)

        # 3. İşlem Kontrolcüleri
        self.scaler = CoordinateScaler()
        self.action = ActionController()

        # 4. OS ve API Katmanları
        self.api = APILayer()
        self.os = OSLayer()

        # 5. Router
        self.router = IntentRouter(self.api, self.os, self.vision, self.action, self.scaler)

        # FIX #1: max_workers 2→3
        # Neden: screen_future(worker1) + _async_execute_intent(worker2) eş zamanlı çalışıyor.
        # 3. komut gelince kuyruğa girip screen_future.result() timeout'a düşüyordu.
        self.executor_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)

        self.on_status_change: Callable[[str], None] | None = None
        self.is_active: bool = True

        # FIX #2: bool yerine threading.Event — set/clear atomik, race condition yok.
        # Eski: self.is_processing = True/False (thread-safe değil)
        # Yeni: self._processing_event.set() / .clear() / .is_set()
        self._processing_event = threading.Event()

        print("[Orchestrator] Tum moduller basariyla yuklendi.")

    def toggle_active(self) -> bool:
        self.is_active = not self.is_active
        state_str = "AKTIF" if self.is_active else "STANDBY"
        print(f"[Orchestrator] Sistem modu degistirildi: {state_str}")
        if self.on_status_change:
            self.on_status_change("Aktif" if self.is_active else "Stand By")
        return self.is_active

    def _is_wake_command(self, text: str) -> bool:
        """Standby'dan cikis icin wake kelimelerini kontrol eder."""
        t = text.lower().strip()
        wake_words = ["uyan", "aktif ol", "hey ajan", "basla", "dinle", "wake up", "active"]
        return any(w in t for w in wake_words)

    def _is_standby_command(self, text: str) -> bool:
        """Standby moduna gecis komutlarini kontrol eder."""
        t = text.lower().strip()
        sleep_words = ["stand by", "standby", "bekle", "uyu", "sus", "duraklat", "dinleme"]
        return any(w in t for w in sleep_words)

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        self.on_status_change = callback

    def _update_status(self, status: str) -> None:
        if self.on_status_change:
            self.on_status_change(status)

    def _step_transcribe(self, recognizer: sr.Recognizer, audio_data: sr.AudioData) -> str | None:
        print("\n" + "=" * 50)
        print("[Adim 1] Ses isleniyor (STT)...")
        text: str | None = self.stt_engine.transcribe(audio_data, recognizer)
        if not text:
            print("-> Ses anlasilamadi. Beklemeye devam ediliyor.")
            return None
        print(f"-> Duyulan Metin: '{text}'")
        return text

    def _step_scan_screen(self) -> np.ndarray | None:
        print("[Adim 2] Ekran taraniyor (Vision)...")
        try:
            frame: np.ndarray = self.capturer.capture_primary_screen()
        except Exception as e:
            print(f"-> Ekran yakalanamadi: {e}")
            return None
        if frame.size == 0:
            print("-> Ekran goruntusu bos dondu. Iptal.")
            return None
        print(f"-> Ekran yakalandi: {frame.shape[1]}x{frame.shape[0]}")
        return frame

    def _on_audio_received(self, recognizer: sr.Recognizer, audio_data: sr.AudioData) -> None:
        # --- STANDBY MODU ---
        # Standby'dayken STT (Whisper) bile calistirma. Sadece Google'in hafif
        # recognize_google ile wake kelimesini ara. Bu, Whisper'in %100 CPU
        # kullanimini tamamen engeller.
        if not self.is_active:
            try:
                # Google free API: hizli ve hafif, sadece wake kelimesi icin yeterli
                raw_text = recognizer.recognize_google(audio_data, language="tr-TR")
                print(f"[STANDBY] Duyulan (wake check): '{raw_text}'")
                if self._is_wake_command(raw_text):
                    print("[Orchestrator] Wake komutu alindi! Sistemi aktif ediliyor...")
                    self.toggle_active()
            except Exception:
                pass  # Sessizlik veya anlasilamayan ses — normal
            return

        # --- AKTIF MOD ---
        if self._processing_event.is_set():
            return

        try:
            self._processing_event.set()
            self._update_status("Dinliyor...")

            # Paralel: STT işlerken ekranı arka planda yakala
            screen_future = self.executor_pool.submit(self._step_scan_screen)
            text: str | None = self._step_transcribe(recognizer, audio_data)

            if not text:
                self._update_status("Bekliyor")
                self._processing_event.clear()
                return

            # Standby komutunu kontrol et
            if self._is_standby_command(text):
                screen_future.cancel()
                print("[Orchestrator] Standby komutu alindi. Sistem beklemeye aliniyor...")
                self.toggle_active()
                self._processing_event.clear()
                return

            self._update_status("Isleniyor...")

            future: concurrent.futures.Future[bool] = self.executor_pool.submit(
                self._async_execute_intent, text, screen_future
            )
            future.add_done_callback(self._on_vision_done)

        except Exception as e:
            print(f"[Orchestrator] Pipeline hatası: {e}")
            self._update_status("Hata")
            self._processing_event.clear()
            print("[Orchestrator] Dinlemeye devam ediliyor...\n")

    def _async_execute_intent(
        self,
        text: str,
        screen_future: "concurrent.futures.Future | None" = None,
    ) -> bool:
        # API/OS komutları — ekran taramasına gerek yok
        if self.router.is_pure_action(text):
            print("[Adim 2] Saf aksiyon komutu — ekran taramasi atlandi.")
            # screen_future arka planda tamamlanır; sonucunu almayız → bekleme yok
            print("[Adim 3] Intent Router'a iletiliyor (screen_image=None)...")
            self._update_status("Yonlendiriliyor...")
            success = self.router.route_command(text, None)
            print("=" * 50 + "\n")
            return success

        # VLM gerektiren komutlar — screen_future'ı bekle
        frame: np.ndarray | None = None
        if screen_future is not None:
            try:
                frame = screen_future.result(timeout=5.0)
            except Exception as e:
                print(f"[Orchestrator] screen_future hatası ({e}), yeniden deneniyor...")
                frame = self._step_scan_screen()
        else:
            frame = self._step_scan_screen()

        if frame is None:
            return False

        print("[Adim 3] Intent Router'a iletiliyor...")
        self._update_status("Yonlendiriliyor...")
        success = self.router.route_command(text, frame)
        print("=" * 50 + "\n")
        return success

    def _on_vision_done(self, future: concurrent.futures.Future[bool]) -> None:
        try:
            success: bool = future.result(timeout=30)
            self._update_status("Tamamlandı" if success else "Bekliyor")
        except concurrent.futures.TimeoutError:
            print("[Orchestrator] Intent işlemi zaman aşımına uğradi (30s). Sıfırlanıyor.")
            self._update_status("Zaman Aşımı")
        except Exception as e:
            print(f"[Orchestrator] Asenkron islem hatasi: {e}")
            self._update_status("Hata")
        finally:
            # FIX #2: Timer ile sıfırlama yerine doğrudan clear — 1.5s bekleme kalktı.
            # Önceki: threading.Timer(1.5, reset_status).start() → bu sürede komut yutuluyordu.
            def reset_processing() -> None:
                time.sleep(0.5)  # Kısa bekleme: GUI güncellemesi için yeterli
                self._update_status("Bekliyor")
                self._processing_event.clear()

            threading.Thread(target=reset_processing, daemon=True).start()

    def start(self, block: bool = True) -> None:
        print("[Orchestrator] Dinleme servisi baslatiliyor...")
        self.bg_listener.start_listening(self._on_audio_received)
        print("[Orchestrator] Sistem aktif. Ctrl+C veya Failsafe ile cikin.")
        if block:
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n[Orchestrator] Kullanici istegi ile kapatiliyor...")
                self.stop()

    def stop(self) -> None:
        self.bg_listener.stop_listening()
        self.executor_pool.shutdown(wait=False)
        print("[Orchestrator] Sistem tamamen durduruldu.")


if __name__ == "__main__":
    orchestrator = AgentOrchestrator()
    orchestrator.start()