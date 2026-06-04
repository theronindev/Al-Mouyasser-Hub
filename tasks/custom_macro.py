"""
Task: Custom Macro Builder
- One data textbox (one value per line)
- Dynamic step configurator: N steps, each with action type + value + delay
- Actions: Type from data, Type fixed text, Press key, Mouse click
- Mouse click uses coordinate capture (press S to mark)
- Steps config saved to configs/custom_steps.json
- Executes all steps for each line of data
"""

import customtkinter as ctk
from tkinter import messagebox
import pyautogui
import time
import os
import json
import threading

from core.base_task import BaseTask

# ── Config file ─────────────────────────────────────────────────────
CUSTOM_CONFIG = os.path.join("configs", "custom_steps.json")

# Action types
ACTIONS = ["Type from data", "Type fixed text", "Press key", "Mouse click"]


def _load_config() -> dict:
    """Load saved custom config."""
    if os.path.exists(CUSTOM_CONFIG):
        try:
            with open(CUSTOM_CONFIG, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"steps": []}


def _save_config(config: dict):
    """Save custom config to JSON."""
    os.makedirs("configs", exist_ok=True)
    with open(CUSTOM_CONFIG, 'w') as f:
        json.dump(config, f, indent=2)


class CustomTask(BaseTask):
    name = "Custom"
    description = "Build custom automation macros with configurable steps"

    def __init__(self, parent_notebook, tab_name, hub_ref):
        self.step_rows = []       # List of step UI row data
        self.saved_config = _load_config()
        super().__init__(parent_notebook, tab_name, hub_ref)

    # ══════════════════════════════════════════════════════════════════
    # UI
    # ══════════════════════════════════════════════════════════════════

    def setup_ui(self):
        # Description
        ctk.CTkLabel(self.config_frame,
                     text="🔧 Custom Macro — Build your own automation sequence",
                     font=("Segoe UI", 12), text_color="#9b59b6").pack(anchor="w", padx=10, pady=(5, 2))

        # ── Top row: Data textbox + Step config side by side ──
        top_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        top_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Data textbox
        data_col = ctk.CTkFrame(top_frame, fg_color="transparent")
        data_col.pack(side="left", fill="both", expand=False, padx=(0, 10))

        ctk.CTkLabel(data_col, text="Data (one per line):",
                     font=("Segoe UI", 11, "bold"), text_color="#3498db").pack(anchor="w")
        self.data_textbox = ctk.CTkTextbox(data_col, height=200, width=180,
                                            font=("Consolas", 11))
        self.data_textbox.pack(fill="both", expand=True)

        # Right: Steps configuration
        steps_col = ctk.CTkFrame(top_frame, fg_color="transparent")
        steps_col.pack(side="left", fill="both", expand=True)

        # Step count control
        count_frame = ctk.CTkFrame(steps_col, fg_color="transparent")
        count_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(count_frame, text="Steps:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 5))

        self.step_count_entry = ctk.CTkEntry(count_frame, width=50, font=("Segoe UI", 11))
        saved_count = len(self.saved_config.get("steps", []))
        self.step_count_entry.insert(0, str(saved_count if saved_count > 0 else 3))
        self.step_count_entry.pack(side="left", padx=(0, 5))

        ctk.CTkButton(count_frame, text="Set Steps", width=90, height=28,
                      font=("Segoe UI", 11),
                      command=self._set_steps).pack(side="left", padx=(0, 10))

        ctk.CTkButton(count_frame, text="💾 Save", width=70, height=28,
                      fg_color="#27ae60", hover_color="#219a52",
                      font=("Segoe UI", 11),
                      command=self._save_steps).pack(side="left", padx=(0, 5))

        ctk.CTkButton(count_frame, text="📂 Load", width=70, height=28,
                      fg_color="#3498db", hover_color="#2980b9",
                      font=("Segoe UI", 11),
                      command=self._load_steps).pack(side="left")

        # Steps header
        header_frame = ctk.CTkFrame(steps_col, fg_color="transparent")
        header_frame.pack(fill="x")

        ctk.CTkLabel(header_frame, text="#", font=("Segoe UI", 10, "bold"),
                     width=25).pack(side="left")
        ctk.CTkLabel(header_frame, text="Action", font=("Segoe UI", 10, "bold"),
                     width=130).pack(side="left", padx=2)
        ctk.CTkLabel(header_frame, text="Value", font=("Segoe UI", 10, "bold"),
                     width=140).pack(side="left", padx=2)
        ctk.CTkLabel(header_frame, text="Delay(s)", font=("Segoe UI", 10, "bold"),
                     width=55).pack(side="left", padx=2)

        # Scrollable steps container
        self.steps_scroll = ctk.CTkScrollableFrame(steps_col, height=160)
        self.steps_scroll.pack(fill="both", expand=True)

        # Build initial steps (from saved or default)
        if saved_count > 0:
            self._load_steps()
        else:
            self._build_step_rows(3)

    # ══════════════════════════════════════════════════════════════════
    # Step row management
    # ══════════════════════════════════════════════════════════════════

    def _set_steps(self):
        """Set the number of steps and rebuild rows."""
        try:
            count = int(self.step_count_entry.get())
            if count < 1 or count > 30:
                messagebox.showwarning("Warning", "Steps must be between 1 and 30")
                return
        except ValueError:
            messagebox.showwarning("Warning", "Enter a valid number")
            return

        self._build_step_rows(count)
        self.log(f"🔧 Set {count} steps")

    def _build_step_rows(self, count: int, config_data: list = None):
        """Build step configuration rows."""
        # Clear existing
        for widget in self.steps_scroll.winfo_children():
            widget.destroy()
        self.step_rows = []

        for i in range(count):
            row_data = {}
            row = ctk.CTkFrame(self.steps_scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)

            # Step number
            ctk.CTkLabel(row, text=f"{i+1}", font=("Segoe UI", 10),
                         width=25).pack(side="left")

            # Action dropdown
            action_var = ctk.StringVar(value=ACTIONS[0])
            action_dropdown = ctk.CTkComboBox(
                row, width=130, values=ACTIONS, variable=action_var,
                font=("Segoe UI", 10), state="readonly",
                command=lambda val, idx=i: self._on_action_change(idx))
            action_dropdown.pack(side="left", padx=2)
            row_data["action_var"] = action_var
            row_data["action_dropdown"] = action_dropdown

            # Value field (text entry)
            value_entry = ctk.CTkEntry(row, width=120, font=("Segoe UI", 10),
                                        placeholder_text="(auto)")
            value_entry.pack(side="left", padx=2)
            value_entry.configure(state="disabled")  # Default: Type from data = disabled
            row_data["value_entry"] = value_entry

            # Capture button (for mouse click, hidden by default)
            capture_btn = ctk.CTkButton(row, text="📍", width=28, height=24,
                                         font=("Segoe UI", 10),
                                         command=lambda idx=i: self._capture_coord(idx))
            # Don't pack yet — only shown for Mouse click
            row_data["capture_btn"] = capture_btn
            row_data["coord"] = None

            # Delay entry
            delay_entry = ctk.CTkEntry(row, width=50, font=("Segoe UI", 10))
            delay_entry.insert(0, "0.3")
            delay_entry.pack(side="left", padx=2)
            row_data["delay_entry"] = delay_entry

            # Load saved config if available
            if config_data and i < len(config_data):
                saved = config_data[i]
                action_var.set(saved.get("action", ACTIONS[0]))
                value_entry.configure(state="normal")
                value_entry.delete(0, "end")
                value_entry.insert(0, saved.get("value", ""))
                delay_entry.delete(0, "end")
                delay_entry.insert(0, str(saved.get("delay", 0.3)))
                if saved.get("coord"):
                    row_data["coord"] = tuple(saved["coord"])
                # Apply UI state based on action
                self._apply_action_ui(i, saved.get("action", ACTIONS[0]), row_data)

            self.step_rows.append(row_data)

        # Update step count entry
        self.step_count_entry.delete(0, "end")
        self.step_count_entry.insert(0, str(count))

    def _on_action_change(self, step_idx: int):
        """Handle action dropdown change — update value field state."""
        if step_idx >= len(self.step_rows):
            return
        row = self.step_rows[step_idx]
        action = row["action_var"].get()
        self._apply_action_ui(step_idx, action, row)

    def _apply_action_ui(self, step_idx: int, action: str, row: dict):
        """Apply UI state based on selected action."""
        value_entry = row["value_entry"]
        capture_btn = row["capture_btn"]

        # Hide capture button by default
        capture_btn.pack_forget()

        if action == "Type from data":
            value_entry.configure(state="normal")
            value_entry.delete(0, "end")
            value_entry.insert(0, "(auto)")
            value_entry.configure(state="disabled", placeholder_text="(auto)")
        elif action == "Type fixed text":
            value_entry.configure(state="normal", placeholder_text="text to type")
            if value_entry.get() == "(auto)":
                value_entry.delete(0, "end")
        elif action == "Press key":
            value_entry.configure(state="normal", placeholder_text="enter, tab, down...")
            if value_entry.get() == "(auto)":
                value_entry.delete(0, "end")
        elif action == "Mouse click":
            coord = row.get("coord")
            if coord:
                value_entry.configure(state="normal")
                value_entry.delete(0, "end")
                value_entry.insert(0, f"{coord[0]}, {coord[1]}")
                value_entry.configure(state="disabled")
            else:
                value_entry.configure(state="normal")
                value_entry.delete(0, "end")
                value_entry.insert(0, "Not set")
                value_entry.configure(state="disabled")
            # Show capture button
            capture_btn.pack(side="left", padx=2)

    # ══════════════════════════════════════════════════════════════════
    # Coordinate capture
    # ══════════════════════════════════════════════════════════════════

    def _capture_coord(self, step_idx: int):
        """Capture mouse coordinate for a step."""
        self.log(f"📍 Step {step_idx+1}: Hover over target position, press 'S' (3 sec delay)...")
        threading.Thread(target=self._do_capture_coord, args=(step_idx,), daemon=True).start()

    def _do_capture_coord(self, step_idx: int):
        time.sleep(3)
        try:
            import keyboard
            self.log(f"👉 Step {step_idx+1}: Hover and press 'S' now...")
            while not keyboard.is_pressed('s'):
                time.sleep(0.05)
            x, y = pyautogui.position()
            time.sleep(0.5)  # Debounce

            self.step_rows[step_idx]["coord"] = (x, y)

            # Update UI
            def _update():
                entry = self.step_rows[step_idx]["value_entry"]
                entry.configure(state="normal")
                entry.delete(0, "end")
                entry.insert(0, f"{x}, {y}")
                entry.configure(state="disabled")
            self.tab.after(0, _update)

            self.log(f"✅ Step {step_idx+1}: Captured ({x}, {y})")

        except Exception as e:
            self.log(f"❌ Capture failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # Save / Load
    # ══════════════════════════════════════════════════════════════════

    def _get_steps_config(self) -> list:
        """Read current step configuration from UI."""
        steps = []
        for row in self.step_rows:
            action = row["action_var"].get()
            value = row["value_entry"].get() if row["value_entry"].cget("state") == "normal" else ""

            try:
                delay = float(row["delay_entry"].get())
            except ValueError:
                delay = 0.3

            step = {
                "action": action,
                "value": value,
                "delay": delay,
            }
            if row.get("coord"):
                step["coord"] = list(row["coord"])

            steps.append(step)
        return steps

    def _save_steps(self):
        """Save step configuration to JSON."""
        config = {"steps": self._get_steps_config()}
        _save_config(config)
        self.saved_config = config
        self.log(f"💾 Saved {len(config['steps'])} steps to custom_steps.json")

    def _load_steps(self):
        """Load step configuration from JSON."""
        config = _load_config()
        steps = config.get("steps", [])
        if not steps:
            self.log("⚠️ No saved steps found")
            return

        self._build_step_rows(len(steps), steps)
        self.saved_config = config
        self.log(f"📂 Loaded {len(steps)} steps from custom_steps.json")

    # ══════════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════════

    def validate(self) -> bool:
        # Check data
        lines = self._parse_data()
        if not lines:
            messagebox.showwarning("Warning", "Data textbox is empty!")
            return False

        # Check steps exist
        if not self.step_rows:
            messagebox.showwarning("Warning", "No steps configured! Click 'Set Steps' first.")
            return False

        # Validate each step
        has_data_step = False
        for i, row in enumerate(self.step_rows):
            action = row["action_var"].get()

            if action == "Type from data":
                has_data_step = True

            elif action == "Type fixed text":
                val = row["value_entry"].get().strip()
                if not val:
                    messagebox.showwarning("Warning", f"Step {i+1}: Fixed text is empty!")
                    return False

            elif action == "Press key":
                val = row["value_entry"].get().strip()
                if not val:
                    messagebox.showwarning("Warning", f"Step {i+1}: Key name is empty!\n"
                                           f"Examples: enter, tab, down, up, escape, space")
                    return False

            elif action == "Mouse click":
                if not row.get("coord"):
                    messagebox.showwarning("Warning", f"Step {i+1}: Mouse coordinate not captured!\n"
                                           f"Click 📍 to capture position.")
                    return False

        if not has_data_step:
            # Warn but don't block — maybe they just want to repeat actions
            pass

        return True

    # ══════════════════════════════════════════════════════════════════
    # Execution
    # ══════════════════════════════════════════════════════════════════

    def _parse_data(self) -> list:
        """Get non-empty lines from data textbox."""
        text = self.data_textbox.get("1.0", "end")
        return [line.strip() for line in text.strip().splitlines() if line.strip()]

    def _check_stop(self) -> bool:
        return not self.is_running

    def execute(self):
        lines = self._parse_data()
        steps = self._get_steps_config()

        self.total_items = len(lines)
        self.update_stats()

        self.log(f"🚀 Starting Custom Macro — {self.total_items} items, {len(steps)} steps each")
        self.log("⏳ Starting in 3 seconds... Get ready!")
        if not self.interruptible_sleep(3):
            return

        for i, data_line in enumerate(lines):
            if not self.wait_if_paused():
                break

            self.update_progress(i + 1, self.total_items)
            self.log(f"📌 [{i+1}/{self.total_items}] Data: {data_line}")

            try:
                success = True
                for step_idx, step in enumerate(steps):
                    if self._check_stop():
                        success = False
                        break

                    action = step["action"]
                    value = step.get("value", "")
                    delay = step.get("delay", 0.3)

                    # Execute action
                    if action == "Type from data":
                        pyautogui.write(data_line)
                    elif action == "Type fixed text":
                        pyautogui.write(value)
                    elif action == "Press key":
                        pyautogui.press(value.strip().lower())
                    elif action == "Mouse click":
                        coord = step.get("coord")
                        if coord:
                            pyautogui.click(coord[0], coord[1])

                    # Wait
                    if delay > 0:
                        if delay >= 1.0:
                            if not self.interruptible_sleep(delay):
                                success = False
                                break
                        else:
                            time.sleep(delay)

                    if self._check_stop():
                        success = False
                        break

                if not self.is_running:
                    self.log(f"⏹️ Stopped during: {data_line}")
                    break

                if success:
                    self.processed_count += 1
                    self.log(f"✅ Done: {data_line}")
                else:
                    self.failed_count += 1

            except Exception as e:
                if not self.is_running:
                    break
                self.failed_count += 1
                self.log(f"❌ Error: {data_line} — {e}")

            self.update_stats()
            if not self.is_running:
                break

        # Summary
        total = self.processed_count + self.failed_count
        rate = (self.processed_count / total * 100) if total > 0 else 0
        self.log(f"{'='*40}")
        self.log(f"🎉 Custom Macro completed — {self.processed_count} OK / {self.failed_count} Failed ({rate:.0f}%)")
