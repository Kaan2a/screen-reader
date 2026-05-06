"""
@ai-context: Florence-2 vision engine for advanced object detection and grounding.
Provides state-of-the-art visual understanding for UI elements using Microsoft's Florence-2.
"""

import logging
from typing import TypedDict
import numpy as np

logger = logging.getLogger(__name__)

try:
    from transformers import AutoModelForCausalLM, AutoProcessor
    import torch
    from PIL import Image
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

from src.utils.device_utils import get_best_device, get_compute_type

class FlorenceResult(TypedDict):
    x: float
    y: float
    w: float
    h: float
    text: str
    confidence: float
    method: str

class DetectionResult(TypedDict):
    label: str
    bbox: list[float]

class FlorenceEngine:
    def __init__(self, model_id: str = "microsoft/Florence-2-base") -> None:
        self.model_id = model_id
        self.is_loaded = False
        
        if not HAS_TRANSFORMERS:
            logger.warning("[FlorenceEngine] transformers library is missing. is_loaded=False.")
            return

        self.device = get_best_device()
        compute_type = get_compute_type(self.device)
        
        # Florence-2 works best with bfloat16 or float16 on GPU, float32 on CPU.
        if compute_type == "int8":
            torch_dtype = torch.float32
        elif compute_type == "float16":
            torch_dtype = torch.float16
        else:
            torch_dtype = torch.float32

        logger.info(f"[FlorenceEngine] Loading {model_id} on {self.device} with {torch_dtype}...")
        
        try:
            self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch_dtype, trust_remote_code=True).to(self.device)
            self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
            self.is_loaded = True
            logger.info("[FlorenceEngine] Model loaded successfully.")
        except Exception as e:
            logger.error(f"[FlorenceEngine] Failed to load model: {e}")
            self.is_loaded = False

    def _run_inference(self, image_np: np.ndarray, task_prompt: str, text_input: str | None = None) -> dict | None:
        if not self.is_loaded:
            return None
            
        try:
            # OpenCV provides BGR, PIL needs RGB
            image_pil = Image.fromarray(image_np[..., ::-1])
            prompt = task_prompt if text_input is None else task_prompt + text_input
            
            inputs = self.processor(text=prompt, images=image_pil, return_tensors="pt").to(self.device, self.model.dtype)
            
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                num_beams=3
            )
            
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = self.processor.post_process_generation(generated_text, task=task_prompt, image_size=(image_pil.width, image_pil.height))
            
            return parsed_answer
        except Exception as e:
            logger.error(f"[FlorenceEngine] Inference failed: {e}")
            return None

    def _ocr_search(self, image_np: np.ndarray, query: str) -> FlorenceResult | None:
        """Searches for text using OCR_WITH_REGION."""
        parsed_answer = self._run_inference(image_np, "<OCR_WITH_REGION>")
        if not parsed_answer:
            return None
            
        try:
            ocr_results = parsed_answer.get("<OCR_WITH_REGION>", {})
            labels = ocr_results.get("labels", [])
            # Florence-2 uses quad_boxes for OCR_WITH_REGION typically, but fallback to bboxes
            bboxes = ocr_results.get("quad_boxes", ocr_results.get("bboxes", []))
            
            query_lower = query.lower()
            
            for label, bbox in zip(labels, bboxes):
                if query_lower in label.lower():
                    if len(bbox) == 8: # quad box: [x1, y1, x2, y2, x3, y3, x4, y4]
                        xs = bbox[0::2]
                        ys = bbox[1::2]
                        x1, x2 = min(xs), max(xs)
                        y1, y2 = min(ys), max(ys)
                    else: # bounding box: [x1, y1, x2, y2]
                        x1, y1, x2, y2 = bbox
                        
                    w = x2 - x1
                    h = y2 - y1
                    x = x1 + w / 2
                    y = y1 + h / 2
                    
                    return FlorenceResult(
                        x=float(x),
                        y=float(y),
                        w=float(w),
                        h=float(h),
                        text=label,
                        confidence=1.0, # Confidence omitted in standard Florence outputs
                        method="OCR"
                    )
        except Exception as e:
            logger.error(f"[FlorenceEngine] OCR search error: {e}")
            
        return None

    def _grounding_search(self, image_np: np.ndarray, query: str) -> FlorenceResult | None:
        """Searches for objects using CAPTION_TO_PHRASE_GROUNDING."""
        parsed_answer = self._run_inference(image_np, "<CAPTION_TO_PHRASE_GROUNDING>", text_input=query)
        if not parsed_answer:
            return None
            
        try:
            grounding_results = parsed_answer.get("<CAPTION_TO_PHRASE_GROUNDING>", {})
            labels = grounding_results.get("labels", [])
            bboxes = grounding_results.get("bboxes", [])
            
            if labels and bboxes and len(bboxes) > 0:
                bbox = bboxes[0] # Take the first match
                x1, y1, x2, y2 = bbox
                w = x2 - x1
                h = y2 - y1
                x = x1 + w / 2
                y = y1 + h / 2
                
                return FlorenceResult(
                    x=float(x),
                    y=float(y),
                    w=float(w),
                    h=float(h),
                    text=query,
                    confidence=1.0,
                    method="Grounding"
                )
        except Exception as e:
            logger.error(f"[FlorenceEngine] Grounding search error: {e}")
            
        return None

    def find_element(self, image_np: np.ndarray, query: str) -> FlorenceResult | None:
        """Finds an element by first trying OCR, then Grounding fallback."""
        if not self.is_loaded:
            logger.warning(f"[FlorenceEngine] Model not loaded. Graceful fallback for '{query}'.")
            return None
            
        logger.info(f"[FlorenceEngine] Searching for '{query}' using OCR...")
        res = self._ocr_search(image_np, query)
        if res:
            return res
            
        logger.info(f"[FlorenceEngine] '{query}' not found via OCR. Trying Visual Grounding...")
        res = self._grounding_search(image_np, query)
        return res

    def detect_elements(self, image_np: np.ndarray) -> list[DetectionResult]:
        """Detects all objects in the image using OD (Object Detection)."""
        parsed_answer = self._run_inference(image_np, "<OD>")
        results: list[DetectionResult] = []
        if not parsed_answer:
            return results
            
        try:
            od_results = parsed_answer.get("<OD>", {})
            labels = od_results.get("labels", [])
            bboxes = od_results.get("bboxes", [])
            
            for label, bbox in zip(labels, bboxes):
                results.append(DetectionResult(label=label, bbox=bbox))
        except Exception as e:
            logger.error(f"[FlorenceEngine] Object detection error: {e}")
            
        return results
