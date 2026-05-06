"""
@ai-context: Monitors CPU, RAM, and execution time of heavy vision models.
Ensures ML inferences run non-blocking via executors to keep the main GUI responsive.
"""

import functools
import os
import time
import logging
from collections.abc import Callable
from typing import ParamSpec, TypeVar

import psutil

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

# Generic tip tanimi, dekore edilen fonksiyonun orjinal tipini korumasi icin.
def profile_performance(func: Callable[P, R]) -> Callable[P, R]:
    """
    Belirtilen fonksiyonun calisma suresini (ms), tukettigi ekstra RAM miktarini (MB)
    ve anlik CPU kullanim artisini (%) hesaplayip konsola yazdirir.

    Args:
        func (Callable): Olculmek istenen fonksiyon.

    Returns:
        Callable: Dekore edilmis fonksiyon, orjinal degeri dondurur.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        process = psutil.Process(os.getpid())

        # Baslangic metrikleri
        start_time: float = time.perf_counter()
        start_mem: float = process.memory_info().rss / (1024 * 1024)

        # Psutil CPU yüzdesini ölçmek için önce bir kez çağırmak gerekir (aralığı belirlemek için)
        process.cpu_percent(interval=None)

        # Fonksiyonu calistir
        result: R = func(*args, **kwargs)

        # Bitis metrikleri
        end_time: float = time.perf_counter()
        end_mem: float = process.memory_info().rss / (1024 * 1024)
        cpu_usage: float = process.cpu_percent(interval=None)

        execution_time_ms: float = (end_time - start_time) * 1000
        mem_diff: float = end_mem - start_mem

        logger.info(f"[Profiler] {func.__name__} Tamamlandi:")
        logger.info(f"  - Sure     : {execution_time_ms:.2f} ms")
        logger.info(f"  - Extra RAM: {mem_diff:+.2f} MB")
        logger.info(f"  - Anlik CPU: {cpu_usage:.1f}%")

        return result

    return wrapper  # type: ignore[return-value]
