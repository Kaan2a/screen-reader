"""
@ai-context: Monitors CPU, RAM, and execution time of heavy vision models.
Ensures ML inferences run non-blocking via executors to keep the main GUI responsive.
"""

import functools
import os
import time
from collections.abc import Callable
from typing import Any

import psutil


# Generic tip tanimi, dekore edilen fonksiyonun orjinal tipini korumasi icin.
def profile_performance[T: Callable[..., Any]](func: T) -> T:
    """
    Belirtilen fonksiyonun calisma suresini (ms), tukettigi ekstra RAM miktarini (MB)
    ve anlik CPU kullanim artisini (%) hesaplayip konsola yazdirir.

    Args:
        func (Callable): Olculmek istenen fonksiyon.

    Returns:
        Callable: Dekore edilmis fonksiyon, orjinal degeri dondurur.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        process = psutil.Process(os.getpid())

        # Baslangic metrikleri
        start_time: float = time.perf_counter()
        start_mem: float = process.memory_info().rss / (1024 * 1024)

        # Psutil CPU yüzdesini ölçmek için önce bir kez çağırmak gerekir (aralığı belirlemek için)
        process.cpu_percent(interval=None)

        # Fonksiyonu calistir
        result: Any = func(*args, **kwargs)

        # Bitis metrikleri
        end_time: float = time.perf_counter()
        end_mem: float = process.memory_info().rss / (1024 * 1024)
        cpu_usage: float = process.cpu_percent(interval=None)

        execution_time_ms: float = (end_time - start_time) * 1000
        mem_diff: float = end_mem - start_mem

        print(f"[Profiler] {func.__name__} Tamamlandi:")
        print(f"  - Sure     : {execution_time_ms:.2f} ms")
        print(f"  - Extra RAM: {mem_diff:+.2f} MB")
        print(f"  - Anlik CPU: {cpu_usage:.1f}%")

        return result

    return wrapper  # type: ignore[return-value]
