"""
@ai-context: Hardware abstraction utility for detecting best available computation device.
Supports CUDA, DirectML, and CPU backends.
"""

import torch
import logging

logger = logging.getLogger(__name__)

def get_best_device() -> str:
    """Detects and returns the best available device string for torch."""
    if torch.cuda.is_available():
        return "cuda"
    
    # Check for DirectML (requires torch-directml or similar)
    try:
        import torch_directml
        if torch_directml.is_available():
            return "privateuseone:0"
    except ImportError:
        pass
        
    return "cpu"

def get_compute_type(device: str) -> str:
    """Returns recommended compute type (float16/int8/float32) for a device."""
    if device == "cuda":
        return "float16"
    return "float32"
