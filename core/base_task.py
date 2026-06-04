"""
Base Task - Abstract interface for all automation tasks.
Every task tab inherits from this and implements its own UI + execute logic.
"""

from abc import ABC, abstractmethod
import customtkinter as ctk
import threading
import time
from datetime import datetime

# Shared color palette (matches hub.py)
C = {
    "bg":           "#0a0e1a",
    "card":         "#141b2d",
    "input":        "#0d1117",
    "border":       "#1e2a3a",
    "accent":       "#00b4d8",
    "accent_hover": "#0096b7",
    "success":      "#00c9a7",
    "warning":      "#ffbe0b",
    "danger":       "#ff5a5f",
    "text":         "#e0e6ed",
    "text_dim":     "#6b7b8d",
    "log_bg":       "#080c14",
    "log_text":     "#4ade80",
}


class BaseTask(ABC):
    """Abstract base class for all automation tasks."""

    name: str = "Unnamed Task"
    description: str = ""

    def __init__(self, parent_notebook: ctk.CTkTabview, tab_name: str, hub_ref):
        self.hub = hub_ref
        self.tab_name = tab_name
        self.tab = parent_notebook.tab(tab_name)

        # State
        self.is_running = False
        self.is_paused = False
        self._thread = None

        # Stats
        self.total_items = 0
        self.processed_count = 0
        self.failed_count = 0

        self._build_common_ui()
        self.setup_ui()

    # ── Common UI skeleton ──────────────────────────────────────────

    def _build_common_ui(self):
        """Builds the shared layout: config area, stats + progress, controls, log."""

        # Top: task-specific config area
        self.config_frame = ctk.CTkFrame(self.tab, fg_color=C["card"],
                                          corner_radius=8, border_width=1,
                                          border_color=C["border"])
        self.config_frame.pack(fill="x", padx=12, pady=(10, 5))

        # ── Stats + Progress row ──
        stats_progress = ctk.CTkFrame(self.tab, fg_color="transparent")
        stats_progress.pack(fill="x", padx=12, pady=4)

        # Stats badges
        stats_left = ctk.CTkFrame(stats_progress, fg_color="transparent")
        stats_left.pack(side="left")

        self.stat_total = ctk.CTkLabel(stats_left, text="📊 Total: 0",
                                        font=("Segoe UI", 11),
                                        text_color=C["text_dim"])
        self.stat_total.pack(side="left", padx=(0, 16))

        self.stat_processed = ctk.CTkLabel(stats_left, text="✅ Processed: 0",
                                            font=("Segoe UI", 11),
                                            text_color=C["success"])
        self.stat_processed.pack(side="left", padx=(0, 16))

        self.stat_failed = ctk.CTkLabel(stats_left, text="❌ Failed: 0",
                                         font=("Segoe UI", 11),
                                         text_color=C["danger"])
        self.stat_failed.pack(side="left")

        # Progress label on right
        self.progress_label = ctk.CTkLabel(stats_progress, text="Ready",
                                            font=("Segoe UI", 11),
                                            text_color=C["text_dim"])
        self.progress_label.pack(side="right")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.tab, height=6,
                                                corner_radius=3,
                                                progress_color=C["accent"],
                                                fg_color=C["border"])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=12, pady=(0, 6))

        # ── Control buttons ──
        btn_frame = ctk.CTkFrame(self.tab, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.btn_start = ctk.CTkButton(
            btn_frame, text="▶  Start", width=130, height=36,
            fg_color=C["success"], hover_color="#00a88a",
            text_color="#0a0e1a",
            font=("Segoe UI", 12, "bold"), corner_radius=8,
            command=self._start_wrapper)
        self.btn_start.pack(side="left", padx=(0, 6))

        self.btn_pause = ctk.CTkButton(
            btn_frame, text="⏸  Pause", width=110, height=36,
            fg_color=C["warning"], hover_color="#d9a200",
            text_color="#0a0e1a",
            font=("Segoe UI", 12, "bold"), corner_radius=8,
            command=self.toggle_pause, state="disabled")
        self.btn_pause.pack(side="left", padx=(0, 6))

        self.btn_stop = ctk.CTkButton(
            btn_frame, text="⏹  Stop", width=110, height=36,
            fg_color=C["danger"], hover_color="#d44a4e",
            text_color="#ffffff",
            font=("Segoe UI", 12, "bold"), corner_radius=8,
            command=self.stop, state="disabled")
        self.btn_stop.pack(side="left")

        # ── Log area ──
        log_frame = ctk.CTkFrame(self.tab, fg_color=C["card"],
                                  corner_radius=8, border_width=1,
                                  border_color=C["border"])
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=10, pady=(8, 0))

        ctk.CTkLabel(log_header, text="📋 Activity Log",
                     font=("Segoe UI", 11, "bold"),
                     text_color=C["text_dim"]).pack(side="left")

        self.log_box = ctk.CTkTextbox(
            log_frame, height=120, font=("Consolas", 11),
            fg_color=C["log_bg"], text_color=C["log_text"],
            border_width=1, border_color=C["border"],
            corner_radius=6)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    # ── Shared methods ──────────────────────────────────────────────

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        def _update():
            self.log_box.insert("end", line)
            self.log_box.see("end")

        try:
            self.tab.after(0, _update)
        except Exception:
            pass

        self.hub.global_log(f"[{self.tab_name}] {message}")

    def update_stats(self):
        def _update():
            self.stat_total.configure(text=f"📊 Total: {self.total_items}")
            self.stat_processed.configure(text=f"✅ Processed: {self.processed_count}")
            self.stat_failed.configure(text=f"❌ Failed: {self.failed_count}")
        try:
            self.tab.after(0, _update)
        except Exception:
            pass

    def update_progress(self, current: int, total: int):
        if total == 0:
            return
        pct = current / total
        def _update():
            self.progress_bar.set(pct)
            self.progress_label.configure(text=f"{current}/{total}  ({pct*100:.0f}%)")
        try:
            self.tab.after(0, _update)
        except Exception:
            pass

    def _start_wrapper(self):
        if self.is_running:
            return
        if not self.validate():
            return

        self.processed_count = 0
        self.failed_count = 0
        self.is_running = True
        self.is_paused = False
        self.update_stats()
        self.progress_bar.set(0)
        self.progress_label.configure(text="Starting...")

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_stop.configure(state="normal")

        self._thread = threading.Thread(target=self._execute_wrapper, daemon=True)
        self._thread.start()

    def _execute_wrapper(self):
        try:
            self.execute()
        except Exception as e:
            self.log(f"💥 Critical error: {str(e)}")
        finally:
            self.is_running = False
            self.is_paused = False
            def _reset():
                self.btn_start.configure(state="normal")
                self.btn_pause.configure(state="disabled")
                self.btn_stop.configure(state="disabled")
            try:
                self.tab.after(0, _reset)
            except Exception:
                pass

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.configure(text="▶  Resume")
            self.log("⏸️ Paused")
        else:
            self.btn_pause.configure(text="⏸  Pause")
            self.log("▶️ Resumed")

    def stop(self):
        self.is_running = False
        self.is_paused = False
        self.log("⏹️ Stopped")

    def wait_if_paused(self):
        while self.is_paused and self.is_running:
            time.sleep(0.2)
        return self.is_running

    def interruptible_sleep(self, seconds: float):
        elapsed = 0
        while elapsed < seconds and self.is_running:
            chunk = min(0.2, seconds - elapsed)
            time.sleep(chunk)
            elapsed += chunk
        return self.is_running

    # ── Abstract methods ────────────────────────────────────────────

    @abstractmethod
    def setup_ui(self):
        pass

    @abstractmethod
    def validate(self) -> bool:
        pass

    @abstractmethod
    def execute(self):
        pass
