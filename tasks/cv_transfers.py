"""
Task: CV Transfers — Type item/qty pairs into a selected window.
- Line numbers next to Item and QTY textboxes
- Image-based popup detection: capture the OK button from error popup
- After each step, locateOnScreen checks if OK button is visible
- If found → auto-pause, user fixes manually, then resumes
- Does NOT click anything on the popup
"""

import customtkinter as ctk
from tkinter import messagebox
import pyautogui
import pygetwindow as gw
import time
import os
import json
import threading

from core.base_task import BaseTask

# ── Config ──────────────────────────────────────────────────────────
DELAYS_FILE = os.path.join("configs", "sfa_delays.json")
CVT_ERROR_IMAGE = os.path.join("configs", "cvt_error_popup.png")

CVT_DELAY_DEFAULTS = {
    "cvt_before_start":    ("Before start (focus)",   2.0),
    "cvt_after_item":      ("After type item",        0.3),
    "cvt_after_enter1":    ("After Enter (item)",     0.5),
    "cvt_after_type1":     ("After type \"1\"",       0.3),
    "cvt_after_enter2":    ("After Enter (1)",        0.3),
    "cvt_after_qty":       ("After type qty",         0.3),
    "cvt_after_down":      ("After Down arrow",       0.5),
}


def _load_cvt_delays() -> dict:
    defaults = {k: v for k, (_, v) in CVT_DELAY_DEFAULTS.items()}
    if os.path.exists(DELAYS_FILE):
        try:
            with open(DELAYS_FILE, 'r') as f:
                saved = json.load(f)
            for k in defaults:
                if k in saved:
                    defaults[k] = saved[k]
        except Exception:
            pass
    return defaults


def _save_cvt_delays(delays: dict):
    os.makedirs("configs", exist_ok=True)
    existing = {}
    if os.path.exists(DELAYS_FILE):
        try:
            with open(DELAYS_FILE, 'r') as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.update(delays)
    with open(DELAYS_FILE, 'w') as f:
        json.dump(existing, f, indent=2)


class CVTransfersTask(BaseTask):
    name = "CV Transfers"
    description = "Type item/qty pairs into a target window"

    def __init__(self, parent_notebook, tab_name, hub_ref):
        self.delays = _load_cvt_delays()
        self.delay_entries = {}
        self.target_window = None
        self.target_title = ""
        self.windows_list = []

        super().__init__(parent_notebook, tab_name, hub_ref)

    # ══════════════════════════════════════════════════════════════════
    # UI
    # ══════════════════════════════════════════════════════════════════

    def setup_ui(self):
        desc = ctk.CTkLabel(self.config_frame,
                            text="📋 CV Transfers — Type item/qty pairs into a target window",
                            font=("Segoe UI", 12), text_color="#9b59b6")
        desc.pack(anchor="w", padx=10, pady=(5, 2))

        # ── Window selector ──
        win_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        win_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(win_frame, text="Target Window:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))

        self.window_dropdown = ctk.CTkComboBox(win_frame, width=400, state="readonly",
                                                font=("Segoe UI", 11))
        self.window_dropdown.pack(side="left", padx=(0, 10))
        self.window_dropdown.set("-- Select a window --")

        ctk.CTkButton(win_frame, text="🔄 Refresh", width=90,
                      command=self._refresh_windows).pack(side="left")

        # ── Error popup capture ──
        error_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        error_frame.pack(fill="x", padx=10, pady=5)

        self.error_img_status = ctk.CTkLabel(
            error_frame,
            text="✅ Error image ready" if os.path.exists(CVT_ERROR_IMAGE) else "⚠️ No error popup image",
            font=("Segoe UI", 11),
            text_color="#2ecc71" if os.path.exists(CVT_ERROR_IMAGE) else "#e74c3c")
        self.error_img_status.pack(side="left", padx=(0, 5))

        ctk.CTkButton(error_frame, text="Capture Error Image", width=160,
                      command=self._start_error_capture).pack(side="left")

        ctk.CTkLabel(error_frame,
                     text="(trigger an error first, then capture the OK button)",
                     font=("Segoe UI", 10), text_color="gray").pack(side="left", padx=10)

        # ── Item & QTY textboxes with line numbers ──
        data_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        data_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Item column
        item_col = ctk.CTkFrame(data_frame, fg_color="transparent")
        item_col.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ctk.CTkLabel(item_col, text="Item (one per line):",
                     font=("Segoe UI", 11, "bold"), text_color="#3498db").pack(anchor="w")

        item_inner = ctk.CTkFrame(item_col, fg_color="transparent")
        item_inner.pack(fill="both", expand=True)

        self.item_line_nums = ctk.CTkTextbox(item_inner, width=35, height=150,
                                              font=("Consolas", 11), fg_color="#0d1117",
                                              text_color="#6b7b8d", state="disabled")
        self.item_line_nums.pack(side="left", fill="y")

        self.item_textbox = ctk.CTkTextbox(item_inner, height=150, font=("Consolas", 11))
        self.item_textbox.pack(side="left", fill="both", expand=True)

        # QTY column
        qty_col = ctk.CTkFrame(data_frame, fg_color="transparent")
        qty_col.pack(side="left", fill="both", expand=True, padx=(5, 0))

        ctk.CTkLabel(qty_col, text="QTY (one per line):",
                     font=("Segoe UI", 11, "bold"), text_color="#e67e22").pack(anchor="w")

        qty_inner = ctk.CTkFrame(qty_col, fg_color="transparent")
        qty_inner.pack(fill="both", expand=True)

        self.qty_line_nums = ctk.CTkTextbox(qty_inner, width=35, height=150,
                                             font=("Consolas", 11), fg_color="#0d1117",
                                             text_color="#6b7b8d", state="disabled")
        self.qty_line_nums.pack(side="left", fill="y")

        self.qty_textbox = ctk.CTkTextbox(qty_inner, height=150, font=("Consolas", 11))
        self.qty_textbox.pack(side="left", fill="both", expand=True)

        # Bind text changes to update line numbers
        self.item_textbox.bind("<KeyRelease>", lambda e: self._update_line_nums(self.item_textbox, self.item_line_nums))
        self.qty_textbox.bind("<KeyRelease>", lambda e: self._update_line_nums(self.qty_textbox, self.qty_line_nums))

        # Bind scroll sync
        self.item_textbox.bind("<MouseWheel>", lambda e: self._sync_scroll(self.item_textbox, self.item_line_nums, e))
        self.qty_textbox.bind("<MouseWheel>", lambda e: self._sync_scroll(self.qty_textbox, self.qty_line_nums, e))

        # Initialize line numbers
        self._update_line_nums(self.item_textbox, self.item_line_nums)
        self._update_line_nums(self.qty_textbox, self.qty_line_nums)

        self._refresh_windows()

    # ══════════════════════════════════════════════════════════════════
    # Line numbers
    # ══════════════════════════════════════════════════════════════════

    def _update_line_nums(self, textbox, line_nums_widget):
        text = textbox.get("1.0", "end")
        line_count = max(text.count('\n'), 1)
        nums = "\n".join(str(i) for i in range(1, line_count + 1))
        line_nums_widget.configure(state="normal")
        line_nums_widget.delete("1.0", "end")
        line_nums_widget.insert("1.0", nums)
        line_nums_widget.configure(state="disabled")

    def _sync_scroll(self, textbox, line_nums_widget, event):
        line_nums_widget.yview_moveto(textbox.yview()[0])

    # ══════════════════════════════════════════════════════════════════
    # Window management
    # ══════════════════════════════════════════════════════════════════

    def _refresh_windows(self):
        self.windows_list = [w for w in gw.getAllWindows() if w.title and w.title.strip()]
        titles = [w.title for w in self.windows_list]
        if titles:
            self.window_dropdown.configure(values=titles)
            self.window_dropdown.set(titles[0])
            self.log(f"🔄 Found {len(titles)} windows")
        else:
            self.window_dropdown.configure(values=["No windows found"])
            self.window_dropdown.set("No windows found")

    def _get_target_window(self):
        selected_title = self.window_dropdown.get()
        for w in self.windows_list:
            if w.title == selected_title:
                return w
        return None

    # ══════════════════════════════════════════════════════════════════
    # Error popup image capture
    # ══════════════════════════════════════════════════════════════════

    def _start_error_capture(self):
        self.log("📸 Capture OK Button — in 3 seconds...")
        self.log("   Trigger an error in Oracle Forms first, leave the popup visible.")
        self.log("   Press 'S' on TOP-LEFT of the OK button, then 'S' on BOTTOM-RIGHT.")
        threading.Thread(target=self._do_error_capture, daemon=True).start()

    def _do_error_capture(self):
        time.sleep(3)
        try:
            import keyboard as kb
            screenshot = pyautogui.screenshot()

            self.log("👉 Hover over TOP-LEFT corner of the OK button → press 'S'")
            while not kb.is_pressed('s'):
                time.sleep(0.05)
            x1, y1 = pyautogui.position()
            self.log(f"   ✅ Top-left: ({x1}, {y1})")
            time.sleep(0.8)

            self.log("👉 Hover over BOTTOM-RIGHT corner of the OK button → press 'S'")
            while not kb.is_pressed('s'):
                time.sleep(0.05)
            x2, y2 = pyautogui.position()
            self.log(f"   ✅ Bottom-right: ({x2}, {y2})")
            time.sleep(0.5)

            region = screenshot.crop((x1, y1, x2, y2))
            os.makedirs("configs", exist_ok=True)
            region.save(CVT_ERROR_IMAGE)

            self.log(f"💾 OK button image saved to {CVT_ERROR_IMAGE}")
            self.tab.after(0, lambda: self.error_img_status.configure(
                text="✅ Error image ready", text_color="#2ecc71"))

        except Exception as e:
            self.log(f"❌ Error capture failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # Popup detection (image-based)
    # ══════════════════════════════════════════════════════════════════

    def _check_for_popup(self, line_num: int, item: str, context: str) -> bool:
        """
        Check if the error popup OK button is visible on screen.
        If found → auto-pause. Does NOT click anything.
        Returns True if popup was detected (paused + resumed or stopped).
        """
        if not os.path.exists(CVT_ERROR_IMAGE):
            return False

        try:
            location = pyautogui.locateOnScreen(CVT_ERROR_IMAGE, confidence=0.8)
            if location:
                self.log(f"🔴 ERROR POPUP at line {line_num} — Item: {item}")
                self.log(f"   Detected after: {context}")
                self.log(f"   ⏸️ Auto-pausing — close the popup & fix the error manually")
                self.log(f"   Then click Resume to continue from line {line_num + 1}")

                # Auto-pause
                self.is_paused = True
                def _update_btn():
                    self.btn_pause.configure(text="▶  Resume")
                try:
                    self.tab.after(0, _update_btn)
                except Exception:
                    pass

                # Wait while paused
                while self.is_paused and self.is_running:
                    time.sleep(0.2)

                if not self.is_running:
                    return True

                self.log(f"▶️ Resumed — continuing from line {line_num + 1}")

                # Re-activate target window
                try:
                    self.target_window.activate()
                    time.sleep(0.5)
                except Exception:
                    pass

                return True
        except Exception as e:
            # locateOnScreen can throw if no match — that's normal
            pass

        return False

    # ══════════════════════════════════════════════════════════════════
    # Settings tab integration
    # ══════════════════════════════════════════════════════════════════

    def build_delay_settings_in(self, parent_frame):
        ctk.CTkLabel(parent_frame, text="CV Transfers Delays (sec)",
                     font=("Segoe UI", 12, "bold"), text_color="#9b59b6").pack(anchor="w", padx=15, pady=(15, 5))

        for key, (label, default_val) in CVT_DELAY_DEFAULTS.items():
            row = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 11), width=180, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=60, font=("Segoe UI", 11))
            entry.insert(0, str(self.delays.get(key, default_val)))
            entry.pack(side="left", padx=(5, 0))
            self.delay_entries[key] = entry

        btn_row = ctk.CTkFrame(parent_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkButton(btn_row, text="💾 Save", width=100, height=28,
                      fg_color="#27ae60", hover_color="#219a52",
                      font=("Segoe UI", 11),
                      command=self._save_delays_from_ui).pack(side="left", padx=5)

        ctk.CTkButton(btn_row, text="↩ Reset", width=100, height=28,
                      fg_color="#95a5a6", hover_color="#7f8c8d",
                      font=("Segoe UI", 11),
                      command=self._reset_delays).pack(side="left", padx=5)

    def _save_delays_from_ui(self):
        for key, entry in self.delay_entries.items():
            try:
                self.delays[key] = float(entry.get())
            except ValueError:
                pass
        _save_cvt_delays(self.delays)
        self.log("💾 CV Transfers delays saved")

    def _reset_delays(self):
        for key, (label, default_val) in CVT_DELAY_DEFAULTS.items():
            self.delays[key] = default_val
            entry = self.delay_entries[key]
            entry.delete(0, "end")
            entry.insert(0, str(default_val))
        _save_cvt_delays(self.delays)
        self.log("↩ CV Transfers delays reset to defaults")

    def d(self, key: str) -> float:
        return self.delays.get(key, 0.3)

    # ══════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════

    def _check_stop(self) -> bool:
        return not self.is_running

    def _parse_lines(self, textbox) -> list:
        text = textbox.get("1.0", "end")
        return [line.strip() for line in text.strip().splitlines() if line.strip()]

    # ══════════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════════

    def validate(self) -> bool:
        win = self._get_target_window()
        if not win:
            messagebox.showwarning("Warning", "Select a valid target window first!\nClick 🔄 Refresh to update the list.")
            return False
        self.target_window = win
        self.target_title = win.title

        items = self._parse_lines(self.item_textbox)
        qtys = self._parse_lines(self.qty_textbox)

        if not items:
            messagebox.showwarning("Warning", "Item textbox is empty!")
            return False

        if not qtys:
            messagebox.showwarning("Warning", "QTY textbox is empty!")
            return False

        if len(items) != len(qtys):
            messagebox.showerror("Error",
                                 f"Item and QTY line counts don't match!\n"
                                 f"Items: {len(items)} lines\n"
                                 f"QTY: {len(qtys)} lines\n\n"
                                 f"Each item needs a corresponding QTY.")
            return False

        if not os.path.exists(CVT_ERROR_IMAGE):
            self.log("⚠️ No error popup image captured — popup detection DISABLED")
            self.log("   Capture it via 'Capture Error Image' button for auto-pause on errors")
        else:
            self.log("🛡️ Error popup detection: ENABLED")

        self._save_delays_from_ui()
        return True

    # ══════════════════════════════════════════════════════════════════
    # Execution
    # ══════════════════════════════════════════════════════════════════

    def execute(self):
        items = self._parse_lines(self.item_textbox)
        qtys = self._parse_lines(self.qty_textbox)

        self.total_items = len(items)
        self.update_stats()

        self.log(f"🚀 Starting CV Transfers — {self.total_items} entries")
        self.log(f"🪟 Target: {self.target_title}")

        # Activate target window
        try:
            self.target_window.activate()
            self.log("✅ Window activated")
        except Exception as e:
            self.log(f"⚠️ Could not activate window: {e}")
            try:
                self.target_window.minimize()
                time.sleep(0.3)
                self.target_window.restore()
            except Exception:
                pass

        self.log(f"⏳ Starting in {self.d('cvt_before_start'):.0f} seconds... Get ready!")
        if not self.interruptible_sleep(self.d("cvt_before_start")):
            return

        for i, (item, qty) in enumerate(zip(items, qtys)):
            if not self.wait_if_paused():
                break

            line_num = i + 1
            self.update_progress(line_num, self.total_items)
            self.log(f"📌 Line {line_num}/{self.total_items} — Item: {item}, QTY: {qty}")

            try:
                # Step 1: Type item number
                pyautogui.write(item)
                time.sleep(self.d("cvt_after_item"))
                if self._check_stop(): break
                if self._check_for_popup(line_num, item, "typing item"):
                    if not self.is_running: break
                    self.failed_count += 1
                    self.update_stats()
                    continue

                # Step 2: Press Enter (item)
                pyautogui.press('enter')
                time.sleep(self.d("cvt_after_enter1"))
                if self._check_stop(): break
                if self._check_for_popup(line_num, item, "Enter after item"):
                    if not self.is_running: break
                    self.failed_count += 1
                    self.update_stats()
                    continue

                # Step 3: Type "1"
                pyautogui.write('1')
                time.sleep(self.d("cvt_after_type1"))
                if self._check_stop(): break
                if self._check_for_popup(line_num, item, "typing 1"):
                    if not self.is_running: break
                    self.failed_count += 1
                    self.update_stats()
                    continue

                # Step 4: Press Enter (1)
                pyautogui.press('enter')
                time.sleep(self.d("cvt_after_enter2"))
                if self._check_stop(): break
                if self._check_for_popup(line_num, item, "Enter after 1"):
                    if not self.is_running: break
                    self.failed_count += 1
                    self.update_stats()
                    continue

                # Step 5: Type qty
                pyautogui.write(qty)
                time.sleep(self.d("cvt_after_qty"))
                if self._check_stop(): break
                if self._check_for_popup(line_num, item, "typing qty"):
                    if not self.is_running: break
                    self.failed_count += 1
                    self.update_stats()
                    continue

                # Step 6: Press Down arrow
                pyautogui.press('down')
                time.sleep(self.d("cvt_after_down"))
                if self._check_stop(): break
                if self._check_for_popup(line_num, item, "Down arrow"):
                    if not self.is_running: break
                    self.failed_count += 1
                    self.update_stats()
                    continue

                self.processed_count += 1
                self.log(f"✅ Line {line_num}: {item} × {qty}")

            except Exception as e:
                if not self.is_running:
                    self.log(f"⏹️ Stopped at line {line_num}: {item}")
                    break
                self.failed_count += 1
                self.log(f"❌ Line {line_num} error: {item} — {e}")

            self.update_stats()
            if not self.is_running:
                break

        # Summary
        total = self.processed_count + self.failed_count
        rate = (self.processed_count / total * 100) if total > 0 else 0
        self.log(f"{'='*40}")
        self.log(f"🎉 CV Transfers completed — {self.processed_count} OK / {self.failed_count} Failed ({rate:.0f}%)")
