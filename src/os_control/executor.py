"""
@ai-context: Executes parsed voice commands by mapping UI elements
from ApplicationState to physical screen coordinates and performing
mouse actions. Isolates OS-level errors so the main loop never dies.
"""

import pyautogui

from src.core.state import ApplicationState, UIElement
from src.os_control.mouse_actions import MouseController
from src.utils.scaler import CoordinateScaler
from src.voice.intent_parser import ParsedCommand


class ActionExecutor:
    """
    Executes physical OS actions (mouse clicks) based on parsed
    voice intents and the current UI state. Contains error boundary.
    """

    def __init__(self, mouse_controller: MouseController, scaler: CoordinateScaler) -> None:
        """Initializes the executor with hardware controllers."""
        self.mouse = mouse_controller
        self.scaler = scaler

    def execute(
        self,
        command: ParsedCommand,
        state: ApplicationState,
        source_width: int,
        source_height: int,
    ) -> bool:
        """
        Finds the target in state, scales coordinates, performs action.
        Returns True on success, False on any failure. Never raises.
        """
        print(f"\n[Executor] '{command.target}' araniyor...")
        target_element: UIElement | None = state.find_element(command.target)

        if not target_element:
            print(f"[Executor] Uyari: Ekranda '{command.target}' bulunamadi.")
            return False

        print(f"[Executor] Hedef bulundu! Guven Skoru: %{int(target_element.confidence * 100)}")

        if source_width <= 0 or source_height <= 0:
            print("[Executor] Uyari: Gecersiz kaynak cozunurlugu.")
            return False

        target_x: int
        target_y: int
        target_x, target_y = self.scaler.scale_point(
            target_element.x,
            target_element.y,
            source_width,
            source_height,
        )

        try:
            if command.action == "click":
                self.mouse.click_at(target_x, target_y, button="left")
            elif command.action == "double_click":
                self.mouse.double_click_at(target_x, target_y)
            elif command.action == "right_click":
                self.mouse.click_at(target_x, target_y, button="right")
            else:
                print(f"[Executor] Uyari: '{command.action}' eylemi desteklenmiyor.")
                return False

        except pyautogui.FailSafeException:
            print("[Executor] ACIL DURUM: Failsafe tetiklendi!")
            return False

        except Exception as e:
            print(f"[Executor] OS eylem hatasi: {e}")
            return False

        print(f"[Executor] Islem tamamlandi: {command.action} -> {command.target}")
        return True
