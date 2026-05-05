"""
@ai-context: CLIP tabanlı görsel-metin eşleştirme sistemi.
OCR'ın okuyamadığı yazısız ikonları 'kavramsal' olarak bulur.

DÜZELTMELER (v2):
- KRİTİK: safe_query encode("ascii", errors="ignore") → _safe_clip_query()
  Eski kod: "beğen" → "" (boş string, CLIP hiçbir şeyle eşleşemiyordu)
  Yeni kod: "beğen" → "begen" (CLIP anlar, eşleşme çalışır)
- CLIP max token 77 sınırı korunuyor
- BGR→RGB dönüşümü zaten vardı, korundu
- try/except blokları güçlendirildi
"""

import logging

import cv2
import numpy as np
import torch
from PIL import Image

try:
    from transformers import CLIPModel, CLIPProcessor
except ImportError:
    raise ImportError(
        "HuggingFace 'transformers' kütüphanesi eksik. "
        "Lütfen 'pip install transformers' ile yükleyin."
    )

from src.utils.device_utils import get_best_device

logger = logging.getLogger(__name__)


# ─── Yardımcı fonksiyon ────────────────────────────────────────────────────────

def _safe_clip_query(query: str) -> str:
    """
    CLIP tokenizer için güvenli sorgu üretir.

    Problem: CLIP tokenizer'ı Türkçe karakterleri (ğ, ş, ı...) işleyebilir,
    ama bazı edge case'lerde 0xFD gibi geçersiz byte'lar utf-8 hatasına yol açar.

    Çözüm: Türkçe karakterleri Latin karşılığına map et — silme, dönüştür.
    "beğen" → "begen" ✓   (eski: "begen" → "" ✗)
    "müzik" → "muzik" ✓   (eski: "muzik" → "" ✗)
    "şarkı" → "sarki" ✓

    CLIP max token 77 — uzun query'leri kırp.
    """
    replacements = {
        'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U',
        'ş': 's', 'Ş': 'S',
        'ı': 'i', 'İ': 'I',
        'ö': 'o', 'Ö': 'O',
        'ç': 'c', 'Ç': 'C',
        'î': 'i', 'â': 'a', 'û': 'u',
    }
    for tr_char, en_char in replacements.items():
        query = query.replace(tr_char, en_char)

    # ASCII dışı kalan karakterleri kaldır (emoji vb.)
    query = query.encode("ascii", errors="ignore").decode("ascii")

    # Boş kaldıysa orijinalin ilk 32 karakterini kullan (son çare)
    query = query.strip()
    if not query:
        logger.warning("[CLIP] Query normalize sonrası boş kaldı, orijinal kullanılıyor.")
        # En azından bir şey gönder
        return "icon button"

    return query[:77]  # CLIP max token sınırı


# ─── Ana sınıf ─────────────────────────────────────────────────────────────────

class SemanticVision:
    """
    CLIP tabanlı görsel-metin eşleştirme sistemi.
    OCR'ın okuyamadığı yazısız ikonları 'kavramsal' olarak bulur.
    """

    def __init__(self) -> None:
        self.device: str = "cpu"
        self.model_name: str = "Jl-wei/uiclip-vit-base-patch32"

        logger.info(f"Yükleniyor (CLIP): {self.model_name} (Cihaz: {self.device})")

        try:
            self.model: CLIPModel = CLIPModel.from_pretrained(self.model_name, torch_dtype=torch.float32).to(self.device)
            self.processor: CLIPProcessor = CLIPProcessor.from_pretrained(self.model_name)
            self.model.eval()
            logger.info("CLIP modeli başarıyla yüklendi.")
        except Exception as e:
            logger.error(f"CLIP modeli yüklenirken hata oluştu: {e}")
            raise e

    def find_best_match(
        self,
        query: str,
        cropped_images: list[np.ndarray],
    ) -> tuple[int, float]:
        """
        Verilen OpenCV resim kırpıntıları arasında metin sorgusuna
        kavramsal olarak en uygun olanın indeksini ve olasılık skorunu döndürür.

        Returns:
            (index, score) — bulunamazsa (-1, 0.0)
        """
        if not cropped_images or not query:
            return -1, 0.0

        # FIX: ASCII'ye çevirirken Türkçe karakterleri SİLMEK yerine MAP et
        safe_query = _safe_clip_query(query)
        logger.debug(f"[CLIP] Query: '{query}' → safe: '{safe_query}'")

        pil_images: list[Image.Image] = []
        valid_indices: list[int] = []

        # Her resmi ayrı dönüştür — biri bozuk olsa diğerleri etkilenmesin
        for idx, img in enumerate(cropped_images):
            try:
                # uint8'e normalize et
                if img.dtype != np.uint8:
                    img = np.clip(img, 0, 255).astype(np.uint8)

                # Çok küçük/boş kırpıntıları atla
                if img.size == 0 or img.shape[0] < 4 or img.shape[1] < 4:
                    continue

                # BGR/BGRA → RGB dönüşümü
                if len(img.shape) == 3 and img.shape[2] == 4:
                    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                elif len(img.shape) == 3 and img.shape[2] == 3:
                    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                elif len(img.shape) == 2:
                    rgb_img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                else:
                    rgb_img = img.copy()

                pil_images.append(Image.fromarray(rgb_img))
                valid_indices.append(idx)

            except Exception as img_err:
                logger.debug(f"Resim {idx} dönüştürülemedi, atlanıyor: {img_err}")
                continue

        if not pil_images:
            logger.warning("[CLIP] Geçerli resim kırpıntısı bulunamadı.")
            return -1, 0.0

        try:
            inputs = self.processor(
                text=[safe_query],
                images=pil_images,
                return_tensors="pt",
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            logits_per_text: torch.Tensor = outputs.logits_per_text
            probs: torch.Tensor = logits_per_text.softmax(dim=1)
            probs_list: list[float] = probs.cpu().numpy()[0].tolist()

            max_score: float = max(probs_list)
            local_best_idx: int = probs_list.index(max_score)
            original_idx = valid_indices[local_best_idx]

            logger.info(
                f"[CLIP] '{safe_query}' → indeks {original_idx}, skor {max_score:.3f}"
            )
            return original_idx, max_score

        except Exception as e:
            logger.error(f"[CLIP] SemanticVision eşleştirme hatası: {e}")
            return -1, 0.0