"""
Task: Tasks Automation
Creates tasks in a web-based task management system.
Supports manual entry (titles+descriptions+date range) and auto-generation mode.
11-step form-filling workflow with coordinate-based navigation.
"""

import customtkinter as ctk
from tkinter import messagebox
import pyautogui
import time
import json
import os
import random
import threading
from datetime import datetime, timedelta

from core.base_task import BaseTask
from core.coord_capture import capture_coordinates, load_coordinates


# Pool of IT tasks for auto-generation mode (from original script.py)
IT_TASKS_POOL = [
    ("Printer Maintenance", "Resolved spooler errors and replaced maintenance kit."),
    ("Workstation Setup", "Cable management and hardware health check."),
    ("Password Resets", "Bulk password resets and MFA configuration."),
    ("Network Troubleshooting", "Investigated Wi-Fi dead zones and AP connectivity."),
    ("Handheld Scanner Fix", "Updated firmware and checked battery health on scanners."),
    ("Antivirus Audit", "Verified virus definitions on warehouse workstations."),
    ("Ticket Queue", "Cleared backlog of low priority support tickets."),
    ("Asset Inventory", "Cataloged new peripherals and updated tracker."),
    ("Email Support", "Fixed Outlook syncing issues for remote users."),
    ("VPN Connectivity", "Assisted sales team with VPN login errors."),
]

COORDS_FILE = os.path.join("configs", "tasks_coords.json")
COORD_POINTS = ["Create Button", "Title Field", "Submit Button"]


class TasksAutomationTask(BaseTask):
    name = "Tasks Automation"
    description = "Auto-create tasks in web task manager with date ranges"

    def __init__(self, parent_notebook, tab_name, hub_ref):
        self.coords = load_coordinates(COORDS_FILE)
        self.mode = "manual"  # "manual" or "auto"
        super().__init__(parent_notebook, tab_name, hub_ref)

    def setup_ui(self):
        """Build task-specific config UI."""
        desc = ctk.CTkLabel(self.config_frame,
                            text="📝 Tasks Automation — Fill web forms with tasks for date ranges",
                            font=("Segoe UI", 12), text_color="#9b59b6")
        desc.pack(anchor="w", padx=10, pady=(5, 5))

        # Mode toggle
        mode_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=10, pady=5)

        self.mode_var = ctk.StringVar(value="manual")
        ctk.CTkRadioButton(mode_frame, text="Manual (enter titles/desc)",
                           variable=self.mode_var, value="manual",
                           command=self._toggle_mode).pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_frame, text="Auto-generate IT tasks",
                           variable=self.mode_var, value="auto",
                           command=self._toggle_mode).pack(side="left", padx=10)

        # Manual input area
        self.manual_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        self.manual_frame.pack(fill="x", padx=10, pady=5)

        left_col = ctk.CTkFrame(self.manual_frame, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        ctk.CTkLabel(left_col, text="Titles (one per line):", font=("Segoe UI", 11)).pack(anchor="w")
        self.title_text = ctk.CTkTextbox(left_col, height=70, width=220)
        self.title_text.pack(fill="x")

        right_col = ctk.CTkFrame(self.manual_frame, fg_color="transparent")
        right_col.pack(side="left", fill="both", expand=True, padx=(5, 0))
        ctk.CTkLabel(right_col, text="Descriptions (one per line):", font=("Segoe UI", 11)).pack(anchor="w")
        self.desc_text = ctk.CTkTextbox(right_col, height=70, width=220)
        self.desc_text.pack(fill="x")

        # Auto-gen settings
        self.auto_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        # Not packed initially

        auto_row = ctk.CTkFrame(self.auto_frame, fg_color="transparent")
        auto_row.pack(fill="x")
        ctk.CTkLabel(auto_row, text="Weeks back:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 5))
        self.weeks_entry = ctk.CTkEntry(auto_row, width=50)
        self.weeks_entry.insert(0, "3")
        self.weeks_entry.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(auto_row, text="Work start:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 5))
        self.work_start_entry = ctk.CTkEntry(auto_row, width=60)
        self.work_start_entry.insert(0, "08:00")
        self.work_start_entry.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(auto_row, text="Work end:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 5))
        self.work_end_entry = ctk.CTkEntry(auto_row, width=60)
        self.work_end_entry.insert(0, "16:30")
        self.work_end_entry.pack(side="left")

        # Date range
        date_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        date_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(date_frame, text="Start Date (MM-DD-YYYY):", font=("Segoe UI", 11)).pack(side="left", padx=(0, 5))
        self.start_date_entry = ctk.CTkEntry(date_frame, width=120)
        self.start_date_entry.insert(0, datetime.now().strftime("%m-%d-%Y"))
        self.start_date_entry.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(date_frame, text="End Date (MM-DD-YYYY):", font=("Segoe UI", 11)).pack(side="left", padx=(0, 5))
        self.end_date_entry = ctk.CTkEntry(date_frame, width=120)
        self.end_date_entry.insert(0, datetime.now().strftime("%m-%d-%Y"))
        self.end_date_entry.pack(side="left")

        # Weekend config
        weekend_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        weekend_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(weekend_frame, text="Off days:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 10))
        self.fri_var = ctk.BooleanVar(value=True)
        self.sat_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(weekend_frame, text="Friday", variable=self.fri_var).pack(side="left", padx=5)
        ctk.CTkCheckBox(weekend_frame, text="Saturday", variable=self.sat_var).pack(side="left", padx=5)

        # Setup coords button
        coord_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        coord_frame.pack(fill="x", padx=10, pady=5)

        self.coord_status = ctk.CTkLabel(coord_frame,
                                          text="✅ Coords loaded" if self.coords else "⚠️ No coords — setup required",
                                          font=("Segoe UI", 11),
                                          text_color="#2ecc71" if self.coords else "#e74c3c")
        self.coord_status.pack(side="left", padx=(0, 15))

        ctk.CTkButton(coord_frame, text="Setup Coords", width=120,
                      command=self._start_coord_capture).pack(side="left")

    def _toggle_mode(self):
        if self.mode_var.get() == "manual":
            self.auto_frame.pack_forget()
            self.manual_frame.pack(fill="x", padx=10, pady=5,
                                    before=self.config_frame.winfo_children()[-3])  # Before date_frame
        else:
            self.manual_frame.pack_forget()
            self.auto_frame.pack(fill="x", padx=10, pady=5,
                                  before=self.config_frame.winfo_children()[-3])

    def _start_coord_capture(self):
        self.log("🎯 Starting coordinate capture in 3 seconds... Switch to your browser!")
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

        try:
            start = datetime.strptime(self.start_date_entry.get(), "%m-%d-%Y")
            end = datetime.strptime(self.end_date_entry.get(), "%m-%d-%Y")
            if end < start:
                messagebox.showwarning("Warning", "End date must be after start date!")
                return False
        except ValueError:
            messagebox.showwarning("Warning", "Invalid date format! Use MM-DD-YYYY")
            return False

        if self.mode_var.get() == "manual":
            titles = self.title_text.get("0.0", "end").strip().split('\n')
            descs = self.desc_text.get("0.0", "end").strip().split('\n')
            if not titles or titles[0] == "":
                messagebox.showwarning("Warning", "Enter at least one title!")
                return False
            if len(titles) != len(descs):
                messagebox.showwarning("Warning", "Titles and descriptions count must match!")
                return False

        return True

    def execute(self):
        """Main automation — Tasks creation workflow."""
        mode = self.mode_var.get()

        # Build workdays list
        start = datetime.strptime(self.start_date_entry.get(), "%m-%d-%Y")
        end = datetime.strptime(self.end_date_entry.get(), "%m-%d-%Y")

        off_days = []
        if self.fri_var.get():
            off_days.append(4)
        if self.sat_var.get():
            off_days.append(5)

        workdays = []
        curr = start
        while curr <= end:
            if curr.weekday() not in off_days:
                workdays.append(curr.strftime("%m-%d-%Y"))
            curr += timedelta(days=1)

        if not workdays:
            self.log("❌ No workdays in selected range!")
            return

        if mode == "manual":
            self._execute_manual(workdays)
        else:
            self._execute_auto(workdays)

    def _execute_manual(self, workdays: list):
        """Manual mode: user-provided titles/descriptions for each workday."""
        titles = self.title_text.get("0.0", "end").strip().split('\n')
        descs = self.desc_text.get("0.0", "end").strip().split('\n')

        self.total_items = len(workdays) * len(titles)
        self.update_stats()

        self.log(f"🚀 Manual mode — {len(titles)} tasks × {len(workdays)} days = {self.total_items} entries")
        self.log("⏳ Starting in 5 seconds... Switch to your browser!")
        time.sleep(5)

        count = 0
        for date_val in workdays:
            for i in range(len(titles)):
                if not self.wait_if_paused():
                    return

                count += 1
                self.update_progress(count, self.total_items)
                self.log(f"📌 [{count}/{self.total_items}] {titles[i]} ({date_val})")

                try:
                    self._fill_form(titles[i], descs[i], date_val, "08:00", "a",
                                    date_val, "04:30", "p")
                    self.processed_count += 1
                except Exception as e:
                    self.failed_count += 1
                    self.log(f"❌ Error: {e}")

                self.update_stats()

        self.log(f"{'='*40}")
        self.log(f"🎉 Manual mode completed — {self.processed_count} created")

    def _execute_auto(self, workdays: list):
        """Auto mode: generate daily schedule with random IT tasks."""
        work_start = self.work_start_entry.get()
        work_end = self.work_end_entry.get()

        # Pre-calculate total for progress
        # Estimate ~5 tasks per day
        estimated_total = len(workdays) * 5
        self.total_items = estimated_total
        self.update_stats()

        self.log(f"🚀 Auto mode — {len(workdays)} days, generating schedules...")
        self.log("⏳ Starting in 5 seconds... Switch to your browser!")
        time.sleep(5)

        count = 0
        for date_val in workdays:
            if not self.wait_if_paused():
                return

            schedule = self._generate_daily_schedule(work_start, work_end)

            for task in schedule:
                if not self.wait_if_paused():
                    return

                count += 1
                self.total_items = max(self.total_items, count)  # Adjust as we go
                self.update_progress(count, self.total_items)
                self.log(f"📌 [{count}] {task['title']} ({date_val} {task['start']}-{task['end']})")

                try:
                    s_hour, s_p = self._get_am_pm(task['start'])
                    e_hour, e_p = self._get_am_pm(task['end'])
                    self._fill_form(task['title'], task['desc'],
                                    date_val, s_hour, s_p,
                                    date_val, e_hour, e_p)
                    self.processed_count += 1
                except Exception as e:
                    self.failed_count += 1
                    self.log(f"❌ Error: {e}")

                self.update_stats()

        self.total_items = count
        self.update_stats()
        self.log(f"{'='*40}")
        self.log(f"🎉 Auto mode completed — {self.processed_count} tasks created across {len(workdays)} days")

    def _fill_form(self, title, desc, start_date, start_time, start_ampm,
                   end_date, end_time, end_ampm):
        """11-step form filling workflow. EXACT logic from original."""
        # 1. Click Create
        pyautogui.click(*self.coords['Create Button'])
        time.sleep(2.0)

        # 2-3. Title + Description
        pyautogui.click(*self.coords['Title Field'])
        pyautogui.write(title, interval=0.01)
        pyautogui.press('tab')
        pyautogui.write(desc, interval=0.01)
        pyautogui.press('tab')

        # 4-5. Start date + time
        pyautogui.write(start_date, interval=0.02)
        pyautogui.press('tab')
        pyautogui.write(start_time, interval=0.05)
        pyautogui.write(start_ampm)
        time.sleep(0.3)
        pyautogui.press('tab', presses=2)

        # 6-7. End date + time
        pyautogui.write(end_date, interval=0.02)
        pyautogui.press('tab')
        pyautogui.write(end_time, interval=0.05)
        pyautogui.write(end_ampm)
        time.sleep(0.3)
        pyautogui.press('tab', presses=2)

        # 8. Status (Down x2) + Tab
        pyautogui.press('down', presses=2)
        time.sleep(0.5)
        pyautogui.press('tab')

        # 9. Priority (Down x1) + Submit
        pyautogui.press('down')
        time.sleep(0.5)
        pyautogui.click(*self.coords['Submit Button'])

        # 10-11. Wait + Enter
        time.sleep(2.5)
        pyautogui.press('enter')
        time.sleep(2.5)

    def _generate_daily_schedule(self, work_start: str, work_end: str) -> list:
        """Generate a day's schedule. Exact logic from script.py."""
        schedule = []
        current_time = work_start

        # Task 1: Cashvan (4 hours)
        cashvan_end = self._add_minutes(current_time, 240)
        schedule.append({
            "title": "Cashvan Collection and Transections",
            "desc": "Daily collection and device syncing.",
            "start": current_time,
            "end": cashvan_end
        })
        current_time = cashvan_end

        target_end = datetime.strptime(work_end, "%H:%M")
        while True:
            curr = datetime.strptime(current_time, "%H:%M")
            if curr >= target_end:
                break
            remaining = (target_end - curr).total_seconds() / 60
            duration = random.choice([30, 45, 60])
            if duration > remaining:
                duration = int(remaining)
            if duration <= 15:
                break

            task_info = random.choice(IT_TASKS_POOL)
            end_time = self._add_minutes(current_time, duration)
            schedule.append({
                "title": task_info[0],
                "desc": task_info[1],
                "start": current_time,
                "end": end_time
            })
            current_time = end_time

        return schedule

    @staticmethod
    def _add_minutes(time_str: str, minutes: int) -> str:
        dt = datetime.strptime(time_str, "%H:%M") + timedelta(minutes=minutes)
        return dt.strftime("%H:%M")

    @staticmethod
    def _get_am_pm(time_str: str) -> tuple:
        dt = datetime.strptime(time_str, "%H:%M")
        return dt.strftime("%I:%M"), dt.strftime("%p").lower()[0]
