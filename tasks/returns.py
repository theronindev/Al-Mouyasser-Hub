"""
Task: Returns Processing
Processes return orders from CSV through SFA Sale Order forms.
15-step workflow: fill form → save → copy result → action → close window.
Coordinate-based with interactive setup.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import pyautogui
import pyperclip
import time
import os
import threading
from datetime import datetime

from core.base_task import BaseTask
from core.coord_capture import capture_coordinates, load_coordinates

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

COORDS_FILE = os.path.join("configs", "returns_coords.json")
COORD_POINTS = ["Sale Order", "Organization", "Return Invoice Field", "Copy Target Area", "Action Button"]


class ReturnsTask(BaseTask):
    name = "Returns"
    description = "Process return orders from CSV — 15-step SFA form workflow"

    def __init__(self, parent_notebook, tab_name, hub_ref):
        self.coords = load_coordinates(COORDS_FILE)
        self.csv_file = ""
        self.tasks_data = []
        self.results = []

        super().__init__(parent_notebook, tab_name, hub_ref)

    def setup_ui(self):
        """Build task-specific config UI."""
        desc = ctk.CTkLabel(self.config_frame,
                            text="🔁 Returns — Load CSV → Auto-fill Return Order forms → Export results",
                            font=("Segoe UI", 12), text_color="#e74c3c")
        desc.pack(anchor="w", padx=10, pady=(5, 5))

        # File picker
        file_row = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        file_row.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(file_row, text="CSV File:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))

        self.file_entry = ctk.CTkEntry(file_row, width=350, state="disabled",
                                        placeholder_text="Select Returns CSV file...")
        self.file_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(file_row, text="Browse", width=90,
                      command=self._browse_file).pack(side="left")

        # Coords setup
        coord_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        coord_frame.pack(fill="x", padx=10, pady=5)

        self.coord_status = ctk.CTkLabel(coord_frame,
                                          text="✅ Coords loaded" if self.coords else "⚠️ No coords — setup required",
                                          font=("Segoe UI", 11),
                                          text_color="#2ecc71" if self.coords else "#e74c3c")
        self.coord_status.pack(side="left", padx=(0, 15))

        ctk.CTkButton(coord_frame, text="Setup Coords", width=120,
                      command=self._start_coord_capture).pack(side="left")

        # Info
        info = ctk.CTkLabel(self.config_frame,
                            text="CSV columns: Order Source Reference, Cons Billing Number, Child Code",
                            font=("Segoe UI", 10), text_color="gray")
        info.pack(anchor="w", padx=10, pady=(0, 5))

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Returns CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.csv_file = path
            self.file_entry.configure(state="normal")
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)
            self.file_entry.configure(state="disabled")
            self._load_csv()

    def _load_csv(self):
        """Load return data from CSV."""
        if not HAS_PANDAS:
            # Fallback: manual CSV parsing
            try:
                import csv
                with open(self.csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    all_rows = list(reader)

                # Deduplicate on (Child Code, Cons Billing Number)
                seen = set()
                self.tasks_data = []
                for row in all_rows:
                    key = (row['Child Code'], row['Cons Billing Number'])
                    if key not in seen:
                        seen.add(key)
                        self.tasks_data.append({
                            'child_code': row['Child Code'],
                            'billing_number': row['Cons Billing Number']
                        })
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load CSV:\n{e}")
                self.log(f"❌ CSV load error: {e}")
                return
        else:
            try:
                df = pd.read_csv(self.csv_file)
                tasks = df[['Child Code', 'Cons Billing Number']].drop_duplicates()
                self.tasks_data = [
                    {'child_code': row['Child Code'], 'billing_number': row['Cons Billing Number']}
                    for _, row in tasks.iterrows()
                ]
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load CSV:\n{e}")
                self.log(f"❌ CSV load error: {e}")
                return

        self.total_items = len(self.tasks_data)
        self.update_stats()
        self.log(f"✅ Loaded {self.total_items} unique return records")

    def _start_coord_capture(self):
        self.log("🎯 Starting coordinate capture in 3 seconds... Switch to your app!")
        threading.Thread(target=self._do_capture, daemon=True).start()

    def _do_capture(self):
        time.sleep(3)
        result = capture_coordinates(COORD_POINTS, COORDS_FILE, callback=self.log)
        if result:
            self.coords = result
            self.coord_status.configure(text="✅ Coords loaded", text_color="#2ecc71")

    def validate(self) -> bool:
        if not self.coords:
            messagebox.showwarning("Warning", "Setup coordinates first!")
            return False
        if not self.csv_file:
            messagebox.showwarning("Warning", "Select a CSV file first!")
            return False
        if not self.tasks_data:
            messagebox.showwarning("Warning", "No return data loaded!")
            return False
        self.results = []
        return True

    def execute(self):
        """Main automation — Returns 15-step workflow."""
        self.log(f"🚀 Starting Returns processing — {self.total_items} records")
        self.log("⏳ Starting in 5 seconds... Switch to your app!")
        time.sleep(5)

        for i, task in enumerate(self.tasks_data):
            if not self.wait_if_paused():
                break

            self.update_progress(i + 1, self.total_items)
            self.log(f"📌 [{i+1}/{self.total_items}] Inv: {task['billing_number']}")

            try:
                success = self._process_one(task)
                if success:
                    self.processed_count += 1
                    self.log(f"✅ Done: {task['billing_number']}")
                else:
                    self.failed_count += 1
                    self.log(f"❌ Failed: {task['billing_number']}")
            except Exception as e:
                self.failed_count += 1
                self.log(f"❌ Error: {task['billing_number']} — {e}")

            self.update_stats()

        # Export results
        if self.results:
            self._save_results()

        # Summary
        total = self.processed_count + self.failed_count
        rate = (self.processed_count / total * 100) if total > 0 else 0
        elapsed = "completed"
        self.log(f"{'='*40}")
        self.log(f"🎉 Returns {elapsed} — {self.processed_count} OK / {self.failed_count} Failed ({rate:.0f}%)")

    def _process_one(self, task: dict) -> bool:
        """Process one return. EXACT 15-step workflow from scriptWithPOPUP.py."""
        try:
            pyautogui.PAUSE = 0.5

            org = task['child_code']
            inv = task['billing_number']

            # 1. Click Sale Order + Enter
            pyautogui.click(self.coords["Sale Order"])
            pyautogui.press('enter')

            # 2. Organization: Clear and Write
            self._clear_field(self.coords["Organization"])
            pyautogui.write(str(org), interval=0.1)

            # 3. Double Tab
            pyautogui.press('tab', presses=2)

            # 4. Fixed fields
            pyautogui.write("IMMEDIATE")
            pyautogui.press('tab')
            pyautogui.write("RETURN")
            pyautogui.press('tab')

            # 5. Return Invoice: Clear and Write
            self._clear_field(self.coords["Return Invoice Field"])
            pyautogui.write(str(inv))
            pyautogui.press('tab')

            # 6. Space + Tab
            pyautogui.press('space')
            pyautogui.press('tab')

            # 7. Reason (14) + 11 Tabs
            pyautogui.write("14")
            pyautogui.press('tab', presses=11)

            # 8. Note
            pyautogui.write("Wrong Printing")
            time.sleep(0.5)

            # 9. ALT + B + N
            pyautogui.keyDown('alt')
            pyautogui.press('b')
            pyautogui.press('n')
            pyautogui.keyUp('alt')
            time.sleep(0.5)

            # 10. Enter
            pyautogui.press('enter')
            time.sleep(0.5)

            # 11. Save (Ctrl+S)
            pyautogui.hotkey('ctrl', 's')
            time.sleep(2.5)

            # 12. Double-click Copy Target and copy
            pyautogui.click(self.coords["Copy Target Area"], clicks=2, interval=0.1)
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)

            # 13. Get clipboard result
            copied_text = pyperclip.paste().strip()
            if copied_text:
                self.results.append(copied_text)
                self.log(f"📋 Result: {copied_text}")

            # 14. Action Button + Enter x2
            pyautogui.click(self.coords["Action Button"])
            time.sleep(0.5)
            pyautogui.press('enter', presses=2, interval=0.3)
            time.sleep(0.5)

            # 15. Close window (Alt+F4)
            pyautogui.hotkey('alt', 'f4')
            time.sleep(1.0)

            return True

        except Exception as e:
            self.log(f"⚠️ Workflow error: {e}")
            return False

    def _clear_field(self, coord):
        """Clear a field by triple-click + delete."""
        if isinstance(coord, list):
            coord = tuple(coord)
        pyautogui.click(coord, clicks=3, interval=0.1)
        time.sleep(0.3)
        pyautogui.press('delete')
        pyautogui.press('backspace')
        time.sleep(0.1)

    def _save_results(self):
        """Save results to Result.txt in the CSV directory."""
        try:
            result_file = os.path.join(os.path.dirname(self.csv_file), "Result.txt")
            with open(result_file, "a", encoding="utf-8") as f:
                if not os.path.exists(result_file) or os.path.getsize(result_file) == 0:
                    f.write("Done\n")
                for r in self.results:
                    f.write(f"{r}\n")
            self.log(f"📄 Results saved to: {result_file}")
        except Exception as e:
            self.log(f"⚠️ Failed to save results: {e}")
