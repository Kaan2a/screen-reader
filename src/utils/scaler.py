"""
@ai-context: Handles exact mathematical scaling and mapping between
AI vision coordinates and physical OS DPI resolutions to prevent
mouse miss-clicks.
"""

import ctypes


class CoordinateScaler:
    """
    Maps coordinates from AI vision/screenshot dimensions to physical
    OS screen dimensions, accounting for Windows DPI scaling.
    """

    def __init__(self) -> None:
        """Calculates the physical screen resolution using Windows API."""
        self.physical_width: int = 1920
        self.physical_height: int = 1080

        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            self.physical_width = int(user32.GetSystemMetrics(0))
            self.physical_height = int(user32.GetSystemMetrics(1))
        except Exception:
            pass

    def scale_point(
        self,
        x: float,
        y: float,
        source_width: int,
        source_height: int,
    ) -> tuple[int, int]:
        """Scales a single (X, Y) point to the physical OS resolution."""
        if source_width == 0 or source_height == 0:
            return int(x), int(y)

        scale_x: float = self.physical_width / float(source_width)
        scale_y: float = self.physical_height / float(source_height)

        target_x: int = int(round(x * scale_x))
        target_y: int = int(round(y * scale_y))

        return target_x, target_y

    def scale_box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        source_w: int,
        source_h: int,
    ) -> tuple[int, int, int, int]:
        """Scales a bounding box to the physical OS resolution."""
        if source_w == 0 or source_h == 0:
            return int(x), int(y), int(w), int(h)

        scale_x: float = self.physical_width / float(source_w)
        scale_y: float = self.physical_height / float(source_h)

        target_x: int = int(round(x * scale_x))
        target_y: int = int(round(y * scale_y))
        target_w: int = int(round(w * scale_x))
        target_h: int = int(round(h * scale_y))

        return target_x, target_y, target_w, target_h


if __name__ == "__main__":
    print("Initializing CoordinateScaler...")
    scaler: CoordinateScaler = CoordinateScaler()
    print(f"Detected Physical Resolution: {scaler.physical_width}x{scaler.physical_height}")

    scaler.physical_width = 1920
    scaler.physical_height = 1080

    result_pt: tuple[int, int] = scaler.scale_point(320.0, 320.0, 640, 640)
    print("\nScaling (320, 320) from 640x640 to 1920x1080:")
    print(f"Result: {result_pt}")

    result_box: tuple[int, int, int, int] = scaler.scale_box(320.0, 320.0, 100.0, 100.0, 640, 640)
    print("\nScaling box (100x100) from 640x640 to 1920x1080:")
    print(f"Result: {result_box}")
