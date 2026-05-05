"""
@ai-context: Extracts text and calculates precise bounding box
coordinates from screen captures using EasyOCR for UI text
interactions. Optimized with image downscaling for faster processing.
"""

import cv2
import easyocr
import numpy as np
import torch

from src.utils.profiler import profile_performance
from src.utils.device_utils import get_best_device


class OcrAnalyzer:
    """
    OCR detection module using EasyOCR for reading UI text.
    Automatically uses GPU if available.
    """

    # Maximum width for OCR processing (wider images are downscaled)
    _MAX_OCR_WIDTH: int = 1280

    def __init__(self) -> None:
        """Initializes the EasyOCR reader for Turkish and English."""
        self.device_name = get_best_device()
        self.use_gpu: bool = self.device_name != "cpu"
        self.reader = easyocr.Reader(["tr", "en"], gpu=self.use_gpu)

    @profile_performance
    def extract_text(self, image: np.ndarray) -> list[dict[str, str | float]]:
        """Reads text from the image and extracts bounding boxes."""
        height, width = image.shape[:2]
        scale_ratio = 1.0
        process_image = image

        # Performans icin cozunurluk yuksekse goruntuyu kucult
        if width > self._MAX_OCR_WIDTH:
            scale_ratio = self._MAX_OCR_WIDTH / width
            new_width = self._MAX_OCR_WIDTH
            new_height = int(height * scale_ratio)
            process_image = cv2.resize(
                image, (new_width, new_height), interpolation=cv2.INTER_LINEAR
            )

        raw_results = self.reader.readtext(process_image)

        detected_texts: list[dict[str, str | float]] = []

        inv_scale: float = 1.0 / scale_ratio  # to map coords back to original

        for bbox, text, confidence in raw_results:
            x_coords: list[float] = [float(pt[0]) * inv_scale for pt in bbox]
            y_coords: list[float] = [float(pt[1]) * inv_scale for pt in bbox]

            x_min: float = min(x_coords)
            x_max: float = max(x_coords)
            y_min: float = min(y_coords)
            y_max: float = max(y_coords)

            center_x: float = (x_min + x_max) / 2.0
            center_y: float = (y_min + y_max) / 2.0
            box_width: float = x_max - x_min
            box_height: float = y_max - y_min

            detected_texts.append(
                {
                    "text": str(text),
                    "x": center_x,
                    "y": center_y,
                    "w": box_width,
                    "h": box_height,
                    "confidence": float(confidence),
                }
            )

        return detected_texts


if __name__ == "__main__":
    import time

    print("Initializing OcrAnalyzer...")
    analyzer: OcrAnalyzer = OcrAnalyzer()

    dummy_image: np.ndarray = np.zeros((1080, 1920, 3), dtype=np.uint8)

    print("Running OCR on dummy image...")
    start_time: float = time.time()

    results: list[dict[str, str | float]] = analyzer.extract_text(dummy_image)

    end_time: float = time.time()
    elapsed_ms: float = (end_time - start_time) * 1000

    print(f"Extraction completed in {elapsed_ms:.2f} ms. Found {len(results)} texts.")

    for item in results:
        print(item)
