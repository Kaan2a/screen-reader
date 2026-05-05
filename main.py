"""
@ai-context: Main entry point for the Autonomous Screen Reader & Commander.
Initializes and starts the Orchestrator and the Status GUI concurrently.
CDP (Chrome DevTools Protocol) otomatik olarak başlatılır.
"""

from src.core.orchestrator import AgentOrchestrator
from src.ui.status_window import AgentStatusGUI
from src.utils.cdp_launcher import ensure_cdp_ready

def main() -> None:
    print("Agent Status GUI ve Orchestrator baslatiliyor...")

    # CDP'yi arka planda hazırla (Brave/Chrome/Edge debug modunda açılır)
    print("[CDP] Tarayici debug baglantisi kontrol ediliyor...")
    cdp_ok = ensure_cdp_ready()
    if cdp_ok:
        print("[CDP] Tarayici debug modu hazir. YouTube/Netflix komutlari aktif.")
    else:
        print("[CDP] Tarayici debug modu bulunamadi. Like/pause komutlari VLM ile calisacak.")

    # GUI'yi baslat
    app = AgentStatusGUI()
    
    # Orchestrator'i baslat
    orchestrator = AgentOrchestrator()
    
    # Callback baglantilari
    # UI'daki "Durum: ..." etiketini gunceller
    orchestrator.set_status_callback(app.update_action_status)
    # UI'daki Aktif/Pasif butonunu orchestrator'a baglar
    app.on_toggle_callback = orchestrator.toggle_active
    
    # Mikrofon acildiginda arayuzu gunceller
    app.update_mic_status(True)

    # Orchestrator'i non-blocking modda baslat (arka plan thread)
    orchestrator.start(block=False)

    # Uygulama kapatildiginda arka plan servislerini durdur
    def on_closing() -> None:
        print("GUI kapatiliyor, arka plan servisleri durduruluyor...")
        orchestrator.stop()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)

    # GUI mainloop (Ana thread burada bloklanir)
    app.mainloop()

if __name__ == "__main__":
    main()
