"""
@ai-context: Main entry point for the Autonomous Screen Reader & Commander.
Initializes and starts the Orchestrator and the Status GUI concurrently.
Automatically detects and launches CDP (Chrome DevTools Protocol) if needed.
"""

from src.core.orchestrator import AgentOrchestrator, AgentConfig
from src.ui.status_window import AgentStatusGUI
from src.utils.cdp_launcher import ensure_cdp_ready

CONFIG: AgentConfig = {
    "llm_model_path": "models/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf",
    "whisper_model": "large-v3-turbo",
    "language": "tr",
    "cdp_port": 9222,
    "n_gpu_layers": 35,
    "florence_model": "microsoft/Florence-2-base"
}

def main() -> None:
    print("Starting Agent Status GUI and Orchestrator...")

    # Prepare CDP in the background (Brave/Chrome/Edge launched in debug mode)
    print("[CDP] Checking browser debug connection...")
    cdp_ok = ensure_cdp_ready()
    if cdp_ok:
        print("[CDP] Browser debug mode ready. High-speed YouTube/Netflix commands enabled.")
    else:
        print("[CDP] Browser debug mode not found. Interaction will fallback to VLM vision.")

    # Initialize GUI
    app = AgentStatusGUI()
    
    # Initialize Orchestrator
    orchestrator = AgentOrchestrator(config=CONFIG)
    orchestrator.load_models()
    
    # Link callbacks
    # Update "Status: ..." label in UI
    orchestrator.set_status_callback(app.update_action_status)
    # Link Active/Passive toggle button to orchestrator
    app.on_toggle_callback = orchestrator.toggle_active
    
    # Update UI mic status
    app.update_mic_status(True)

    # Start Orchestrator in non-blocking mode (background thread)
    orchestrator.start(block=False)

    # Cleanup logic on close
    def on_closing() -> None:
        print("Closing GUI, stopping background services...")
        orchestrator.stop()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)

    # Main GUI loop
    app.mainloop()

if __name__ == "__main__":
    main()
