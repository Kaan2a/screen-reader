"""
@ai-context: Region of Interest (ROI) tabanlı Akıllı Önbellekleme sistemini içeren Görsel Kontrolcü.
3 modeli yönetir: EasyOCR, CLIP ve Moondream2.

DÜZELTMELER (v2):
- KRİTİK: full_screen_scan ve _scan_roi'deki string "in" karşılaştırması
  → rapidfuzz WRatio + Türkçe normalize ile değiştirildi.
  Eski: target "müzikler", OCR "Muzikier" → "muzikier" in "müzikler" → False → None
  Yeni: normalize("müzikler") ~= normalize("Muzikier") → WRatio ~85 → eşleşti
- Eşik: WRatio >= 70 (ayarlanabilir)
- pyautogui import kaldırıldı (bu modülde kullanılmıyordu)
"""

import logging
from typing import Optional, Union

import cv2
import numpy as np

from src.vision.ocr_analyzer import OcrAnalyzer
from src.vision.semantic_matcher import SemanticVision
from src.vision.moondream_analyzer import MoondreamAnalyzer

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    import difflib
    _RAPIDFUZZ_AVAILABLE = False

logger = logging.getLogger(__name__)


# ─── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _normalize_tr(text: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirir, küçük harfe alır."""
    text = text.lower().strip()
    for tr_char, en_char in {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's',
        'ö': 'o', 'ç': 'c', 'î': 'i', 'â': 'a', 'û': 'u',
    }.items():
        text = text.replace(tr_char, en_char)
    return text


def _match_score(target: str, candidate: str) -> float:
    """
    İki string arasında normalize edilmiş benzerlik skoru (0–100).
    rapidfuzz varsa WRatio, yoksa difflib * 100.
    """
    norm_target = _normalize_tr(target)
    norm_candidate = _normalize_tr(candidate)

    # Hızlı yol: tam eşleşme veya içerme
    if norm_target == norm_candidate:
        return 100.0
    if norm_target in norm_candidate or norm_candidate in norm_target:
        return 90.0

    if _RAPIDFUZZ_AVAILABLE:
        return float(_fuzz.WRatio(norm_target, norm_candidate))
    else:
        return difflib.SequenceMatcher(None, norm_target, norm_candidate).ratio() * 100.0


# Eşik: bu değerin altındaki eşleşmeler reddedilir
_MATCH_THRESHOLD = 70.0


# ─── TypedDict ─────────────────────────────────────────────────────────────────

from typing import TypedDict

class CacheData(TypedDict):
    bbox: tuple[float, float, float, float]  # (center_x, center_y, width, height)
    resolution: tuple[int, int]              # (image_width, image_height)


# ─── Ana sınıf ─────────────────────────────────────────────────────────────────

class VisionController:
    """
    ROI tabanlı Akıllı Önbellekleme sistemini içeren Görsel Kontrolcü.
    """

    def __init__(
        self,
        ocr_analyzer: OcrAnalyzer,
        semantic_matcher: SemanticVision,
        moondream: Optional[MoondreamAnalyzer] = None,
    ) -> None:
        self.analyzer = ocr_analyzer
        self.semantic = semantic_matcher
        self.moondream = moondream
        self._cache: dict[str, CacheData] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    def find_target(
        self,
        target_name: str,
        full_image: np.ndarray,
    ) -> Optional[dict[str, Union[float, str]]]:
        """
        Önce ROI önbelleğine bakar, bulamazsa tam ekran aramasına geçer.
        """
        image_height, image_width = full_image.shape[:2]

        if target_name in self._cache:
            cache_data = self._cache[target_name]

            if cache_data["resolution"] == (image_width, image_height):
                logger.info(f"'{target_name}' için ROI önbelleği kullanılıyor.")
                roi_result = self._scan_roi(target_name, full_image, cache_data["bbox"])

                if roi_result is not None:
                    # Cache'i yeni konumla güncelle
                    self._cache[target_name] = {
                        "bbox": (
                            float(roi_result["x"]),
                            float(roi_result["y"]),
                            float(roi_result["w"]),
                            float(roi_result["h"]),
                        ),
                        "resolution": (image_width, image_height),
                    }
                    return roi_result
                else:
                    logger.warning(f"'{target_name}' ROI içinde bulunamadı. Önbellek temizleniyor.")
                    del self._cache[target_name]
            else:
                logger.info(f"'{target_name}' için çözünürlük değişmiş, önbellek geçersiz kılındı.")
                del self._cache[target_name]

        return self.full_screen_scan(target_name, full_image)

    def find_icon(
        self,
        target_name: str,
        full_image: np.ndarray,
    ) -> Optional[dict[str, Union[float, str]]]:
        """CLIP modelini kullanarak ekrandaki buton veya ikonları bulur."""
        logger.info(f"'{target_name}' ikonu aranıyor (CLIP)...")
        candidates = self._extract_candidates(full_image)

        if not candidates:
            return None

        crops = [c[0] for c in candidates]
        best_idx, score = self.semantic.find_best_match(target_name, crops)

        if best_idx != -1 and score > 0.05:
            best_bbox = candidates[best_idx][1]
            return {
                "x": best_bbox[0],
                "y": best_bbox[1],
                "w": best_bbox[2],
                "h": best_bbox[3],
                "confidence": score,
                "text": target_name,
            }

        return None

    def find_complex_element(
        self,
        target_name: str,
        full_image: np.ndarray,
    ) -> Optional[dict[str, Union[float, str]]]:
        """Moondream2 ile karmaşık UI öğelerini arar + OCR çift doğrulama."""
        if not self.moondream or not self.moondream.is_loaded:
            logger.warning("Moondream2 yüklü değil, karmaşık arama yapılamıyor.")
            return None

        logger.info(f"'{target_name}' karmaşık UI öğesi aranıyor (Moondream2)...")
        result = self.moondream.find_element_coordinates(full_image, target_name)

        if not result:
            logger.warning(f"'{target_name}' Moondream2 ile bulunamadı.")
            return None

        x, y = result["x"], result["y"]
        logger.info(f"Moondream2 ({x}, {y}) koordinatını önerdi. OCR doğrulaması yapılıyor...")

        padding = 75
        image_height, image_width = full_image.shape[:2]
        x_start = max(0, int(x - padding))
        y_start = max(0, int(y - padding))
        x_end = min(image_width, int(x + padding))
        y_end = min(image_height, int(y + padding))

        roi_image = full_image[y_start:y_end, x_start:x_end]
        ocr_results = self.analyzer.extract_text(roi_image)

        # FIX: OCR doğrulamasında da normalize + fuzzy kullan
        text_confirmed = any(
            _match_score(word, str(res["text"])) >= _MATCH_THRESHOLD
            for res in ocr_results
            for word in target_name.lower().split()
        )

        confidence = 0.95 if text_confirmed else 0.60
        status = "BAŞARILI" if text_confirmed else "BAŞARISIZ (ikon olabilir)"
        logger.info(f"OCR Çift Doğrulaması {status}! Güven: {confidence}")

        return {
            "x": float(x),
            "y": float(y),
            "w": 10.0,
            "h": 10.0,
            "confidence": confidence,
            "text": target_name,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def full_screen_scan(
        self,
        target_name: str,
        full_image: np.ndarray,
    ) -> Optional[dict[str, Union[float, str]]]:
        """
        Tam ekranda OCR araması yapar.
        FIX: string "in" yerine rapidfuzz WRatio + normalize kullanır.
        """
        logger.info(f"'{target_name}' için tam ekran (full_screen_scan) taraması yapılıyor.")
        image_height, image_width = full_image.shape[:2]

        results = self.analyzer.extract_text(full_image)

        best_result = None
        best_score = 0.0

        for obj in results:
            score = _match_score(target_name, str(obj["text"]))
            if score >= _MATCH_THRESHOLD and score > best_score:
                best_score = score
                best_result = obj

        if best_result is not None:
            logger.info(
                f"[OCR] '{target_name}' bulundu: '{best_result['text']}' "
                f"(skor: {best_score:.1f}) @ ({best_result['x']:.0f}, {best_result['y']:.0f})"
            )
            self._cache[target_name] = {
                "bbox": (
                    float(best_result["x"]),
                    float(best_result["y"]),
                    float(best_result["w"]),
                    float(best_result["h"]),
                ),
                "resolution": (image_width, image_height),
            }
            return {
                "x": float(best_result["x"]),
                "y": float(best_result["y"]),
                "w": float(best_result["w"]),
                "h": float(best_result["h"]),
                "confidence": float(best_result["confidence"]),
                "text": str(best_result["text"]),
            }

        return None

    def _scan_roi(
        self,
        target_name: str,
        full_image: np.ndarray,
        bbox: tuple[float, float, float, float],
    ) -> Optional[dict[str, Union[float, str]]]:
        """
        Belirtilen BBox etrafına 50px padding ekleyerek ROI taraması yapar.
        FIX: string "in" yerine rapidfuzz WRatio + normalize kullanır.
        """
        image_height, image_width = full_image.shape[:2]
        center_x, center_y, w, h = bbox
        padding = 50

        x_start = max(0, int(center_x - w / 2) - padding)
        y_start = max(0, int(center_y - h / 2) - padding)
        x_end = min(image_width, int(center_x + w / 2) + padding)
        y_end = min(image_height, int(center_y + h / 2) + padding)

        if x_start >= x_end or y_start >= y_end:
            return None

        roi_image = full_image[y_start:y_end, x_start:x_end]
        results = self.analyzer.extract_text(roi_image)

        best_result = None
        best_score = 0.0

        for obj in results:
            score = _match_score(target_name, str(obj["text"]))
            if score >= _MATCH_THRESHOLD and score > best_score:
                best_score = score
                best_result = obj

        if best_result is not None:
            return {
                "x": float(best_result["x"]) + float(x_start),
                "y": float(best_result["y"]) + float(y_start),
                "w": float(best_result["w"]),
                "h": float(best_result["h"]),
                "confidence": float(best_result["confidence"]),
                "text": str(best_result["text"]),
            }

        return None

    def _extract_candidates(
        self,
        image: np.ndarray,
    ) -> list[tuple[np.ndarray, tuple[float, float, float, float]]]:
        """Canny edge detection ile CLIP için aday bölgeler çıkarır."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 16 <= w <= 256 and 16 <= h <= 256:
                cx = float(x + w / 2.0)
                cy = float(y + h / 2.0)
                crop = image[y: y + h, x: x + w]
                candidates.append((crop, (cx, cy, float(w), float(h))))

        return candidates