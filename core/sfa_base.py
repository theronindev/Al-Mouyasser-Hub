"""
SFA Base Task — Shared logic for Transfer Transaction and Transferred Collection.
Handles: Excel loading, file browsing, validation, execution loop, common UI.
Subclasses only implement: _process_one(), _get_description(), _on_complete(), and set coords/config.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import openpyxl
import pyautogui
import time
import os
from datetime import datetime

from core.base_task import BaseTask


class SFABaseTask(BaseTask):
    """Shared base for both SFA modes. Eliminates duplicated code."""

    def __init__(self, parent_notebook, tab_name, hub_ref):
        # Subclass MUST set these before calling super().__init__
        # self.config = {...}
        # self.coords = {...}
        # self.task_color = "#..."
        # self.task_description = "..."

        self.excel_file = ""
        self.cv_data = []

        super().__init__(parent_notebook, tab_name, hub_ref)

    # ── Shared UI ───────────────────────────────────────────────────

    def setup_ui(self):
        """Build common SFA UI: description, file picker, delay setting. Subclass can extend via _setup_extra_ui()."""
        # Description
        desc = ctk.CTkLabel(self.config_frame,
                            text=self.task_description,
                            font=("Segoe UI", 12), text_color=self.task_color)
        desc.pack(anchor="w", padx=10, pady=(5, 5))

        # File picker row
        file_row = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        file_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(file_row, text="Excel File:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))

        self.file_entry = ctk.CTkEntry(file_row, width=350, state="disabled",
                                        placeholder_text="Select CashVan Excel file...")
        self.file_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(file_row, text="Browse", width=90,
                      command=self._browse_file).pack(side="left")

        # Delay setting
        delay_row = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        delay_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(delay_row, text=self.delay_label, font=("Segoe UI", 11)).pack(side="left", padx=(0, 10))
        self.delay_entry = ctk.CTkEntry(delay_row, width=60)
        self.delay_entry.insert(0, str(self.config['delay_long']))
        self.delay_entry.pack(side="left")

        # Hook for subclass-specific UI
        self._setup_extra_ui()

    def _setup_extra_ui(self):
        """Override in subclass to add extra UI elements."""
        pass

    # ── Shared logic ────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select CashVan Excel File",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if path:
            self.excel_file = path
            self.file_entry.configure(state="normal")
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)
            self.file_entry.configure(state="disabled")
            self._load_excel()

    def _load_excel(self):
        """Load CV data from Excel. Columns: CV Name, CV Code, Price."""
        try:
            wb = openpyxl.load_workbook(self.excel_file)
            ws = wb.active
            self.cv_data = []

            for row in ws.iter_rows(min_row=2, values_only=True):
                cv_name = row[0] if row[0] else "Unknown"
                cv_code = str(row[1]) if row[1] else ""
                price = row[2] if row[2] else 0
                if cv_code:
                    self.cv_data.append({'name': cv_name, 'code': cv_code, 'price': price})

            self.total_items = len(self.cv_data)
            self.update_stats()
            self.log(f"✅ Loaded {self.total_items} CV records")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load Excel:\n{e}")
            self.log(f"❌ Excel load error: {e}")

    def validate(self) -> bool:
        if not self.excel_file:
            messagebox.showwarning("Warning", "Select an Excel file first!")
            return False
        if not self.cv_data:
            messagebox.showwarning("Warning", "No CV data loaded!")
            return False

        # Update delay from entry
        try:
            self.config['delay_long'] = float(self.delay_entry.get())
        except ValueError:
            pass

        # Hook for subclass validation
        return self._validate_extra()

    def _validate_extra(self) -> bool:
        """Override in subclass for additional validation."""
        return True

    def execute(self):
        """Shared execution loop — iterates CV data, calls subclass _process_one()."""
        self.log(f"🚀 Starting {self.name}...")
        self.log("⏳ Starting in 3 seconds... Get ready!")
        time.sleep(3)

        for i, cv in enumerate(self.cv_data):
            if not self.wait_if_paused():
                break

            self.update_progress(i + 1, self.total_items)
            self.log(f"📌 [{i+1}/{self.total_items}] {cv['name']} (Code: {cv['code']})")

            try:
                success = self._process_one(cv)
                if success:
                    self.processed_count += 1
                    self.log(f"✅ Done: {cv['name']}")
                else:
                    self.failed_count += 1
                    self.log(f"❌ Failed: {cv['name']}")
            except Exception as e:
                self.failed_count += 1
                self.log(f"❌ Error: {cv['name']} — {e}")

            self.update_stats()
            time.sleep(self.config['delay_short'])

        # Hook for post-processing (e.g., error export)
        self._on_complete()

        # Summary
        total = self.processed_count + self.failed_count
        rate = (self.processed_count / total * 100) if total > 0 else 0
        self.log(f"{'='*40}")
        self.log(f"🎉 Completed — {self.processed_count} OK / {self.failed_count} Failed ({rate:.0f}%)")

    def _on_complete(self):
        """Override in subclass for post-completion actions."""
        pass

    # ── Shared dropdown helper ──────────────────────────────────────

    def select_dropdown_item(self, coord: tuple, position: int):
        """Click a dropdown and select the Nth item using arrow keys.
        position=1 means 1st item (Home → Enter).
        position=2 means 2nd item (Home → Down → Enter), etc.
        """
        pyautogui.click(*coord)
        time.sleep(self.config['delay_medium'])
        pyautogui.press('home')
        time.sleep(0.2)
        for _ in range(position - 1):
            pyautogui.press('down')
            time.sleep(0.3)
        pyautogui.press('enter')

    # ── Abstract — subclass MUST implement ──────────────────────────

    def _process_one(self, cv: dict) -> bool:
        """Process a single CV entry. Subclass implements the mode-specific workflow."""
        raise NotImplementedError
