"""
@ai-context: Web automation layer using Playwright and CDP.
Enables high-speed browser interactions.
Features Florence-2 visual fallback for unselectable elements.
"""

import logging
import numpy as np

try:
    from playwright.sync_api import sync_playwright, Playwright, BrowserContext, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

from src.vision.florence_engine import FlorenceEngine
import pyautogui

logger = logging.getLogger(__name__)

SELECTORS: dict[str, dict[str, str]] = {
    "youtube": {
        "like": "like-button-view-model button",
        "play": ".ytp-play-button",
        "skip_ad": ".ytp-ad-skip-button"
    }
}

class PlaywrightLayer:
    """Async or standard Playwright manager (Placeholder for future async operations)."""
    def __init__(self) -> None:
        logger.info("[PlaywrightLayer] Initialized.")

class SyncPlaywrightLayer:
    """Synchronous Playwright manager with visual fallback capabilities."""
    
    def __init__(self, cdp_port: int = 9222) -> None:
        self.cdp_url = f"http://localhost:{cdp_port}"
        self.playwright: "Playwright | None" = None
        self.browser: "BrowserContext | None" = None
        self.florence: FlorenceEngine | None = None
        
        logger.info("[SyncPlaywrightLayer] Initialized.")
        
    def _connect(self) -> "Page | None":
        """Connects to an existing Chrome instance via CDP."""
        if not HAS_PLAYWRIGHT:
            logger.error("[SyncPlaywrightLayer] Playwright is not installed.")
            return None
            
        try:
            if not self.playwright:
                self.playwright = sync_playwright().start()
            
            if not self.browser:
                self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
                
            pages = self.browser.contexts[0].pages
            if pages:
                return pages[0] # Return active page
            return None
        except Exception as e:
            logger.error(f"[SyncPlaywrightLayer] CDP Connection failed: {e}")
            return None

    def _florence_fallback(self, action: str, target: str, screenshot_np: np.ndarray | None) -> bool:
        """Fallback to visual detection if CDP fails."""
        if screenshot_np is None:
            logger.error("[SyncPlaywrightLayer] Florence fallback failed: No screenshot provided.")
            return False
            
        logger.info(f"[SyncPlaywrightLayer] Engaging Florence fallback for {action} on {target}...")
        
        if not self.florence:
            # Lazy load Florence to save memory
            self.florence = FlorenceEngine()
            
        # Determine visual query based on intended action
        query = f"{target} {action}"
        if "beğen" in action.lower() or "like" in action.lower() or target.lower() == "like":
            query = "like button"
            
        result = self.florence.find_element(screenshot_np, query)
        
        if result:
            logger.info(f"[SyncPlaywrightLayer] Florence found element at x={result['x']}, y={result['y']}.")
            try:
                # Use OS layer/PyAutoGUI for the physical click
                pyautogui.click(x=int(result["x"]), y=int(result["y"]))
                return True
            except Exception as e:
                logger.error(f"[SyncPlaywrightLayer] Fallback click failed: {e}")
                return False
            
        logger.warning(f"[SyncPlaywrightLayer] Florence fallback failed to find '{query}'.")
        return False

    def execute_action(self, action: str, target: str, screenshot_np: np.ndarray | None = None) -> bool:
        """
        Executes a web action. Uses ultra-fast CDP Playwright first,
        falls back to Florence-2 visual interaction on failure.
        """
        success = False
        page = self._connect()
        
        if page:
            try:
                if target in SELECTORS and action in SELECTORS[target]:
                    selector = SELECTORS[target][action]
                    logger.info(f"[SyncPlaywrightLayer] Trying CDP click on selector: {selector}")
                    
                    # 50ms timeout for ultra-fast execution requirement
                    page.locator(selector).click(timeout=50)
                    success = True
                    logger.info("[SyncPlaywrightLayer] CDP click successful (<50ms).")
                else:
                    logger.warning(f"[SyncPlaywrightLayer] No predefined selector for {target}->{action}.")
            except Exception as e:
                logger.warning(f"[SyncPlaywrightLayer] CDP interaction failed: {e}")
                
        # Automatic Fallback to Florence if CDP failed
        if not success:
            success = self._florence_fallback(action, target, screenshot_np)
            
        return success
        
    def cleanup(self) -> None:
        """Closes browser connections and stops Playwright."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
