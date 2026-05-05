"""
@ai-context: Modern customtkinter GUI. Safely displays real-time
agent status and microphone state using thread-safe .after()
updates to prevent UI freezes or crashes.
"""

import threading

import customtkinter as ctk


class AgentStatusGUI(ctk.CTk):  # type: ignore[misc]
    """
    Always-on-top floating status window for the agent.
    Displays microphone state and current action status.
    """

    def __init__(self) -> None:
        """Initializes the status window with all UI elements."""
        super().__init__()

        self.title("Agent Controller")
        self.geometry("300x160")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.overrideredirect(True)  # Kenarlıksız modern görünüm

        # Renk Paleti (Premium Dark)
        self.bg_color = "#121212"
        self.accent_blue = "#3B82F6"
        self.accent_green = "#10B981"
        self.accent_red = "#EF4444"
        self.text_main = "#F3F4F6"
        self.text_dim = "#9CA3AF"

        self.configure(fg_color=self.bg_color)

        screen_w: int = self.winfo_screenwidth()
        x_pos: int = screen_w - 320
        self.geometry(f"300x160+{x_pos}+40")

        self._drag_x: int = 0
        self._drag_y: int = 0
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)

        # Ana Konteynır
        self.main_frame = ctk.CTkFrame(
            self, fg_color=self.bg_color, corner_radius=15, border_width=1, border_color="#262626"
        )
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Başlık Bölümü
        self.header = ctk.CTkLabel(
            self.main_frame,
            text="AUTONOMOUS AGENT",
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            text_color=self.accent_blue,
        )
        self.header.pack(pady=(15, 5))

        # Ayırıcı Hat
        self.line = ctk.CTkFrame(self.main_frame, height=1, fg_color="#262626")
        self.line.pack(fill="x", padx=30, pady=5)

        # Mikrofon Durumu
        self.mic_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.mic_frame.pack(fill="x", padx=25, pady=(10, 2))

        self.mic_dot = ctk.CTkLabel(
            self.mic_frame,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color=self.accent_red,
            width=20,
        )
        self.mic_dot.pack(side="left")

        self.mic_text = ctk.CTkLabel(
            self.mic_frame,
            text="MICROPHONE IDLE",
            font=ctk.CTkFont(family="Inter", size=12, weight="normal"),
            text_color=self.text_dim,
        )
        self.mic_text.pack(side="left", padx=5)

        # İşlem Durumu
        self.status_frame = ctk.CTkFrame(self.main_frame, fg_color="#1A1A1A", corner_radius=8)
        self.status_frame.pack(fill="x", padx=20, pady=(10, 5))

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="System Standby",
            font=ctk.CTkFont(family="Inter", size=13),
            text_color=self.text_main,
            height=35,
        )
        self.status_label.pack(pady=2)

        # Kontrol Butonu (Active/Standby)
        self.toggle_btn = ctk.CTkButton(
            self.main_frame,
            text="DEACTIVATE AGENT",
            font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            fg_color="#262626",
            hover_color="#333333",
            text_color=self.text_main,
            height=30,
            corner_radius=8,
            command=self._on_toggle_click,
        )
        self.toggle_btn.pack(fill="x", padx=20, pady=(5, 15))

        self.on_toggle_callback = None

    def _on_toggle_click(self) -> None:
        """Handles the button click to toggle agent state."""
        if self.on_toggle_callback:
            is_active = self.on_toggle_callback()
            if is_active:
                self.toggle_btn.configure(text="DEACTIVATE AGENT", fg_color="#262626")
                self.header.configure(text_color=self.accent_blue)
            else:
                self.toggle_btn.configure(text="ACTIVATE AGENT", fg_color=self.accent_blue)
                self.header.configure(text_color=self.text_dim)
                self.status_label.configure(text="AGENT IN STANDBY", text_color=self.text_dim)

    def _on_drag_start(self, event: "ctk.CTk") -> None:
        """Records the starting position for dragging."""
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event: "ctk.CTk") -> None:
        """Moves the window as the user drags."""
        x: int = self.winfo_pointerx() - self._drag_x
        y: int = self.winfo_pointery() - self._drag_y
        self.geometry(f"+{x}+{y}")

    def update_mic_status(self, is_on: bool) -> None:
        """Updates the microphone indicator. Thread-safe."""

        def _update() -> None:
            if is_on:
                self.mic_dot.configure(text_color=self.accent_green)
                self.mic_text.configure(text="LISTENING ACTIVE", text_color=self.text_main)
            else:
                self.mic_dot.configure(text_color=self.accent_red)
                self.mic_text.configure(text="MICROPHONE IDLE", text_color=self.text_dim)

        self.after(0, _update)

    def update_action_status(self, status_text: str) -> None:
        """Updates the action status label. Thread-safe."""

        # Duruma göre renk seçimi
        color = self.text_main
        if "Hata" in status_text or "Bulunamadı" in status_text:
            color = self.accent_red
        elif "Tamamlandı" in status_text:
            color = self.accent_green
        elif "Aranıyor" in status_text or "Taranıyor" in status_text:
            color = self.accent_blue

        def _update() -> None:
            self.status_label.configure(text=status_text, text_color=color)

        self.after(0, _update)


if __name__ == "__main__":
    print("Initializing AgentStatusGUI...")
    app: AgentStatusGUI = AgentStatusGUI()

    def simulate_updates() -> None:
        """Simulates status changes after delays."""
        app.update_mic_status(True)
        app.update_action_status("Dinliyor...")

        def phase_2() -> None:
            app.update_action_status("Ekran Taraniyor...")

        def phase_3() -> None:
            app.update_action_status("Hedef Ariyor...")

        def phase_4() -> None:
            app.update_action_status("Tikliyor...")

        def phase_5() -> None:
            app.update_action_status("Tamamlandi!")

        threading.Timer(3.0, phase_2).start()
        threading.Timer(5.0, phase_3).start()
        threading.Timer(7.0, phase_4).start()
        threading.Timer(9.0, phase_5).start()

    threading.Timer(1.0, simulate_updates).start()
    app.mainloop()
