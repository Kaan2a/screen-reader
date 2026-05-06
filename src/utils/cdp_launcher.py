"""
@ai-context: Chrome DevTools Protocol (CDP) auto-launcher.
Called during main.py startup. Detects if a browser is already in debug mode;
if not, it automatically launches the first compatible browser found (Brave > Chrome > Edge)
with the remote debugging port enabled.
"""

import os
import subprocess
import logging
import time

try:
    import requests
    _requests_ok = True
except ImportError:
    _requests_ok = False

logger = logging.getLogger(__name__)

CDP_PORT: int = 9222

# Browser priority: Brave > Chrome > Edge
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
    """Returns True if the CDP debug port is responsive."""
    if not _requests_ok:
        return False
    try:
        r = requests.get(f"http://localhost:{port}/json/version", timeout=1.0)
        if r.status_code == 200:
            browser_name = r.json().get("Browser", "Unknown")
            logger.info(f"[CDP] Active connection: {browser_name} (port {port})")
            return True
    except Exception:
        pass
    return False


def _find_browser() -> tuple[str, str] | None:
    """Returns the name and path of the first installed compatible browser."""
    for name, paths in _BROWSER_PATHS:
        for path in paths:
            if os.path.isfile(path):
                return name, path
    return None


def ensure_cdp_ready(port: int = CDP_PORT, wait_sec: float = 4.0) -> bool:
    """
    Ensures CDP is ready by launching the browser in debug mode if necessary.

    Returns:
        bool: True if CDP is active and ready for connection.
    """
    # 1. Is it already active?
    if is_cdp_active(port):
        return True

    # 2. Find compatible browser
    found = _find_browser()
    if not found:
        logger.warning(
            "[CDP] No compatible browser (Brave, Chrome, or Edge) found on the system. "
            "CDP disabled — 'like/pause' commands will use VLM fallback."
        )
        return False

    name, exe_path = found
    logger.info(f"[CDP] Launching {name} in debug mode (--remote-debugging-port={port})...")

    try:
        subprocess.Popen(
            [exe_path, f"--remote-debugging-port={port}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS  # Windows background process
        )
    except Exception as e:
        logger.error(f"[CDP] Failed to start {name}: {e}")
        return False

    # 3. Wait for connection (0.5s intervals)
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        time.sleep(0.5)
        if is_cdp_active(port):
            logger.info(f"[CDP] ✓ {name} is ready! Debug connection established.")
            return True

    logger.warning(
        f"[CDP] {name} was launched but debug connection failed within {wait_sec}s.\n"
        "       Possible cause: Browser already open without debug mode. Please close it and retry."
    )
    return False
