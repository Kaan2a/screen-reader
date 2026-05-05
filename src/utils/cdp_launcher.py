"""
@ai-context: Chrome DevTools Protocol (CDP) otomatik başlatıcı.
main.py açılışında çağrılır. Tarayıcı zaten debug modunda açıksa dokunmaz,
kapalıysa sistemdeki ilk uyumlu tarayıcıyı (Brave > Chrome > Edge) debug
moduyla otomatik başlatır.
"""

import os
import subprocess
import logging
import time
from typing import Optional

try:
    import requests
    _requests_ok = True
except ImportError:
    _requests_ok = False

logger = logging.getLogger(__name__)

CDP_PORT: int = 9222

# Tarayıcı öncelik sırası: Brave > Chrome > Edge
_BROWSER_PATHS: list[tuple[str, list[str]]] = [
    ("Brave", [
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]),
    ("Chrome", [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    ]),
    ("Edge", [
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
    ]),
]


def is_cdp_active(port: int = CDP_PORT) -> bool:
    """CDP debug portuna başarıyla bağlanabiliyorsa True döner."""
    if not _requests_ok:
        return False
    try:
        r = requests.get(f"http://localhost:{port}/json/version", timeout=1.0)
        if r.status_code == 200:
            browser_name = r.json().get("Browser", "Bilinmeyen")
            logger.info(f"[CDP] Aktif bağlantı: {browser_name} (port {port})")
            return True
    except Exception:
        pass
    return False


def _find_browser() -> Optional[tuple[str, str]]:
    """Sistemde kurulu ilk tarayıcının adını ve exe yolunu döner."""
    for name, paths in _BROWSER_PATHS:
        for path in paths:
            if os.path.isfile(path):
                return name, path
    return None


def ensure_cdp_ready(port: int = CDP_PORT, wait_sec: float = 4.0) -> bool:
    """
    CDP hazır değilse tarayıcıyı debug moduyla otomatik başlatır.

    Dönüş:
        True  → CDP aktif ve kullanıma hazır
        False → Tarayıcı bulunamadı veya bağlantı kurulamadı
    """
    # 1. Zaten açık mı?
    if is_cdp_active(port):
        return True

    # 2. Uygun tarayıcıyı bul
    found = _find_browser()
    if not found:
        logger.warning(
            "[CDP] Systemde Brave, Chrome veya Edge bulunamadı. "
            "CDP devre dışı — 'like' gibi komutlar VLM fallback ile çalışacak."
        )
        return False

    name, exe_path = found
    logger.info(f"[CDP] {name} debug modunda başlatılıyor (--remote-debugging-port={port})...")

    try:
        subprocess.Popen(
            [exe_path, f"--remote-debugging-port={port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS  # Windows: arka planda kalır
        )
    except Exception as e:
        logger.error(f"[CDP] {name} başlatma hatası: {e}")
        return False

    # 3. Bağlantı gelene kadar bekle (0.5s aralıklarla)
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        time.sleep(0.5)
        if is_cdp_active(port):
            logger.info(f"[CDP] ✓ {name} hazır! Debug bağlantısı kuruldu.")
            return True

    logger.warning(
        f"[CDP] {name} başlatıldı ama {wait_sec}s içinde debug bağlantısı kurulamadı.\n"
        "       Olası neden: Tarayıcı zaten debug'siz açık. Kapatıp tekrar deneyin."
    )
    return False
