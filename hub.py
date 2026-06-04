"""
Al-Mouyasser Hub — Unified launcher for all automation tasks.
5 tabs: SFA CashVan, CV Transfers, Tasks Automation, Returns, Settings

Hotkeys (global, work even when window is inactive):
  P          → Pause/Resume active task
  Shift+P    → Stop active task
  ESC        → Emergency stop ALL running tasks
"""

import customtkinter as ctk
from datetime import datetime
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.hotkeys import HotkeyManager
from tasks.sfa_cashvan import SFATask
from tasks.cv_transfers import CVTransfersTask
from tasks.custom_macro import CustomTask
from tasks.tasks_automation import TasksAutomationTask
from tasks.returns import ReturnsTask

# ── Theme ──────────────────────────────────────────────────────────
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ── Color Palette ──────────────────────────────────────────────────
C = {
    "bg":           "#0a0e1a",
    "header":       "#0f1628",
    "card":         "#141b2d",
    "input":        "#0d1117",
    "border":       "#1e2a3a",
    "accent":       "#00b4d8",
    "accent_hover": "#0096b7",
    "accent_dim":   "#0d2a3a",
    "success":      "#00c9a7",
    "warning":      "#ffbe0b",
    "danger":       "#ff5a5f",
    "text":         "#e0e6ed",
    "text_dim":     "#6b7b8d",
    "text_muted":   "#3d4f5f",
    "log_bg":       "#080c14",
    "log_text":     "#4ade80",
    "link":         "#00b4d8",
}


class AlMouyasserHub(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Al-Mouyasser Hub")
        self.geometry("960x820")
        self.minsize(920, 780)
        self.configure(fg_color=C["bg"])

        os.makedirs("configs", exist_ok=True)

        self._build_ui()
        self._register_tasks()
        self._setup_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ── Header ──
        header = ctk.CTkFrame(self, height=70, fg_color=C["header"], corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Brand
        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(brand, text="⚡", font=("Segoe UI", 28),
                     text_color=C["accent"]).pack(side="left", padx=(0, 8))

        titles = ctk.CTkFrame(brand, fg_color="transparent")
        titles.pack(side="left")

        ctk.CTkLabel(titles, text="Al-Mouyasser Hub",
                     font=("Segoe UI", 20, "bold"),
                     text_color=C["text"]).pack(anchor="w")

        dev_label = ctk.CTkLabel(titles, text="by The Ronin Dev",
                                  font=("Segoe UI", 10),
                                  text_color=C["link"], cursor="hand2")
        dev_label.pack(anchor="w")
        dev_label.bind("<Button-1>", lambda e: webbrowser.open("https://www.theronindev.dev"))
        dev_label.bind("<Enter>", lambda e: dev_label.configure(
            text_color="#ffffff", font=("Segoe UI", 10, "underline")))
        dev_label.bind("<Leave>", lambda e: dev_label.configure(
            text_color=C["link"], font=("Segoe UI", 10)))

        # Hotkeys badge
        hk = ctk.CTkFrame(header, fg_color=C["accent_dim"], corner_radius=8)
        hk.pack(side="right", padx=20, pady=15)
        ctk.CTkLabel(hk,
                     text="  P Pause  │  Shift+P Stop  │  ESC Emergency  ",
                     font=("Consolas", 10), text_color=C["text_dim"]).pack(padx=10, pady=4)

        # Divider
        ctk.CTkFrame(self, height=1, fg_color=C["border"], corner_radius=0).pack(fill="x")

        # ── Tabs ──
        self.tabview = ctk.CTkTabview(
            self, anchor="nw", fg_color=C["bg"],
            segmented_button_fg_color=C["card"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent_hover"],
            segmented_button_unselected_color=C["card"],
            segmented_button_unselected_hover_color=C["border"],
            text_color=C["text_dim"],
            text_color_disabled=C["text_muted"])
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(5, 0))

        for tab in ["SFA", "CV Transfers", "Custom", "Tasks", "Returns", "Settings"]:
            self.tabview.add(tab)

        # ── Collapsible Footer ──
        self.footer_visible = True

        footer_bar = ctk.CTkFrame(self, height=30, fg_color=C["card"], corner_radius=0)
        footer_bar.pack(fill="x", padx=12, pady=(2, 0))
        footer_bar.pack_propagate(False)

        self.footer_toggle_btn = ctk.CTkButton(
            footer_bar, text="📡 Global Activity ▼", width=180, height=24,
            fg_color="transparent", text_color=C["text_dim"],
            hover_color=C["border"], font=("Segoe UI", 11, "bold"),
            anchor="w", command=self._toggle_footer)
        self.footer_toggle_btn.pack(side="left", padx=8)

        ctk.CTkButton(footer_bar, text="Clear", width=55, height=20,
                      fg_color="transparent", border_width=1,
                      border_color=C["border"], text_color=C["text_dim"],
                      hover_color=C["border"], font=("Segoe UI", 10),
                      command=self._clear_global_log).pack(side="right", padx=8)

        self.footer_content = ctk.CTkFrame(self, height=80, fg_color=C["card"], corner_radius=0)
        self.footer_content.pack(fill="x", padx=12, pady=(0, 8))
        self.footer_content.pack_propagate(False)

        self.global_log_box = ctk.CTkTextbox(
            self.footer_content, height=70, font=("Consolas", 10),
            fg_color=C["log_bg"], text_color=C["text_muted"],
            border_width=1, border_color=C["border"], corner_radius=6)
        self.global_log_box.pack(fill="both", expand=True, padx=8, pady=(2, 6))

    def _register_tasks(self):
        self.tasks = {}
        self.tasks["SFA"] = SFATask(self.tabview, "SFA", self)
        self.tasks["CV Transfers"] = CVTransfersTask(self.tabview, "CV Transfers", self)
        self.tasks["Custom"] = CustomTask(self.tabview, "Custom", self)
        self.tasks["Tasks"] = TasksAutomationTask(self.tabview, "Tasks", self)
        self.tasks["Returns"] = ReturnsTask(self.tabview, "Returns", self)
        self._build_settings_tab()

    def _build_settings_tab(self):
        settings_tab = self.tabview.tab("Settings")

        ctk.CTkLabel(settings_tab, text="⚙  Settings",
                     font=("Segoe UI", 16, "bold"),
                     text_color=C["text"]).pack(anchor="w", padx=15, pady=(10, 2))

        ctk.CTkLabel(settings_tab,
                     text="Configure step delays for all automation tasks",
                     font=("Segoe UI", 11),
                     text_color=C["text_dim"]).pack(anchor="w", padx=15, pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(settings_tab, height=500,
                                         fg_color=C["card"], corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=12, pady=5)

        self.tasks["SFA"].build_delay_settings_in(scroll)
        ctk.CTkFrame(scroll, height=1, fg_color=C["border"]).pack(fill="x", padx=15, pady=12)
        self.tasks["CV Transfers"].build_delay_settings_in(scroll)

    def _setup_hotkeys(self):
        self.hotkey_manager = HotkeyManager(self)
        self.hotkey_manager.register()

    def _on_close(self):
        for task in self.tasks.values():
            if task.is_running:
                task.is_running = False
        self.hotkey_manager.unregister()
        self.destroy()

    def get_active_task(self):
        current = self.tabview.get()
        return self.tasks.get(current)

    def get_all_tasks(self):
        return list(self.tasks.values())

    def global_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        def _update():
            self.global_log_box.insert("end", line)
            self.global_log_box.see("end")
        try:
            self.after(0, _update)
        except Exception:
            pass

    def _clear_global_log(self):
        self.global_log_box.delete("0.0", "end")

    def _toggle_footer(self):
        self.footer_visible = not self.footer_visible
        if self.footer_visible:
            self.footer_content.pack(fill="x", padx=12, pady=(0, 8))
            self.footer_toggle_btn.configure(text="📡 Global Activity ▼")
        else:
            self.footer_content.pack_forget()
            self.footer_toggle_btn.configure(text="📡 Global Activity ▶")


def main():
    app = AlMouyasserHub()
    app.mainloop()

if __name__ == "__main__":
    main()
