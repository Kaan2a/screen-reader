import os
import subprocess
import time
import pyautogui
import logging
from typing import Optional

try:
    import pygetwindow as gw
except ImportError:
    gw = None

logger = logging.getLogger(__name__)

class OSLayer:
    """
    OS Katmanı: Pencere yönetimi, uygulama başlatma, dosya sistemi ve klavye/fare kontrolü.
    Gecikme hedefi: < 10ms (API çağrısı hariç).
    """

    def __init__(self) -> None:
        if gw is None:
            logger.warning("'pygetwindow' kütüphanesi eksik. Lütfen 'pip install pygetwindow' ile yükleyin.")

    # ---------------------------------------------------------
    # Pencere Yönetimi
    # ---------------------------------------------------------
    def open_window(self, title: str) -> bool:
        """Pencereyi bulur ve öne getirir (maximize)."""
        if gw is None: return False
        
        windows = gw.getWindowsWithTitle(title)
        if windows:
            win = windows[0]
            try:
                if win.isMinimized:
                    win.restore()
                win.activate()
                logger.info(f"Pencere öne getirildi: {title}")
                return True
            except Exception as e:
                logger.error(f"Pencere aktivasyon hatası: {e}")
                return False
        return False

    def close_window(self, title: str) -> bool:
        """Pencereyi kapatır. Tam veya kısmi başlık eşleşmesini destekler."""
        if gw is None: return False

        # Önce tam eşleşme dene
        windows = gw.getWindowsWithTitle(title)

        # Tam eşleşme yoksa tüm pencerelerde kısmi arama yap
        if not windows:
            title_lower = title.lower()
            all_wins = gw.getAllWindows()
            windows = [w for w in all_wins if title_lower in w.title.lower() and w.title.strip()]

        if windows:
            try:
                windows[0].close()
                logger.info(f"Pencere kapatıldı: {windows[0].title}")
                return True
            except Exception as e:
                logger.error(f"Pencere kapatma hatası: {e}")
                return False

        logger.warning(f"Pencere bulunamadı: '{title}'")
        return False

    def minimize_window(self, title: str) -> bool:
        """Pencereyi küçültür."""
        if gw is None: return False
        
        windows = gw.getWindowsWithTitle(title)
        if windows:
            try:
                windows[0].minimize()
                logger.info(f"Pencere küçültüldü: {title}")
                return True
            except Exception as e:
                logger.error(f"Pencere küçültme hatası: {e}")
                return False
        return False

    def maximize_window(self, title: str) -> bool:
        """Pencereyi tam ekran yapar."""
        if gw is None: return False
        
        windows = gw.getWindowsWithTitle(title)
        if windows:
            try:
                windows[0].maximize()
                logger.info(f"Pencere büyütüldü: {title}")
                return True
            except Exception as e:
                logger.error(f"Pencere büyütme hatası: {e}")
                return False
        return False

    def maximize_active_window(self) -> bool:
        """Şu an odakta olan (aktif) pencereyi tam ekran yapar."""
        if gw is None: return False
        try:
            active_win = gw.getActiveWindow()
            if active_win:
                active_win.maximize()
                logger.info(f"Aktif pencere büyütüldü: {active_win.title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Aktif pencere büyütme hatası: {e}")
            return False

    def minimize_active_window(self) -> bool:
        """Şu an odakta olan (aktif) pencereyi alta alır (minimize)."""
        if gw is None: return False
        try:
            active_win = gw.getActiveWindow()
            if active_win:
                active_win.minimize()
                logger.info(f"Aktif pencere alta alındı: {active_win.title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Aktif pencere küçültme hatası: {e}")
            return False

    def snap_window_left(self) -> bool:
        """Aktif pencereyi sola yaslar (Yarım ekran)."""
        logger.info("[OSLayer] Pencere sola yaslanıyor.")
        return self.hotkey("win", "left")

    def snap_window_right(self) -> bool:
        """Aktif pencereyi sağa yaslar (Yarım ekran)."""
        logger.info("[OSLayer] Pencere sağa yaslanıyor.")
        return self.hotkey("win", "right")

    def show_task_view(self) -> bool:
        """Tüm pencereleri gösterir (Win + Tab)."""
        logger.info("[OSLayer] Görev görünümü açılıyor.")
        return self.hotkey("win", "tab")

    def get_visible_windows(self) -> list[str]:
        """Açık olan ve başlığı bulunan tüm pencerelerin listesini döner."""
        if gw is None: return []
        # Sadece başlığı olan ve görünür pencereleri al
        all_windows = gw.getAllWindows()
        titles = [w.title for w in all_windows if w.title.strip()]
        return titles

    def activate_window_by_index(self, index: int) -> bool:
        """Listedeki N. sıradaki pencereyi öne getirir."""
        if gw is None: return False
        titles = self.get_visible_windows()
        if 0 <= index < len(titles):
            return self.open_window(titles[index])
        return False

    # ---------------------------------------------------------
    # Uygulama Başlatma
    # ---------------------------------------------------------
    def launch_application(self, path_or_command: str) -> bool:
        """Belirtilen yolu veya komutu kullanarak bir uygulamayı başlatır."""
        try:
            # subprocess.Popen bloker değildir, OS katmanı için çok hızlıdır (< 5ms)
            subprocess.Popen(path_or_command, shell=True)
            logger.info(f"Uygulama başlatıldı: {path_or_command}")
            return True
        except Exception as e:
            logger.error(f"Uygulama başlatma hatası: {e}")
            return False

    # ---------------------------------------------------------
    # Dosya Sistemi İşlemleri
    # ---------------------------------------------------------
    def open_file(self, filepath: str) -> bool:
        """Varsayılan uygulama ile dosyayı açar."""
        try:
            os.startfile(filepath)
            logger.info(f"Dosya açıldı: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Dosya açma hatası: {e}")
            return False

    # ---------------------------------------------------------
    # Klavye ve Fare Kontrolü (Hızlı İşlemler)
    # ---------------------------------------------------------
    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """Metin yazar."""
        try:
            pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            logger.error(f"Yazma hatası: {e}")
            return False

    def press_key(self, key: str) -> bool:
        """Belirtilen tuşa basar."""
        try:
            pyautogui.press(key)
            return True
        except Exception as e:
            logger.error(f"Tuş basma hatası: {e}")
            return False

    def hotkey(self, *keys: str) -> bool:
        """Klavye kısayolu uygular (ör. 'ctrl', 'c')."""
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            logger.error(f"Kısayol hatası: {e}")
            return False

    # ---------------------------------------------------------
    # Gelişmiş OS Sistem İşlemleri
    # ---------------------------------------------------------
    def lock_workstation(self) -> bool:
        """Bilgisayarı kilitler (Win + L)."""
        logger.info("[OSLayer] Bilgisayar kilitleniyor.")
        return self.launch_application("rundll32.exe user32.dll,LockWorkStation")

    def show_desktop(self) -> bool:
        """Masaüstünü gösterir (Win + D)."""
        logger.info("[OSLayer] Masaüstü gösteriliyor.")
        return self.hotkey("win", "d")

    def open_settings(self) -> bool:
        """Windows Ayarlarını açar."""
        logger.info("[OSLayer] Windows Ayarları açılıyor.")
        return self.launch_application("start ms-settings:")

    def empty_recycle_bin(self) -> bool:
        """Geri dönüşüm kutusunu boşaltır."""
        logger.info("[OSLayer] Geri dönüşüm kutusu boşaltılıyor.")
        return self.launch_application("PowerShell.exe -NoProfile -Command Clear-RecycleBin -Confirm:$false")

    def take_screenshot(self) -> bool:
        """Ekran görüntüsü alır (PrtScn veya Win+Shift+S)."""
        logger.info("[OSLayer] Ekran görüntüsü alınıyor.")
        return self.press_key("printscreen")

    def toggle_mute(self) -> bool:
        """Sistemi sessize alır veya sesi açar."""
        logger.info("[OSLayer] Sistem sesi susturuldu/açıldı.")
        return self.press_key("volumemute")
