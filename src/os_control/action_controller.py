import logging
import pyautogui

# Modül için logger ayarı
logger = logging.getLogger(__name__)

# Güvenlik ayarları (pyautogui)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

class ActionController:
    """Evrensel koordinatlarla çalışan pyautogui tabanlı fiziksel aksiyon motoru."""

    def click(self, x: int, y: int) -> bool:
        """Belirtilen (x, y) koordinatlarına sol tıklar."""
        try:
            pyautogui.click(x=x, y=y)
            logger.info(f"Sol tıklandı: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Sol tıklama hatası ({x}, {y}): {e}")
            return False

    def double_click(self, x: int, y: int) -> bool:
        """Belirtilen (x, y) koordinatlarına çift tıklar."""
        try:
            pyautogui.doubleClick(x=x, y=y)
            logger.info(f"Çift tıklandı: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Çift tıklama hatası ({x}, {y}): {e}")
            return False

    def right_click(self, x: int, y: int) -> bool:
        """Belirtilen (x, y) koordinatlarına sağ tıklar."""
        try:
            pyautogui.rightClick(x=x, y=y)
            logger.info(f"Sağ tıklandı: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Sağ tıklama hatası ({x}, {y}): {e}")
            return False

    def scroll(self, amount: int, x: int, y: int) -> bool:
        """Belirtilen (x, y) koordinatlarına giderek 'amount' kadar fare tekerleğiyle kaydırır."""
        try:
            pyautogui.moveTo(x=x, y=y)
            pyautogui.scroll(amount)
            logger.info(f"Kaydırıldı (miktar: {amount}): ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Kaydırma hatası ({x}, {y}, miktar={amount}): {e}")
            return False

    def move_to(self, x: int, y: int) -> bool:
        """Fare imlecini belirtilen (x, y) koordinatlarına taşır."""
        try:
            pyautogui.moveTo(x=x, y=y)
            logger.info(f"Fare taşındı: ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Fare taşıma hatası ({x}, {y}): {e}")
            return False

    def close_current_window(self) -> bool:
        """Aktif pencereyi kapatır (ALT+F4 simülasyonu)."""
        try:
            pyautogui.hotkey('alt', 'f4')
            logger.info("Aktif pencere kapatıldı (ALT+F4).")
            return True
        except Exception as e:
            logger.error(f"Pencere kapatma hatası: {e}")
            return False

    def execute_action(self, action_name: str, x: int, y: int) -> bool:
        """
        Gelen metin komutuna göre ilgili fonksiyonu tetikleyen orkestratör metodu.
        
        Desteklenen komutlar: 'click', 'double_click', 'right_click', 'scroll_up', 'scroll_down', 'move_to'
        """
        action = action_name.lower().strip()
        try:
            if action == "tıkla":
                return self.click(x, y)
            elif action == "çift tıkla":
                return self.double_click(x, y)
            elif action == "sağ tıkla":
                return self.right_click(x, y)
            elif action == "move_to":
                return self.move_to(x, y)
            elif action == "yukarı kaydır":
                return self.scroll(60, x, y)
            elif action == "aşağı kaydır":
                return self.scroll(-60, x, y)
            else:
                logger.error(f"Bilinmeyen eylem adı: '{action_name}'. Herhangi bir işlem yapılmadı.")
                return False
        except Exception as e:
            logger.error(f"execute_action hatası (Eylem: {action_name}, X: {x}, Y: {y}): {e}")
            return False
