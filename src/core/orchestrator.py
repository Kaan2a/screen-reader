"""
@ai-context: Main v3 Orchestrator. Centralizes all AI engines and control layers.
Orchestrates Voice, Vision, LLM Reasoning, and OS/Web actions.
"""

import logging
import threading
import time
from collections.abc import Callable
from typing import TypedDict
import numpy as np

from src.core.llm_brain import LLMBrain, ActionCommand
from src.core.memory import MemoryManager
from src.vision.florence_engine import FlorenceEngine
from src.voice.stt_engine import STTEngine
from src.api_control.api_layer import APILayer
from src.os_control.winauto_layer import WinAutoLayer
from src.web.playwright_layer import SyncPlaywrightLayer
from src.vision.screen_capture import ScreenCapturer

logger = logging.getLogger(__name__)

class AgentConfig(TypedDict):
    llm_model_path: str
    whisper_model: str
    language: str
    cdp_port: int
    n_gpu_layers: int
    florence_model: str

class AgentOrchestrator:
    """The central hub for the autonomous agent."""
    def __init__(self, config: AgentConfig) -> None:
        logger.info("[Orchestrator] v3 Architecture initializing...")
        self.config = config
        
        # Memory
        self.memory = MemoryManager()
        
        # Engines (Lazy loaded)
        self._llm: LLMBrain | None = None
        self.stt: STTEngine | None = None
        self._vision: FlorenceEngine | None = None
        
        # Control Layers
        self.api = APILayer()
        self.os = WinAutoLayer()
        self.web = SyncPlaywrightLayer(cdp_port=config["cdp_port"])
        self.screen_capturer = ScreenCapturer()
        
        self.is_active = False
        self._is_running = False
        self._processing_event = threading.Event()
        self._status_callback: Callable[[str], None] | None = None
        self._worker_thread: threading.Thread | None = None
        
        logger.info("[Orchestrator] Core components initialized. (Models configured for Lazy Loading)")

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        self._status_callback = callback

    def _update_status(self, text: str) -> None:
        if self._status_callback:
            self._status_callback(text)

    def toggle_active(self, state: bool) -> None:
        self.is_active = state
        logger.info(f"[Orchestrator] Active state toggled to: {state}")
        if not state:
            # Otomatik bellek yönetimi: Sistem duraklatıldığında RAM/VRAM'i boşalt
            self.free_memory()

    @property
    def llm(self) -> LLMBrain:
        if self._llm is None:
            self._update_status("Zeka Motoru Yükleniyor...")
            logger.info("[Orchestrator] Lazy loading LLM Brain (VRAM alloc)...")
            self._llm = LLMBrain(model_path=self.config["llm_model_path"])
            self._update_status("Dinliyor...")
        return self._llm

    @property
    def vision(self) -> FlorenceEngine:
        if self._vision is None:
            self._update_status("Vizyon Motoru Yükleniyor...")
            logger.info("[Orchestrator] Lazy loading Florence Engine (VRAM alloc)...")
            self._vision = FlorenceEngine(model_id=self.config["florence_model"])
            self._update_status("Dinliyor...")
        return self._vision

    def load_models(self) -> None:
        """Loads ONLY the essential STT model at startup to save RAM/VRAM."""
        logger.info("[Orchestrator] Loading essential AI models...")
        self._update_status("Ses Motoru Yükleniyor...")
        self.stt = STTEngine(language=self.config["language"], model_size=self.config["whisper_model"])
        logger.info("[Orchestrator] STT loaded successfully. Heavy models deferred.")
        self._update_status("Hazır")

    def free_memory(self) -> None:
        """Unloads heavy ML models from memory and clears VRAM."""
        import gc
        logger.info("[Orchestrator] Freeing memory...")
        
        if self._llm:
            del self._llm
            self._llm = None
            
        if self._vision:
            del self._vision
            self._vision = None
            
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("[Orchestrator] CUDA cache cleared.")
        except ImportError:
            pass
            
        self._update_status("Bellek Temizlendi")

    def _capture_screen(self) -> np.ndarray:
        """Captures the primary screen. Throws RuntimeError if uninitialized."""
        if not self.screen_capturer:
            raise RuntimeError("ScreenCapturer not initialized.")
        return self.screen_capturer.capture_primary_screen()

    def _handle_os(self, command: ActionCommand) -> bool:
        if command.action == "open" and command.target == "settings":
            app = command.parameters.get("app", "")
            if app.startswith("ms-settings:"):
                page = app.replace("ms-settings:", "")
            else:
                page = ""
            self.memory.update_context("last_app", "ms-settings:")
            self.memory.update_context("page", page)
            return self.os.open_settings(page)
            
        elif command.action == "click":
            return self.os.click_element(command.target)
            
        elif command.action == "focus":
            return self.os.focus_window(command.target)
            
        return False

    def _handle_api(self, command: ActionCommand) -> bool:
        return self.api.route_media_command(command.action, command.target)

    def _handle_web(self, command: ActionCommand, screen: np.ndarray | None) -> bool:
        return self.web.execute_action(command.action, command.target, screenshot_np=screen)

    def _handle_vision(self, command: ActionCommand, screen: np.ndarray | None) -> bool:
        if not self.vision or screen is None:
            return False
        result = self.vision.find_element(screen, command.target)
        if result:
            import pyautogui
            pyautogui.click(int(result["x"]), int(result["y"]))
            return True
        return False

    def _handle_system(self, command: ActionCommand) -> bool:
        # System-level command fallback
        return False

    def _execute_command(self, command: ActionCommand, original_text: str, screen: np.ndarray | None) -> bool:
        logger.info(f"[Orchestrator] Executing Command: {command}")
        self._update_status("İşlem Uygulanıyor...")
        self.memory.add(role="user", content=original_text)
        
        target = command.target.lower()
        success = False
        
        # Route to appropriate layer based on target or action
        if target in ["spotify", "youtube", "netflix", "twitch", "primevideo", "twitter", "os"]:
            success = self._handle_api(command)
            if not success and target in ["youtube", "netflix"]:
                success = self._handle_web(command, screen)
                
        elif command.action in ["open", "focus"] and target in ["settings", "network"]:
            success = self._handle_os(command)
            
        elif target == "browser" or "web" in command.action:
            success = self._handle_web(command, screen)
            
        else:
            success = self._handle_vision(command, screen)
            
        if success:
            self._update_status("İşlem Tamamlandı.")
            self.memory.add(role="assistant", content="Görevi başarıyla yerine getirdim.")
        else:
            self._update_status("İşlem Başarısız / Bulunamadı.")
            self.memory.add(role="assistant", content="Görevi yerine getiremedim.")
            
        return success

    def _run_loop(self) -> None:
        if not self.stt:
            return
        
        self.stt.start_listening()
        self._is_running = True
        
        while self._is_running:
            if not self.is_active:
                time.sleep(0.1)
                continue
                
            res = self.stt.get_result(timeout=0.1)
            if res and res.text:
                self._update_status(f"Anlaşılan: {res.text}")
                
                if self.llm:
                    cmd = self.llm.process_query(res.text, self.memory.build_llama_context())
                    if cmd:
                        try:
                            screen = self._capture_screen()
                        except Exception as e:
                            logger.error(f"[Orchestrator] Screen capture failed: {e}")
                            screen = None
                            
                        self._execute_command(cmd, res.text, screen)
                        
                # Reset to listening after a cycle
                self._update_status("Dinliyor...")
        
        self.stt.stop_listening()

    def start(self, block: bool = False) -> None:
        if block:
            self._run_loop()
        else:
            self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
            self._worker_thread.start()

    def stop(self) -> None:
        """Stops all active processes."""
        self._is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
        self.web.cleanup()
        logger.info("[Orchestrator] Stopped.")