import torch

def get_best_device() -> str:
    """
    Returns the best available device for PyTorch.
    Checks for CUDA (NVIDIA), DirectML (AMD/Intel on Windows), MPS (Mac), and falls back to CPU.
    """
    if torch.cuda.is_available():
        return "cuda"
    
    try:
        import torch_directml
        if torch_directml.is_available():
            # Return string to prevent torch.load crashes with DirectML device objects
            return "privateuseone:0"
    except ImportError:
        pass

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    
    return "cpu"
