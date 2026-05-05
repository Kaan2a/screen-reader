import os
import json
import logging
import pyautogui
import requests
from typing import Optional

try:
    import websocket
except ImportError:
    websocket = None

logger = logging.getLogger(__name__)

class MediaKeysController:
    """
    Genel Medya Kontrolü
    OS media tuşlarını kullanarak donanım seviyesinde en hızlı (<10ms) müzik/video kontrolü sağlar.
    """
    def play_pause(self) -> bool:
        pyautogui.press('playpause')
        logger.info("[OS Media] Play/Pause komutu gönderildi.")
        return True

    def next_track(self) -> bool:
        pyautogui.press('nexttrack')
        logger.info("[OS Media] Sonraki şarkı komutu gönderildi.")
        return True

    def prev_track(self) -> bool:
        pyautogui.press('prevtrack')
        logger.info("[OS Media] Önceki şarkı komutu gönderildi.")
        return True

    def volume_up(self, amount: int = 5) -> bool:
        for _ in range(amount):
            pyautogui.press('volumeup')
        logger.info(f"[OS Media] Ses {amount} kademe artırıldı.")
        return True

    def volume_down(self, amount: int = 5) -> bool:
        for _ in range(amount):
            pyautogui.press('volumedown')
        logger.info(f"[OS Media] Ses {amount} kademe azaltıldı.")
        return True


class SpotifyAPIController:
    """
    Spotify HTTP API
    Gecikme < 50ms. Çalan şarkıyı değiştirmek veya durdurmak için arka planda hızlı ağ istekleri atar.
    Not: SPOTIFY_ACCESS_TOKEN ortam değişkeni gerektirir.
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
            logger.info("[Spotify API] Play isteği gönderildi.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Play hatası: {e}")
            return False

    def pause(self) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.put(f"{self.base_url}/pause", headers=self.headers, timeout=1)
            logger.info("[Spotify API] Pause isteği gönderildi.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Pause hatası: {e}")
            return False

    def next_track(self) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.post(f"{self.base_url}/next", headers=self.headers, timeout=1)
            logger.info("[Spotify API] Next isteği gönderildi.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Next hatası: {e}")
            return False

    def previous_track(self) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.post(f"{self.base_url}/previous", headers=self.headers, timeout=1)
            logger.info("[Spotify API] Previous isteği gönderildi.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Previous hatası: {e}")
            return False

    def shuffle(self, state: bool = True) -> bool:
        if not self.is_configured(): return False
        try:
            state_str = "true" if state else "false"
            r = requests.put(f"{self.base_url}/shuffle?state={state_str}", headers=self.headers, timeout=1)
            logger.info(f"[Spotify API] Shuffle {state_str} isteği gönderildi.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Shuffle hatası: {e}")
            return False

    def repeat(self, state: str = "context") -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.put(f"{self.base_url}/repeat?state={state}", headers=self.headers, timeout=1)
            logger.info(f"[Spotify API] Repeat {state} isteği gönderildi.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Repeat hatası: {e}")
            return False

    def set_volume(self, percent: int) -> bool:
        if not self.is_configured(): return False
        try:
            r = requests.put(f"{self.base_url}/volume?volume_percent={percent}", headers=self.headers, timeout=1)
            logger.info(f"[Spotify API] Volume {percent} isteği gönderildi.")
            return r.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[Spotify API] Volume hatası: {e}")
            return False


class ChromeCDPController:
    """
    Chrome DevTools Protocol (CDP) Kontrolcüsü
    Tarayıcıdaki aktif sekmeleri okuyarak YouTube gibi sayfalara milisaniyelik JS enjekte eder.
    (Chrome '--remote-debugging-port=9222' ile başlatılmış olmalıdır.)
    """
    def __init__(self, port: int = 9222) -> None:
        self.port = port
        self.base_url = f"http://localhost:{self.port}/json"
        if websocket is None:
            logger.warning("'websocket-client' kütüphanesi eksik. CDP işlemleri başarısız olabilir.")

    def _get_tab_ws_url(self, keyword: str) -> Optional[str]:
        try:
            r = requests.get(self.base_url, timeout=1)
            tabs = r.json()
            for tab in tabs:
                if keyword.lower() in tab.get("url", "").lower() or keyword.lower() in tab.get("title", "").lower():
                    return tab.get("webSocketDebuggerUrl")
        except Exception:
            return None
        return None

    def execute_js(self, keyword: str, js_code: str) -> bool:
        if websocket is None:
            return False
            
        ws_url = self._get_tab_ws_url(keyword)
        if not ws_url:
            logger.warning(f"CDP: '{keyword}' içeren sekme bulunamadı veya Debugging kapalı.")
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
            ws.recv()  # Yanıt bekle (milisaniyeler sürer)
            ws.close()
            logger.info(f"[CDP API] '{keyword}' sekmesine JS enjekte edildi.")
            return True
        except Exception as e:
            logger.error(f"[CDP API] JS Inject hatası: {e}")
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


class APILayer:
    """
    API Katmanı Yöneticisi
    Gecikme Hedefi: < 50ms
    Birden fazla web veya masaüstü uygulamasının API / CDP bağlantılarını orkestre eder.
    """
    def __init__(self) -> None:
        self.media_keys = MediaKeysController()
        self.spotify = SpotifyAPIController()
        self.chrome = ChromeCDPController()

    def route_media_command(self, action: str, target: str = "os") -> bool:
        """
        Gelen medya komutunu en hızlı ve uygun hedefe yönlendirir.
        Örnek: route_media_command("play", "youtube")
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
        elif "twitter" in target or "x.com" in target or "x" in target:
            if action == "like": return self.chrome.twitter_like()
            elif action == "retweet": return self.chrome.twitter_retweet()

        # 6. SPOTIFY (HTTP API)
        elif "spotify" in target:
            if self.spotify.is_configured():
                if action == "play": return self.spotify.play()
                elif action == "pause": return self.spotify.pause()
                elif action == "next": return self.spotify.next_track()
                elif action == "prev": return self.spotify.previous_track()
                elif action == "shuffle": return self.spotify.shuffle(True)
                elif action == "unshuffle": return self.spotify.shuffle(False)
                elif action == "repeat": return self.spotify.repeat("context")
                elif action == "repeat_one": return self.spotify.repeat("track")
                elif action == "repeat_off": return self.spotify.repeat("off")
            else:
                pass

        # 7. OS KATMANI (Fallback veya Genel Medya Komutu)
        # Sadece hedef 'os' ise genel tuşlara basılır. 'spotify' isteyip API bozuksa başka sekmeyi etkilememesi için.
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

        logger.warning(f"[API Katmanı] '{action}' eylemi '{target}' için eşleşmedi veya API ayarlanmadı.")
        return False

