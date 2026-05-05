"""
@ai-context: High-speed screen capturing module using mss and
OpenCV. Converts captures to BGR format optimized for AI models.
"""

import cv2
import mss
import numpy as np


class ScreenCapturer:
    """
    High-speed screen capture using mss.
    Converts captures to BGR format by stripping Alpha channel.
    """

    def __init__(self) -> None:
        """Initialize mss object once to avoid repeated overhead."""
        self.sct = mss.MSS()
        self.monitor: dict[str, int] = self.sct.monitors[1]

    def capture_primary_screen(self) -> np.ndarray:
        """
        Captures the primary monitor screen and removes alpha channel.

        Returns:
            np.ndarray: The captured frame in BGR format.
        """
        sct_img = self.sct.grab(self.monitor)
        img_array: np.ndarray = np.array(sct_img)
        bgr_array: np.ndarray = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
        return bgr_array


if __name__ == "__main__":
    import time

    capturer = ScreenCapturer()

    start: float = time.time()
    frame: np.ndarray = capturer.capture_primary_screen()
    end: float = time.time()

    print(f"Shape: {frame.shape}")
    print(f"Time: {(end - start) * 1000:.2f} ms")
