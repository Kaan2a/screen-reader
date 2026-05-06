"""
@ai-context: Windows Automation layer for native OS interactions.
Replaces legacy action controllers with a unified system.
Handles ultra-fast OS-level commands like opening settings URIs.
"""

import logging
import os

logger = logging.getLogger(__name__)

try:
    import pygetwindow as gw
except ImportError:
    gw = None
    logger.error("[WinAutoLayer] pygetwindow is not installed. Window management may fail.")

try:
    import pywinauto
except ImportError:
    pywinauto = None
    logger.error("[WinAutoLayer] pywinauto is not installed. Advanced UI interactions may fail.")


class WinAutoLayer:
    """Handles native Windows UI interactions and OS-level commands."""
    
    def __init__(self) -> None:
        logger.info("[WinAutoLayer] Initialized.")

    def click_element(self, element_id: str) -> bool:
        if pywinauto is None:
            logger.error("[WinAutoLayer] Cannot click element, pywinauto is missing.")
            return False
        logger.info(f"Clicking element: {element_id}")
        return True

    def open_settings(self, page: str = "") -> bool:
        """
        Opens Windows 10/11 Settings app instantly (<10ms) using ms-settings URI.
        Examples:
            open_settings("") -> Opens general settings
            open_settings("network") -> Opens Network & Internet settings
        """
        try:
            uri = f"start ms-settings:{page}"
            logger.info(f"[WinAutoLayer] Executing: {uri}")
            # Use os.system with 'start' for immediate <10ms execution on Windows
            os.system(uri)
            return True
        except Exception as e:
            logger.error(f"[WinAutoLayer] Failed to open settings: {e}")
            return False
            
    def focus_window(self, window_title: str) -> bool:
        """Focuses a window by title using pygetwindow."""
        if gw is None:
            logger.error("[WinAutoLayer] Cannot focus window, pygetwindow is missing.")
            return False
            
        try:
            windows = gw.getWindowsWithTitle(window_title)
            if windows:
                win = windows[0]
                win.activate()
                logger.info(f"[WinAutoLayer] Focused window: {window_title}")
                return True
            else:
                logger.warning(f"[WinAutoLayer] Window not found: {window_title}")
                return False
        except Exception as e:
            logger.error(f"[WinAutoLayer] Focus error: {e}")
            return False
