"""
@ai-context: Modern customtkinter GUI. 
Displays real-time agent status, a live VAD (Voice Activity Detection) waveform, 
and clearly shows the current stage (Listening, Processing, Executing).
Uses thread-safe .after() updates.
Ultra-dark and compact theme.
"""

import threading
import time
import math
import random
import customtkinter as ctk

class AgentStatusGUI(ctk.CTk):  # type: ignore[misc]
    """
    Compact Dashboard floating status window for the agent.
    Features live waveform, stage tracking, and action logs.
    """

    def __init__(self) -> None:
        """Initializes the dashboard UI elements."""
        super().__init__()

        self.title("Agent Dashboard")
        self.geometry("320x340")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.overrideredirect(True)  # Borderless

        # Ultra Dark Theme Palette
        self.bg_color = "#000000"        # Pure Black
        self.card_bg = "#0A0A0A"         # Slightly lighter than black
        self.border_color = "#1A1A1A"    # Very subtle border
        self.accent_blue = "#3B82F6"     # Bright Blue for active stages
        self.accent_cyan = "#06B6D4"     # Cyan for VAD wave
        self.accent_green = "#10B981"    # Success green
        self.accent_red = "#EF4444"      # Error red
        self.text_main = "#E5E5E5"       # Off-white
        self.text_dim = "#737373"        # Dark gray text
        self.idle_elem = "#1F2937"       # Idle UI elements (bars, inactive circles)

        self.configure(fg_color=self.bg_color)

        # Position on bottom right
        screen_w: int = self.winfo_screenwidth()
        x_pos: int = screen_w - 340
        self.geometry(f"320x340+{x_pos}+40")

        self._drag_x: int = 0
        self._drag_y: int = 0
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)

        # Main Container
        self.main_frame = ctk.CTkFrame(
            self, fg_color=self.card_bg, corner_radius=12, border_width=1, border_color=self.border_color
        )
        self.main_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # Header
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=15, pady=(15, 5))

        self.title_lbl = ctk.CTkLabel(
            self.header_frame, text="Screen Reader", font=ctk.CTkFont(family="Inter", size=14, weight="bold"), text_color=self.text_main
        )
        self.title_lbl.pack(side="left")

        self.version_lbl = ctk.CTkLabel(
            self.header_frame, text="v3.0", font=ctk.CTkFont(family="Inter", size=9, weight="bold"), text_color=self.accent_blue
        )
        self.version_lbl.pack(side="left", padx=8, pady=(2, 0))

        # VAD / Audio Waveform Visualizer
        self.vad_frame = ctk.CTkFrame(self.main_frame, fg_color=self.bg_color, corner_radius=8, border_width=1, border_color=self.border_color)
        self.vad_frame.pack(fill="x", padx=15, pady=(10, 10))
        
        self.canvas_width = 260
        self.canvas = ctk.CTkCanvas(self.vad_frame, height=40, width=self.canvas_width, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(padx=10, pady=8)

        self.wave_bars = []
        self.num_bars = 40
        self.bar_width = 3
        self.bar_spacing = 3

        # Draw initial flat bars
        for i in range(self.num_bars):
            x = 5 + i * (self.bar_width + self.bar_spacing)
            bar = self.canvas.create_rectangle(x, 19, x + self.bar_width, 21, fill=self.idle_elem, outline="")
            self.wave_bars.append(bar)

        self.is_listening = False
        self._animate_vad()

        # Stages Timeline
        self.stages_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stages_frame.pack(fill="x", padx=15, pady=5)

        self.stage_labels = {}
        stages = [("1", "Listening"), ("2", "Processing"), ("3", "Executing")]
        for i, (num, text) in enumerate(stages):
            f = ctk.CTkFrame(self.stages_frame, fg_color="transparent")
            f.pack(side="left", expand=True)

            circle = ctk.CTkLabel(
                f, text=num, width=20, height=20, corner_radius=10,
                fg_color=self.idle_elem, text_color=self.text_main, font=ctk.CTkFont(family="Inter", size=10, weight="bold")
            )
            circle.pack()

            lbl = ctk.CTkLabel(f, text=text, font=ctk.CTkFont(family="Inter", size=9), text_color=self.text_dim)
            lbl.pack(pady=(2, 0))

            self.stage_labels[text.lower()] = (circle, lbl)

            # Draw connecting lines between stages
            if i < len(stages) - 1:
                line_canvas = ctk.CTkCanvas(self.stages_frame, width=15, height=2, bg=self.card_bg, highlightthickness=0)
                line_canvas.create_line(0, 1, 15, 1, fill=self.idle_elem, width=2)
                line_canvas.pack(side="left", pady=(0, 15))

        # Status Information Box
        self.status_box = ctk.CTkFrame(self.main_frame, fg_color=self.bg_color, corner_radius=8, border_width=1, border_color=self.border_color)
        self.status_box.pack(fill="x", padx=15, pady=(15, 10))

        self.status_title = ctk.CTkLabel(
            self.status_box, text="SYSTEM STATUS", font=ctk.CTkFont(family="Inter", size=9, weight="bold"), text_color=self.text_dim
        )
        self.status_title.pack(anchor="w", padx=12, pady=(8, 0))

        self.status_label = ctk.CTkLabel(
            self.status_box, text="System Booting...", font=ctk.CTkFont(family="Inter", size=11),
            text_color=self.text_main, wraplength=250, justify="left"
        )
        self.status_label.pack(anchor="w", padx=12, pady=(2, 12))

        # Toggle Button
        self.footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.footer_frame.pack(fill="x", side="bottom", padx=15, pady=15)

        self.toggle_btn = ctk.CTkButton(
            self.footer_frame, text="SYSTEM ACTIVE", fg_color=self.accent_green,
            hover_color="#059669", font=ctk.CTkFont(family="Inter", size=11, weight="bold"),
            height=30, corner_radius=6, command=self._on_toggle_click
        )
        self.toggle_btn.pack(fill="x")

        self.on_toggle_callback = None
        self._is_active = True
        
        # Initialize default state
        self._set_stage("listening")

    def _animate_vad(self) -> None:
        """Animates the VAD waveform grid."""
        if not hasattr(self, 'canvas'): return

        for i in range(self.num_bars):
            if self.is_listening:
                val = math.sin(time.time() * 6 + i * 0.4) * 10 + random.uniform(2, 12)
                h = max(2, min(30, val))
                color = self.accent_cyan
            else:
                h = 2
                color = self.idle_elem

            x = 5 + i * (self.bar_width + self.bar_spacing)
            y1 = 20 - h / 2
            y2 = 20 + h / 2

            self.canvas.coords(self.wave_bars[i], x, y1, x + self.bar_width, y2)
            self.canvas.itemconfig(self.wave_bars[i], fill=color)

        self.after(50, self._animate_vad)

    def _on_toggle_click(self) -> None:
        """Handles the toggle button click."""
        if self.on_toggle_callback:
            is_active = self.on_toggle_callback()
            if is_active:
                self.toggle_btn.configure(text="SYSTEM ACTIVE", fg_color=self.accent_green, hover_color="#059669")
                self._is_active = True
                self.is_listening = True
                self.update_action_status("Dinliyor...")
            else:
                self.toggle_btn.configure(text="SYSTEM PAUSED", fg_color=self.idle_elem, hover_color="#374151")
                self._is_active = False
                self.is_listening = False
                self.update_action_status("Sistem Duraklatıldı.")
                self._set_stage("")

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
        """Legacy compatibility method. Updates VAD state."""
        self.is_listening = is_on

    def _set_stage(self, active_stage: str) -> None:
        """Updates the visual timeline to highlight the active stage."""
        for name, (circle, lbl) in self.stage_labels.items():
            circle.configure(fg_color=self.idle_elem, text_color=self.text_dim)
            lbl.configure(text_color=self.text_dim)

        if active_stage in self.stage_labels:
            circle, lbl = self.stage_labels[active_stage]
            circle.configure(fg_color=self.accent_blue, text_color="#FFFFFF")
            lbl.configure(text_color=self.accent_blue)

    def update_action_status(self, status_text: str) -> None:
        """Updates the main status label and intelligently sets the stage."""
        color = self.text_main
        txt_lower = status_text.lower()

        # State Mapping Logic
        if "dinliyor" in txt_lower or "hazır" in txt_lower:
            self._set_stage("listening")
            self.is_listening = True if self._is_active else False
        elif "anlaşılan" in txt_lower or "model" in txt_lower or "karar" in txt_lower:
            self._set_stage("processing")
            self.is_listening = False
        elif "uygulanıyor" in txt_lower or "tıklanıyor" in txt_lower or "açılıyor" in txt_lower:
            self._set_stage("executing")
            self.is_listening = False
            color = self.accent_blue
        elif "tamamlandı" in txt_lower:
            self._set_stage("listening") # Return to listening after success
            self.is_listening = True
            color = self.accent_green
        elif "hata" in txt_lower or "başarısız" in txt_lower or "bulunamadı" in txt_lower:
            self._set_stage("listening") # Return to listening after error
            self.is_listening = True
            color = self.accent_red

        def _update() -> None:
            self.status_label.configure(text=status_text, text_color=color)

        self.after(0, _update)

if __name__ == "__main__":
    print("Initializing Dashboard...")
    app: AgentStatusGUI = AgentStatusGUI()

    def simulate_flow() -> None:
        app.update_action_status("Dinliyor...")
        
        def phase_1(): app.update_action_status("Anlaşılan: Hava durumu")
        def phase_2(): app.update_action_status("İşlem Uygulanıyor...")
        def phase_3(): app.update_action_status("İşlem Tamamlandı.")

        threading.Timer(2.0, phase_1).start()
        threading.Timer(4.0, phase_2).start()
        threading.Timer(6.0, phase_3).start()

    threading.Timer(1.0, simulate_flow).start()
    app.mainloop()
