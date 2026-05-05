"""
@ai-context: Handles OS-level mouse interactions (move, click, drag)
using pyautogui. Adheres strictly to SRP by only accepting
primitive coordinate inputs.
"""

import pyautogui


class MouseController:
    """
    Controller for mouse actions (moving, clicking, dragging).
    Strictly responsible for OS-level interactions.
    """

    def __init__(self) -> None:
        """Initializes the MouseController with failsafe active."""
        pyautogui.FAILSAFE = True

    def move_to(self, x: int, y: int) -> None:
        """Moves the mouse smoothly to the specified coordinates."""
        pyautogui.moveTo(x, y, duration=0.2)

    def click_at(self, x: int, y: int, button: str = "left") -> None:
        """Moves to coordinates and performs a single click."""
        self.move_to(x, y)
        pyautogui.click(button=button)

    def double_click_at(self, x: int, y: int) -> None:
        """Moves to coordinates and performs a double click."""
        self.move_to(x, y)
        pyautogui.doubleClick()

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        """Clicks and drags from a starting point to an ending point."""
        self.move_to(start_x, start_y)
        pyautogui.dragTo(end_x, end_y, duration=0.25, button="left")


if __name__ == "__main__":
    import time

    print("Initializing MouseController...")
    mouse: MouseController = MouseController()

    time.sleep(3)

    screen_width: int
    screen_height: int
    screen_width, screen_height = pyautogui.size()

    center_x: int = screen_width // 2
    center_y: int = screen_height // 2

    print(f"Moving to center: ({center_x}, {center_y})")
    mouse.move_to(center_x, center_y)
    print("Test completed.")
