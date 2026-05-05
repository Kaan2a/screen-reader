import logging
import numpy as np
import re

from src.api_control.api_layer import APILayer
from src.os_control.os_layer import OSLayer
from src.vision.vision_controller import VisionController
from src.os_control.action_controller import ActionController
from src.utils.scaler import CoordinateScaler

try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

logger = logging.getLogger(__name__)

def _normalize_text(text: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirir, noktalama ve bozuk karakterleri ayıklar."""
    text = text.lower().strip()
    # Whisper'ın eklediği noktalama işaretlerini temizle
    text = re.sub(r'[.,!?;:…\-\"\'\(\)]', '', text)
    replacements = {
        'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
        'î': 'i', 'â': 'a'
    }
    for tr_char, eng_char in replacements.items():
        text = text.replace(tr_char, eng_char)
    return text.strip()

class IntentRouter:
    """
    3 Katmanlı Intent Router:
    Sesli komutları alır ve en hızlı çözüm yoluna yönlendirir:
    1. API Katmanı (<50ms)
    2. OS Katmanı (<10ms)
    3. VLM / Vision Katmanı (150ms - 200ms)
    """

    def __init__(
        self, 
        api_layer: APILayer, 
        os_layer: OSLayer, 
        vision_controller: VisionController, 
        action_controller: ActionController,
        scaler: CoordinateScaler
    ) -> None:
        self.api = api_layer
        self.os = os_layer
        self.vision = vision_controller
        self.action = action_controller
        self.scaler = scaler
        self._last_windows: list[str] = []  # Numaralandırma için son pencere listesi

    # Ekran taraması gerektirmeyen saf mouse/klavye komutları
    _PURE_ACTION_PATTERNS = re.compile(
        r'^(tikla|click|cift tikla|double click|double|sag tik|right click|'
        r'sag click|yukari kaydir|asagi kaydir|scroll up|scroll down|'
        r'kaydir yukari|kaydir asagi|scroll|yukari|asagi)$'
    )

    def is_pure_action(self, text: str) -> bool:
        """Ekran taraması gerektirmeyen saf aksiyon komutu mu?"""
        norm = _normalize_text(text)
        return bool(self._PURE_ACTION_PATTERNS.match(norm))

    def _match(self, text: str, pattern: str, keywords: list[str], threshold: int = 85) -> bool:
        """
        Hibrit Eşleştirme: Önce Regex, sonra Fuzzy Match.
        """
        # 1. Regex Kontrolü (Hızlı ve Kesin)
        if re.search(pattern, text):
            return True
        
        # 2. Fuzzy Match Kontrolü (Yazım hataları için)
        if _HAS_RAPIDFUZZ:
            for kw in keywords:
                # partial_ratio: kw metnin içinde geçiyor mu? (Yazım hatası toleranslı)
                if fuzz.partial_ratio(kw, text) >= threshold:
                    return True
        else:
            # Yedek: basit içerme kontrolü
            for kw in keywords:
                if kw in text:
                    return True
                    
        return False

    def _try_vision_click(self, target: str, screen_image: np.ndarray, double: bool = False) -> bool:
        """
        OCR → CLIP → Moondream2 sırasıyla ekranda bir hedef arar ve tıklar.
        double=True ise çift tıklar (uygulama açmak için).
        """
        if screen_image is None:
            logger.warning(f"[VLM] Ekran görüntüsü yok, '{target}' aranamıyor.")
            return False

        # 1. OCR ile metin araması
        ocr_result = self.vision.find_target(target, screen_image)
        if ocr_result:
            logger.info(f"[VLM] OCR buldu: '{target}' @ ({ocr_result['x']:.0f}, {ocr_result['y']:.0f})")
            x, y = self.scaler.scale_point(int(ocr_result["x"]), int(ocr_result["y"]), screen_image.shape[1], screen_image.shape[0])
            return self.action.double_click(x, y) if double else self.action.click(x, y)

        # 2. CLIP ile kavramsal ikon araması
        clip_result = self.vision.find_icon(target, screen_image)
        if clip_result:
            logger.info(f"[VLM] CLIP buldu: '{target}' @ ({clip_result['x']:.0f}, {clip_result['y']:.0f})")
            x, y = self.scaler.scale_point(int(clip_result["x"]), int(clip_result["y"]), screen_image.shape[1], screen_image.shape[0])
            return self.action.double_click(x, y) if double else self.action.click(x, y)

        # 3. Moondream2 ile karmaşık UI araması (son çare)
        moon_result = self.vision.find_complex_element(target, screen_image)
        if moon_result:
            logger.info(f"[VLM] Moondream2 buldu: '{target}' @ ({moon_result['x']:.0f}, {moon_result['y']:.0f})")
            x, y = self.scaler.scale_point(int(moon_result["x"]), int(moon_result["y"]), screen_image.shape[1], screen_image.shape[0])
            return self.action.double_click(x, y) if double else self.action.click(x, y)

        logger.warning(f"[VLM] '{target}' ekranda bulunamadı (OCR/CLIP/Moondream2).")
        return False

    def route_command(self, text: str, screen_image: 'np.ndarray | None') -> bool:
        """
        Gelen metni öncelik sırasına göre işler.
        """
        norm_text = _normalize_text(text)
        logger.info(f"[Intent Router] Komut işleniyor: '{text}' (Normalize: '{norm_text}')")
        # ---------------------------------------------------------
        # 1. MEDYA KONTROL KATMANI (Spotify / YouTube / Netflix vb.)
        # ---------------------------------------------------------
        # Spotify komutları
        if self._match(norm_text, r'(spotify|sarki|m.*z.*k)', ["spotify", "sarki", "muzik"]):
            if self._match(norm_text, r'(durdur|beklet|pause|stop)', ["durdur", "beklet", "pause", "stop"]):
                if not self.api.route_media_command("pause", "spotify"):
                    if self.os.open_window("Spotify"):
                        import time
                        time.sleep(0.3)
                        self.api.media_keys.play_pause()
                return True

            elif self._match(norm_text, r'(baslat|oynat|cal|play)', ["baslat", "oynat", "cal", "play"]):
                if not self.api.route_media_command("play", "spotify"):
                    # API yoksa Spotify'ı öne getirip Play tuşuna bas (Youtube çalmasını engeller)
                    if self.os.open_window("Spotify"):
                        import time
                        time.sleep(0.3)
                        self.api.media_keys.play_pause()
                    else:
                        self._try_vision_click("oynat", screen_image)
                return True

            elif self._match(norm_text, r'(sonraki|gec|next|skip|diger)', ["sonraki", "gec", "next", "skip", "diger"]):
                if not self.api.route_media_command("next", "spotify"):
                    if self.os.open_window("Spotify"):
                        import time
                        time.sleep(0.3)
                        self.api.media_keys.next_track()
                return True

            elif self._match(norm_text, r'(onceki|geri|prev|başa sar|evvelki|eskisi)', ["onceki", "geri", "prev", "basa sar"]):
                if not self.api.route_media_command("prev", "spotify"):
                    if self.os.open_window("Spotify"):
                        import time
                        time.sleep(0.3)
                        self.api.media_keys.prev_track()
                return True

            elif self._match(norm_text, r'(karistir|shuffle)', ["karistir", "shuffle"]):
                self.api.route_media_command("shuffle", "spotify")
                return True

            elif self._match(norm_text, r'(tekrar|repeat)', ["tekrar", "repeat"]):
                self.api.route_media_command("repeat", "spotify")
                return True

        # YouTube komutları
        if self._match(norm_text, r'(video|youtube)', ["youtube", "video"]):
            if self._match(norm_text, r'(durdur|pause|stop)', ["durdur", "pause", "stop"]):
                return self.api.route_media_command("pause", "youtube")
            elif self._match(norm_text, r'(baslat|play|oynat)', ["baslat", "play", "oynat"]):
                return self.api.route_media_command("play", "youtube")
            elif self._match(norm_text, r'(reklam.*gec|skip.*ad)', ["reklami gec", "skip ad"]):
                return self.api.route_media_command("skip_ad", "youtube")
            elif self._match(norm_text, r'(sessiz|mute)', ["sessiz", "mute"]):
                return self.api.route_media_command("mute", "youtube")
            elif self._match(norm_text, r'(tam.*ekran|fullscreen)', ["tam ekran", "fullscreen"]):
                return self.api.route_media_command("fullscreen", "youtube")
            elif self._match(norm_text, r'(abone|subscribe)', ["abone ol", "subscribe"]):
                return self.api.route_media_command("subscribe", "youtube")
            elif self._match(norm_text, r'(dislike|begenme)', ["dislike", "begenme"]):
                return self.api.route_media_command("dislike", "youtube")
            elif self._match(norm_text, r'(begen|like)', ["begen", "like"]):
                success = self.api.route_media_command("like", "youtube")
                if not success:
                    return self._try_vision_click("like", screen_image)
                return success

        # Netflix komutları
        if self._match(norm_text, r'(netflix|dizi|film)', ["netflix", "dizi", "film"]):
            if self._match(norm_text, r'(durdur|pause|stop)', ["durdur", "pause", "stop"]):
                return self.api.route_media_command("pause", "netflix")
            elif self._match(norm_text, r'(baslat|play|oynat)', ["baslat", "play", "oynat"]):
                return self.api.route_media_command("play", "netflix")
            elif self._match(norm_text, r'(intro.*gec|skip.*intro)', ["introyu gec", "skip intro"]):
                return self.api.route_media_command("skip_intro", "netflix")
            elif self._match(norm_text, r'(sonraki.*bolum|next.*episode)', ["sonraki bolum", "next episode"]):
                return self.api.route_media_command("next_episode", "netflix")
            elif self._match(norm_text, r'(tam.*ekran|fullscreen)', ["tam ekran", "fullscreen"]):
                return self.api.route_media_command("fullscreen", "netflix")

        # Twitch komutları
        if self._match(norm_text, r'(twitch|yayin)', ["twitch", "yayin"]):
            if self._match(norm_text, r'(durdur|pause|stop)', ["durdur", "pause", "stop"]):
                return self.api.route_media_command("pause", "twitch")
            elif self._match(norm_text, r'(baslat|play|oynat)', ["baslat", "play", "oynat"]):
                return self.api.route_media_command("play", "twitch")
            elif self._match(norm_text, r'(sessiz|mute)', ["sessiz", "mute"]):
                return self.api.route_media_command("mute", "twitch")
            elif self._match(norm_text, r'(tam.*ekran|fullscreen)', ["tam ekran", "fullscreen"]):
                return self.api.route_media_command("fullscreen", "twitch")

        # Prime Video komutları
        if self._match(norm_text, r'(prime|amazon)', ["prime", "amazon"]):
            if self._match(norm_text, r'(durdur|pause|stop)', ["durdur", "pause", "stop"]):
                return self.api.route_media_command("pause", "prime")
            elif self._match(norm_text, r'(baslat|play|oynat)', ["baslat", "play", "oynat"]):
                return self.api.route_media_command("play", "prime")
            elif self._match(norm_text, r'(intro.*gec|skip.*intro)', ["introyu gec", "skip intro"]):
                return self.api.route_media_command("skip_intro", "prime")
            elif self._match(norm_text, r'(sonraki.*bolum|next.*episode)', ["sonraki bolum", "next episode"]):
                return self.api.route_media_command("next_episode", "prime")

        # Twitter / X komutları
        if self._match(norm_text, r'(twitter|x\.com|x\b)', ["twitter", "x.com"]):
            if self._match(norm_text, r'(begen|like)', ["begen", "like"]):
                return self.api.route_media_command("like", "twitter")
            elif self._match(norm_text, r'(retweet|rt)', ["retweet", "rt"]):
                return self.api.route_media_command("retweet", "twitter")

        # Genel "beğen" / "like" komutu (YouTube varsay)
        if self._match(norm_text, r'(begen|like)', ["begen", "like"]):
            logger.info("[Router -> API] Genel Like yönlendirmesi")
            success = self.api.route_media_command("like", "youtube")
            if not success:
                logger.info("[Router -> VLM Fallback] CDP başarısız. Like butonu ekranda aranıyor...")
                return self._try_vision_click("like", screen_image)
            return success

        # Genel ses kontrolleri
        if self._match(norm_text, r'(ses.*ac|ses.*art|volume.*up|sesi.*yukselt)', ["sesi ac", "volume up", "sesi yukselt"]):
            return self.api.route_media_command("vol_up", "os")
        if self._match(norm_text, r'(ses.*kis|ses.*azalt|volume.*down|sesi.*dusur)', ["sesi kis", "volume down", "sesi dusur"]):
            return self.api.route_media_command("vol_down", "os")

        # Genel "tam ekran" / "fullscreen" / "büyüt" komutu
        if self._match(norm_text, r'(tam.*ekran|fullscreen|buyut|maximize)', ["tam ekran", "fullscreen", "buyut", "pencereyi buyut"]):
            logger.info("[Router] Genel Tam Ekran / Büyütme yönlendirmesi")
            # 1. Önce Medya API'lerini dene (CDP ile player seviyesinde tam ekran)
            if self.api.route_media_command("fullscreen", "youtube"): return True
            if self.api.route_media_command("fullscreen", "netflix"): return True
            if self.api.route_media_command("fullscreen", "twitch"): return True
            
            # 2. Eğer medya değilse, aktif pencereyi OS seviyesinde büyüt
            logger.info("[Router -> OS] Pencere maksimize ediliyor")
            return self.os.maximize_active_window()

        # ---------------------------------------------------------
        # 2. PENCERE KAPATMA
        # ---------------------------------------------------------
        if self._match(norm_text, r'(kapat|close|cikis|kapa$)', ["kapat", "close", "cikis", "kapa"]):
            target_raw = re.sub(r'(kapat|close|cikis|kapa)', '', norm_text).strip()

            # Pencere başlığı eşleme tablosu
            _WINDOW_TITLES: dict[str, str] = {
                "not defteri": "Notepad",
                "notepad":     "Notepad",
                "chrome":      "Chrome",
                "google":      "Chrome",
                "brave":       "Brave",
                "firefox":     "Firefox",
                "edge":        "Edge",
                "spotify":     "Spotify",
                "discord":     "Discord",
                "dosya":       "Explorer",
                "explorer":    "Explorer",
                "hesap":       "Calculator",
                "calculator":  "Calculator",
                "terminal":    "Windows Terminal",
                "powershell":  "PowerShell",
                "cmd":         "cmd",
            }

            # Eşleme tablosundan pencere başlığını bul
            window_title = None
            if target_raw:
                for key, title in _WINDOW_TITLES.items():
                    if key in target_raw:
                        window_title = title
                        break
                if not window_title:
                    window_title = target_raw  # Bilinmeyense direkt kullan

            if window_title:
                logger.info(f"[Router -> OS] '{window_title}' penceresi kapatilıyor")
                result = self.os.close_window(window_title)
                if result:
                    return True
                # pygetwindow bulamazsa ALT+F4 ile dene
                logger.warning(f"[Router -> OS] '{window_title}' bulunamadı, ALT+F4 deneniyor.")

            # Hedefsiz kapat veya pencere bulunamadıysa aktif pencereyi kapat
            logger.info("[Router -> OS] Aktif pencere kapatılıyor (ALT+F4)")
            return self.action.close_current_window()

        # ---------------------------------------------------------
        # 3. GENEL SISTEM KOMUTLARI (OS)
        # ---------------------------------------------------------
        if self._match(norm_text, r'(bilgisayar.*kilitle|ekran.*kilitle|lock.*pc|lock.*screen)', ["bilgisayari kilitle", "lock screen"]):
            logger.info("[Router -> OS] Bilgisayar kilitleniyor.")
            return self.os.lock_workstation()
            
        if self._match(norm_text, r'(masaust.*goster|masaust.*don|show.*desktop)', ["masaustunu goster", "show desktop"]):
            logger.info("[Router -> OS] Masaüstü gösteriliyor.")
            return self.os.show_desktop()
            
        if self._match(norm_text, r'(ayarlar.*ac|open.*settings)', ["ayarlari ac", "open settings"]):
            logger.info("[Router -> OS] Windows Ayarları açılıyor.")
            return self.os.open_settings()
            
        if self._match(norm_text, r'(cop.*bosalt|geri.*donusum|empty.*trash|empty.*recycle)', ["copu bosalt", "empty recycle bin"]):
            logger.info("[Router -> OS] Geri dönüşüm kutusu boşaltılıyor.")
            return self.os.empty_recycle_bin()
            
        if self._match(norm_text, r'(ekran.*goruntusu|screenshot|print.*screen)', ["ekran goruntusu", "screenshot"]):
            logger.info("[Router -> OS] Ekran görüntüsü alınıyor.")
            return self.os.take_screenshot()

        # Genel sistem sesi sessize alma / açma (Medya kontrolünde eşleşmediyse buraya düşer)
        if self._match(norm_text, r'(sessize.*al|sesi.*kapat|sistemi.*sustur|mute)', ["sessize al", "sesi kapat", "mute"]):
            logger.info("[Router -> OS] Sistem sesi susturuldu/açıldı.")
            return self.os.toggle_mute()

        # Yarım Ekran / Pencere Yaslama (Sola/Sağa)
        if self._match(norm_text, r'(yarim.*ekran|yasla|snap)', ["yarim ekran", "sola yasla", "saga yasla"]):
            if self._match(norm_text, r'(sol|left)', ["sol"]):
                return self.os.snap_window_left()
            elif self._match(norm_text, r'(sag|right)', ["sag"]):
                return self.os.snap_window_right()

        # Görev Görünümü (Win + Tab)
        if self._match(norm_text, r'(gorev.*gorunumu|pencereleri.*goster|win.*tab)', ["gorev gorunumu", "pencereleri goster", "win tab"]):
            return self.os.show_task_view()

        # Pencereyi Alta Al (Minimize)
        if self._match(norm_text, r'(alta.*al|kucult|minimize)', ["alta al", "kucult", "simge durumuna getir"]):
            return self.os.minimize_active_window()

        # Pencereyi Öne Getirme (İsimle: "... getir", "... göster", "... öne al")
        if self._match(norm_text, r'(getir|goster|one.*al|ac$)', ["getir", "goster", "one al", "one getir"]):
            target_win = re.sub(r'(getir|goster|one.*al|ac)', '', norm_text).strip()
            target_win = re.sub(r"('?[yiıu]$|'?[yiıu]i$)", '', target_win).strip()
            if target_win:
                # Bilinen eşleşmeler
                _MAP = {"not defteri": "Notepad", "hesap makinesi": "Calculator", "dosyalar": "Explorer"}
                final_title = _MAP.get(target_win, target_win)
                logger.info(f"[Router -> OS] Pencere öne getiriliyor: {final_title}")
                return self.os.open_window(final_title)

        # Pencereleri Numaralandır / Listele
        if self._match(norm_text, r'(pencereleri.*listele|hangileri.*acik|numaralandir)', ["pencereleri listele", "hangileri acik", "numaralandir"]):
            self._last_windows = self.os.get_visible_windows()
            if not self._last_windows:
                logger.warning("[Router] Açık pencere bulunamadı.")
                return False
            
            print("\n" + "="*30)
            print("   AÇIK PENCERELER")
            print("="*30)
            for i, title in enumerate(self._last_windows, 1):
                print(f" {i} -> {title}")
            print("="*30 + "\n")
            logger.info(f"[Router] {len(self._last_windows)} pencere listelendi.")
            return True

        # Numaraya Göre Pencere Seç (Örn: "2 numarayı seç", "3 nolu pencere")
        if self._match(norm_text, r'(\d+.*numara|numara.*\d+|\d+.*nolu)', ["numarayi sec"]):
            try:
                # Sayıyı metinden ayıkla
                nums = re.findall(r'\d+', norm_text)
                if nums:
                    idx = int(nums[0]) - 1  # Kullanıcı 1 tabanlı söyler
                    if 0 <= idx < len(self._last_windows):
                        target = self._last_windows[idx]
                        logger.info(f"[Router -> OS] {idx+1} nolu pencere seçiliyor: {target}")
                        return self.os.open_window(target)
                    else:
                        # Eğer listede yoksa mevcut pencerelerde tekrar ara
                        logger.info(f"[Router -> OS] Liste dışı index, güncel listeden deneniyor...")
                        return self.os.activate_window_by_index(idx)
            except Exception as e:
                logger.error(f"[Router] Sayısal seçim hatası: {e}")
                return False

        # ---------------------------------------------------------
        # 4. UYGULAMA BAŞLATMA (OS + VLM Fallback)
        # ---------------------------------------------------------
        # "... aç / başlat / çalıştır" komutları
        if re.search(r'(ac|baslat|calistir|open|launch|run)', norm_text):
            target_app = re.sub(r'(ac|baslat|calistir|open|launch|run)', '', norm_text).strip()
            target_app = re.sub(r"('?[yiıu]$|'?[yiıu]i$)", '', target_app).strip()
            
            if target_app:
                # Bilinen uygulamalar
                known_apps = {
                    "chrome": "start chrome", "google": "start chrome",
                    "brave": "start brave", "firefox": "start firefox", "edge": "start msedge",
                    "hesap": "calc", "calc": "calc", "calculator": "calc",
                    "not": "notepad", "defter": "notepad", "notepad": "notepad",
                    "spotify": "spotify", "discord": "start discord",
                    "dosya": "explorer", "explorer": "explorer",
                    "terminal": "wt", "cmd": "cmd", "powershell": "powershell",
                    "ayarlar": "start ms-settings:", "settings": "start ms-settings:",
                }
                
                for key, cmd in known_apps.items():
                    if key in target_app:
                        logger.info(f"[Router -> OS] '{key}' başlatılıyor: {cmd}")
                        return self.os.launch_application(cmd)
                
                # Bilinmeyen uygulama → masaüstünde ikon ara (CLIP)
                logger.info(f"[Router -> VLM] Masaüstünde ikon aranıyor: '{target_app}'")
                return self._try_vision_click(target_app, screen_image, double=True)

        # ---------------------------------------------------------
        # 4. MOUSE AKSIYONLARI (Ekran taraması GEREKMEZ)
        # Saf tıklama/kaydırma — mevcut mouse pozisyonunda çalışır
        # ---------------------------------------------------------
        import pyautogui as _pag

        # Çift tıklama (hedefsiz)
        if re.search(r'(cift tikla|double click|cift click)', norm_text):
            target = re.sub(r'(cift tikla|double click|double|cift)', '', norm_text).strip()
            if not target or len(target) < 2:
                logger.info("[Router -> Action] Çift tıklama (mevcut pozisyon)")
                _pag.doubleClick()
                return True
            # Hedefli çift tıklama
            logger.info(f"[Router -> VLM] Hedefli çift tıklama: '{target}'")
            return self._try_vision_click(target, screen_image, double=True)

        # Sağ tıklama (hedefsiz)
        if re.search(r'(sag tik|sag tikla|right click|right tik)', norm_text):
            target = re.sub(r'(sag tik|sag tikla|right click|right tik|sag|right)', '', norm_text).strip()
            if not target or len(target) < 2:
                logger.info("[Router -> Action] Sağ tıklama (mevcut pozisyon)")
                _pag.rightClick()
                return True
            logger.info(f"[Router -> VLM] Hedefli sağ tıklama: '{target}'")
            return self._try_vision_click(target, screen_image)

        # Sol tıklama
        if re.search(r'(^tikla$|^click$|^bas$|tikla |click )', norm_text):
            target = re.sub(r'^(tikla|click|bas)\s*', '', norm_text).strip()
            target = re.sub(r"('?[yaeiye]$|'?[yn][aeiı]$)", '', target).strip()
            if not target or len(target) < 2:
                logger.info("[Router -> Action] Sol tıklama (mevcut pozisyon)")
                _pag.click()
                return True
            logger.info(f"[Router -> VLM] Hedefli sol tıklama: '{target}'")
            return self._try_vision_click(target, screen_image)

        # Kaydırma (ekran taraması gerekmez)
        if self._match(norm_text, r'(kaydir|scroll|asagi|yukari)', ["kaydir", "scroll"]):
            if self._match(norm_text, r'(yukari|up)', ["yukari", "up"]):
                logger.info("[Router -> Action] Yukarı kaydırma")
                return self.action.scroll(700, _pag.position()[0], _pag.position()[1])
            else:
                logger.info("[Router -> Action] Aşağı kaydırma")
                return self.action.scroll(-700, _pag.position()[0], _pag.position()[1])

        # ---------------------------------------------------------
        # 5. FORM / YAZMA KOMUTLARI (Moondream2 öncelikli)
        # ---------------------------------------------------------
        if re.search(r'(form|doldur|yaz|nerede|input|field)', norm_text):
            target_element = re.sub(r'(form|doldur|yaz|nerede|input|field)', '', norm_text).strip()
            target_element = re.sub(r"('?[yaeiye]$|'?[yn][aeiı]$)", '', target_element).strip()

            if target_element and screen_image is not None:
                logger.info(f"[Router -> Moondream2] Karmaşık UI analizi: '{target_element}'")
                moon_result = self.vision.find_complex_element(target_element, screen_image)
                if moon_result:
                    logger.info(f"[Router -> Action] Moondream2 buldu: ({moon_result['x']}, {moon_result['y']})")
                    x, y = self.scaler.scale_point(int(moon_result["x"]), int(moon_result["y"]), screen_image.shape[1], screen_image.shape[0])
                    return self.action.click(x, y)

        # ---------------------------------------------------------
        # 7. GENEL FALLBACK
        # Önce bilinen uygulama isimleri kontrol edilir (OS'tan aç).
        # Sonra ekranda OCR ile metin aranır (masaüstü dosya isimleri vb.).
        # Son çare: CLIP ile ikon araması.
        # ---------------------------------------------------------
        remaining = norm_text.strip()
        if not remaining or len(remaining) < 2:
            logger.warning(f"[Intent Router] Komut çok kısa, işlenemiyor: '{norm_text}'")
            return False

        # Bilinen uygulama isimleri sözlüğü (OS'tan doğrudan aç — mouse gerekmez)
        _KNOWN_APPS: dict[str, str] = {
            "brave":        r'"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"',
            "chrome":       "start chrome",
            "google":       "start chrome",
            "firefox":      "start firefox",
            "edge":         "start msedge",
            "spotify":      "spotify",
            "discord":      "start discord",
            "explorer":     "explorer",
            "dosya":        "explorer",
            "notepad":      "notepad",
            "not defteri":  "notepad",
            "hesap":        "calc",
            "calculator":   "calc",
            "terminal":     "wt",
            "powershell":   "powershell",
            "cmd":          "cmd",
            "ayarlar":      "start ms-settings:",
            "settings":     "start ms-settings:",
        }

        # Kısa komutlar için önce bilinen uygulama kontrolü
        words = remaining.split()
        if len(words) <= 2:
            for app_key, app_cmd in _KNOWN_APPS.items():
                if app_key in remaining:
                    logger.info(f"[Router -> OS Fallback] '{app_key}' tanındı, başlatılıyor: {app_cmd}")
                    return self.os.launch_application(app_cmd)

        # Bilinen uygulama değilse → OCR ile ekranda ara (masaüstü dosya/klasör isimleri)
        logger.info(f"[Router -> VLM Fallback] Ekranda OCR ile aranıyor: '{remaining}'")
        ocr_result = self.vision.find_target(remaining, screen_image)
        if ocr_result:
            logger.info(f"[Router -> Action] OCR buldu ({ocr_result['x']:.0f}, {ocr_result['y']:.0f}) → çift tıklanıyor")
            x, y = self.scaler.scale_point(
                int(ocr_result["x"]), int(ocr_result["y"]),
                screen_image.shape[1], screen_image.shape[0]
            )
            return self.action.double_click(x, y)

        # OCR bulamadıysa → CLIP ile ikon benzerliği araması
        logger.info(f"[Router -> VLM Fallback] OCR başarısız. CLIP ile ikon aranıyor: '{remaining}'")
        clip_result = self.vision.find_icon(remaining, screen_image)
        if clip_result:
            logger.info(f"[Router -> Action] CLIP buldu ({clip_result['x']:.0f}, {clip_result['y']:.0f}) → çift tıklanıyor")
            x, y = self.scaler.scale_point(
                int(clip_result["x"]), int(clip_result["y"]),
                screen_image.shape[1], screen_image.shape[0]
            )
            return self.action.double_click(x, y)

        logger.warning(f"[Intent Router] '{remaining}' ekranda bulunamadı ve bilinen bir uygulama değil.")
        return False

