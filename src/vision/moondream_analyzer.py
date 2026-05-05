import logging
import torch
import cv2
import numpy as np
from PIL import Image
import re

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
except ImportError:
    AutoModelForCausalLM = None
    AutoTokenizer = None
    BitsAndBytesConfig = None

from src.utils.device_utils import get_best_device

logger = logging.getLogger(__name__)

class MoondreamAnalyzer:
    """
    Karmaşık UI analizleri, form doldurma ve bounding box tahmini için moondream2 katmanı.
    EasyOCR ile çift doğrulama (double-check) destekler.
    """
    def __init__(self, model_id: str = "vikhyatk/moondream2", revision: str = "2024-08-26"):
        if AutoModelForCausalLM is None:
            logger.warning("'transformers' eksik! Moondream2 başlatılamadı.")
            self.is_loaded = False
            return
            
        self.device = get_best_device()
        logger.info(f"Yükleniyor (Moondream2): {model_id} (Cihaz: {self.device})")
        
        try:
            if self.device == "cuda":
                # GPU varsa 4-bit quantization dene
                from transformers import BitsAndBytesConfig as BnB
                bnb_config = BnB(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                    revision=revision,
                    quantization_config=bnb_config,
                    torch_dtype=torch.float16
                )
                logger.info("CUDA: 4-bit quantization ile yüklendi.")
            elif "privateuseone" in str(self.device):
                # AMD / DirectML: 4-bit desteklenmez ama float16 hizlidir
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                    revision=revision,
                    torch_dtype=torch.float16
                ).to(self.device)
                logger.info(f"DirectML (AMD): float16 ile yüklendi. (Cihaz: {self.device})")
            else:
                # CPU: doğrudan float32, bitsandbytes kullanma
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                    revision=revision,
                    torch_dtype=torch.float32
                ).to(self.device)
                logger.info("CPU: float32 ile yüklendi.")
        except Exception as e:
            logger.error(f"Moondream2 yüklenemedi: {e}")
            self.is_loaded = False
            return

        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.is_loaded = True
        logger.info("Moondream2 başarıyla yüklendi.")

    def find_element_coordinates(self, image_np: np.ndarray, query: str) -> dict | None:
        """
        Moondream2'nin visual grounding (pointing) özelliğini kullanarak koordinat bulur.
        """
        if not self.is_loaded:
            return None
            
        # Pointing prompt
        prompt = f"Point out the {query}"
        image_pil = Image.fromarray(cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB))
        
        try:
            enc_image = self.model.encode_image(image_pil)
            answer = self.model.answer_question(enc_image, prompt, self.tokenizer)
            logger.info(f"[Moondream2] Pointing yanıtı ('{query}'): {answer}")
            
            # Koordinat çıkarma: "[x, y]"
            match = re.search(r'\[\s*(\d+)\s*,\s*(\d+)\s*\]', answer)
            if match:
                x_norm = int(match.group(1))
                y_norm = int(match.group(2))
                
                scale = 1000.0 if x_norm > 100 or y_norm > 100 else 100.0
                
                height, width = image_np.shape[:2]
                real_x = int((x_norm / scale) * width)
                real_y = int((y_norm / scale) * height)
                
                return {"x": real_x, "y": real_y, "confidence": 0.8}
        except Exception as e:
            logger.error(f"Moondream2 koordinat analizi başarısız: {e}")
            
        return None
