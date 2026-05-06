"""
@ai-context: API layer for orchestrating web and OS-level interactions.
Manages Spotify API, Chrome DevTools Protocol (CDP), and hardware media keys.
"""

import os
import json
import logging
import pyautogui
import requests

try:
    import websocket
except ImportError:
    websocket = None

logger = logging.getLogger(__name__)

class MediaKeysController:
    """
    General Media Control
    Uses OS media keys to provide hardware-level music/video control (<10ms).
    """
    def play_pause(self) -> bool:
        pyautogui.press('playpause')
        logger.info("[OS Media] Play/Pause command sent.")
        return True

    def next_track(self) -> bool:
        pyautogui.press('nexttrack')
        logger.info("[OS Media] Next track command sent.")
        return True

    def prev_track(self) -> bool:
        pyautogui.press('prevtrack')
        logger.info("[OS Media] Previous track command sent.")
        return True

    def volume_up(self, amount: int = 5) -> bool:
        for _ in range(amount):
            pyautogui.press('volumeup')
        logger.info(f"[OS Media] Volume increased by {amount} steps.")
        return True

    def volume_down(self, amount: int = 5) -> bool:
        for _ in range(amount):
            pyautogui.press('volumedown')
        logger.info(f"[OS Media] Volume decreased by {amount} steps.")
        return True


class SpotifyAPIController:
    """
    Spotify HTTP API
    Latency < 50ms. Sends background network requests to control playback.
    Note: Requires SPOTIFY_ACCESS_TOKEN environment variable.
    """
    def __init__(self) -> None:
        self.token = os.environ.get("SPOTIFY_ACCESS_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.base_url = "https://api.spotify.com/v1/me/player"

    def is_configured(self) -> bool:
        return bool(self.token)

    def play(self) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.put(f"{self.base_url}/play", headers=self.headers, timeout=1)
            logger.info("[Spotify API] Play request sent.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Play error: {e}")
            return False

    def pause(self) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.put(f"{self.base_url}/pause", headers=self.headers, timeout=1)
            logger.info("[Spotify API] Pause request sent.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Pause error: {e}")
            return False

    def next_track(self) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.post(f"{self.base_url}/next", headers=self.headers, timeout=1)
            logger.info("[Spotify API] Next request sent.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Next error: {e}")
            return False

    def prev_track(self) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.post(f"{self.base_url}/previous", headers=self.headers, timeout=1)
            logger.info("[Spotify API] Previous request sent.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Previous error: {e}")
            return False

    def shuffle(self, state: bool = True) -> bool:
        if not self.is_configured(): return False
        try:
            state_str = "true" if state else "false"
            r = requests.put(f"{self.base_url}/shuffle?state={state_str}", headers=self.headers, timeout=1)
            logger.info(f"[Spotify API] Shuffle {state_str} request sent.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Shuffle error: {e}")
            return False

    def repeat(self, state: str = "context") -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.put(f"{self.base_url}/repeat?state={state}", headers=self.headers, timeout=1)
            logger.info(f"[Spotify API] Repeat {state} request sent.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Repeat error: {e}")
            return False

    def set_volume(self, percent: int) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.put(f"{self.base_url}/volume?volume_percent={percent}", headers=self.headers, timeout=1)
            logger.info(f"[Spotify API] Volume {percent} request sent.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Volume error: {e}")
            return False


class ChromeCDPController:
    """
    Chrome DevTools Protocol (CDP) Controller
    Injects JS into active browser tabs (e.g., YouTube) with millisecond latency.
    (Chrome must be started with '--remote-debugging-port=9222')
    """
    def __init__(self, port: int = 9222) -> None:
        self.port = port
        self.base_url = f"http://localhost:{self.port}/json"
        if websocket is None:
            logger.warning("'websocket-client' library is missing. CDP operations may fail.")

    def _get_tab_ws_url(self, keyword: str) -> str | None:
        try:
            r = requests.get(self.base_url, timeout=1)
            tabs = r.json()
            for tab in tabs:
                url = tab.get("url", "").lower()
                title = tab.get("title", "").lower()
                if keyword.lower() in url or keyword.lower() in title:
                    return tab.get("webSocketDebuggerUrl")
        except Exception:
            return None
        return None

    def execute_js(self, keyword: str, js_code: str) -> bool:
        if websocket is None:
            return False
            
        ws_url = self._get_tab_ws_url(keyword)
        if not ws_url:
            logger.warning(f"CDP: Tab containing '{keyword}' not found or debugging is disabled.")
            return False

        try:
            ws = websocket.create_connection(ws_url, timeout=1.5)
            payload = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code
                }
            }
            ws.send(json.dumps(payload))
            ws.recv()  # Wait for response
            ws.close()
            logger.info(f"[CDP API] JS injected into '{keyword}' tab.")
            return True
        except Exception as e:
            logger.error(f"[CDP API] JS Inject error: {e}")
            return False

    def youtube_play_pause(self) -> bool:
        js = "document.querySelector('.ytp-play-button')?.click();"
        return self.execute_js("youtube", js)

    def youtube_like(self) -> bool:
        js = "document.querySelector('like-button-view-model button')?.click();"
        return self.execute_js("youtube", js)

    def youtube_dislike(self) -> bool:
        js = "document.querySelectorAll('like-button-view-model button')[1]?.click();"
        return self.execute_js("youtube", js)

    def youtube_skip_ad(self) -> bool:
        js = "document.querySelector('.ytp-ad-skip-button, .ytp-skip-ad-button, .ytp-ad-skip-button-modern')?.click();"
        return self.execute_js("youtube", js)

    def youtube_mute(self) -> bool:
        js = "document.querySelector('.ytp-mute-button')?.click();"
        return self.execute_js("youtube", js)

    def youtube_fullscreen(self) -> bool:
        js = "document.querySelector('.ytp-fullscreen-button')?.click();"
        return self.execute_js("youtube", js)

    def youtube_subscribe(self) -> bool:
        js = "document.querySelector('ytd-subscribe-button-renderer button')?.click();"
        return self.execute_js("youtube", js)

    # ------------------- NETFLIX -------------------
    def netflix_play_pause(self) -> bool:
        js = "document.querySelector('.button-nfplayerPlay')?.click();"
        return self.execute_js("netflix", js)

    def netflix_skip_intro(self) -> bool:
        js = "document.querySelector('.skip-credits a, .skip-credits button')?.click();"
        return self.execute_js("netflix", js)

    def netflix_next_episode(self) -> bool:
        js = "document.querySelector('.button-nfplayerNextEpisode')?.click();"
        return self.execute_js("netflix", js)

    def netflix_fullscreen(self) -> bool:
        js = "document.querySelector('.button-nfplayerFullscreen')?.click();"
        return self.execute_js("netflix", js)

    # ------------------- TWITCH -------------------
    def twitch_play_pause(self) -> bool:
        js = "document.querySelector('[data-a-target=\"player-play-pause-button\"]')?.click();"
        return self.execute_js("twitch", js)

    def twitch_mute(self) -> bool:
        js = "document.querySelector('[data-a-target=\"player-mute-unmute-button\"]')?.click();"
        return self.execute_js("twitch", js)

    def twitch_fullscreen(self) -> bool:
        js = "document.querySelector('[data-a-target=\"player-fullscreen-button\"]')?.click();"
        return self.execute_js("twitch", js)

    # ------------------- TWITTER / X -------------------
    def twitter_like(self) -> bool:
        js = "document.querySelector('[data-testid=\"like\"]')?.click();"
        return self.execute_js("twitter", js) or self.execute_js("x.com", js)

    def twitter_retweet(self) -> bool:
        js = "document.querySelector('[data-testid=\"retweet\"]')?.click();"
        return self.execute_js("twitter", js) or self.execute_js("x.com", js)

    # ------------------- PRIME VIDEO -------------------
    def prime_play_pause(self) -> bool:
        js = "document.querySelector('.atvwebplayersdk-playpause-button')?.click();"
        return self.execute_js("primevideo", js)

    def prime_skip_intro(self) -> bool:
        js = "document.querySelector('.atvwebplayersdk-skipelement-button')?.click();"
        return self.execute_js("primevideo", js)

    def prime_next_episode(self) -> bool:
        js = "document.querySelector('.atvwebplayersdk-nextup-button')?.click();"
        return self.execute_js("primevideo", js)

    # ------------------- SPOTIFY WEB -------------------
    def spotify_play_pause(self) -> bool:
        js = "document.querySelector('[data-testid=\"control-button-playpause\"]')?.click();"
        return self.execute_js("spotify", js)


class APILayer:
    """
    API Layer Manager
    Target Latency: < 50ms
    Orchestrates API / CDP connections for multiple web and desktop applications.
    """
    def __init__(self) -> None:
        self.media_keys = MediaKeysController()
        self.spotify = SpotifyAPIController()
        self.chrome = ChromeCDPController()

    def route_media_command(self, action: str, target: str = "os") -> bool:
        """
        Routes media commands to the most appropriate target.
        Example: route_media_command("play", "youtube")
        """
        target = target.lower()
        
        # 1. YOUTUBE (CDP API)
        if "youtube" in target:
            if action in ["play", "pause", "play_pause"]: return self.chrome.youtube_play_pause()
            elif action == "like": return self.chrome.youtube_like()
            elif action == "dislike": return self.chrome.youtube_dislike()
            elif action == "skip_ad": return self.chrome.youtube_skip_ad()
            elif action == "mute": return self.chrome.youtube_mute()
            elif action == "fullscreen": return self.chrome.youtube_fullscreen()
            elif action == "subscribe": return self.chrome.youtube_subscribe()

        # 2. NETFLIX (CDP API)
        elif "netflix" in target:
            if action in ["play", "pause", "play_pause"]: return self.chrome.netflix_play_pause()
            elif action == "skip_intro": return self.chrome.netflix_skip_intro()
            elif action == "next_episode": return self.chrome.netflix_next_episode()
            elif action == "fullscreen": return self.chrome.netflix_fullscreen()

        # 3. TWITCH (CDP API)
        elif "twitch" in target:
            if action in ["play", "pause", "play_pause"]: return self.chrome.twitch_play_pause()
            elif action == "mute": return self.chrome.twitch_mute()
            elif action == "fullscreen": return self.chrome.twitch_fullscreen()

        # 4. PRIME VIDEO (CDP API)
        elif "prime" in target:
            if action in ["play", "pause", "play_pause"]: return self.chrome.prime_play_pause()
            elif action == "skip_intro": return self.chrome.prime_skip_intro()
            elif action == "next_episode": return self.chrome.prime_next_episode()

        # 5. TWITTER / X (CDP API)
        elif target in ("twitter", "x", "x.com") or "twitter" in target or "x.com" in target:
            if action == "like": return self.chrome.twitter_like()
            elif action == "retweet": return self.chrome.twitter_retweet()

        # 6. SPOTIFY (HTTP API primary + CDP fallback for play/pause)
        elif "spotify" in target:
            if self.spotify.is_configured():
                if action == "play":       return self.spotify.play()
                elif action == "pause":    return self.spotify.pause()
                elif action == "next":     return self.spotify.next_track()
                elif action == "prev":     return self.spotify.prev_track()
                elif action == "shuffle":  return self.spotify.shuffle(True)
                elif action == "unshuffle": return self.spotify.shuffle(False)
                elif action == "repeat":   return self.spotify.repeat("context")
                elif action == "repeat_one": return self.spotify.repeat("track")
                elif action == "repeat_off": return self.spotify.repeat("off")

            # Fallback to CDP if HTTP API is not configured
            if action in ["play", "pause", "play_pause"]:
                return self.chrome.spotify_play_pause()

            return False

        # 7. OS LAYER (Fallback or General Media Command)
        if target == "os":
            if action in ["play", "pause", "play_pause"]:
                return self.media_keys.play_pause()
            elif action == "next":
                return self.media_keys.next_track()
            elif action == "prev":
                return self.media_keys.prev_track()
            elif action == "vol_up":
                return self.media_keys.volume_up()
            elif action == "vol_down":
                return self.media_keys.volume_down()

        logger.warning(f"[API Layer] Action '{action}' not matched for target '{target}' or API not configured.")
        return False
        