"""
Task: SFA CashVan (Transaction + Collection in one tab)
- All step delays configurable from expandable UI, saved to configs/sfa_delays.json
- Cross-validates CV_payment_summary.xls against CVN.xls
- Progress tracking, error popup detection, department filters
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import pyautogui
import pyperclip
import time
import re
import os
import json
import threading
import unicodedata
from datetime import datetime
from PIL import Image

from core.base_task import BaseTask
from core.coord_capture import capture_coordinates, load_coordinates

# ── .xls support ────────────────────────────────────────────────────
try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False

# ── Constants ───────────────────────────────────────────────────────

PAYMENT_FILENAME = "CV_payment_summary.xls"
CVN_FILENAME = "CVN.xls"

COMPLETED_TRANSACTION_FILE = "completed_transaction.txt"
COMPLETED_COLLECTION_FILE = "completed_collection.txt"

ERROR_POPUP_IMAGE = os.path.join("configs", "error_popup.png")
DELAYS_FILE = os.path.join("configs", "sfa_delays.json")

SR_GROUP_ORDER = [
    "BTY_S", "FD_S PRESALE", "FDI&II CASHVAN", "HPC_S PRESALE",
    "HPCII CASHVAN", "HPCIII CASHVAN", "RCB CASHVAN", "SPC_S PRESALE",
]
DEPT_TO_POSITION = {dept: i + 1 for i, dept in enumerate(SR_GROUP_ORDER)}

COORDS_FILE_TRANSACTION = os.path.join("configs", "sfa_transaction_coords.json")
COORDS_FILE_COLLECTION = os.path.join("configs", "sfa_collection_coords.json")

TRANSACTION_POINTS = ["Org Group", "SR Group", "Salesrep", "Find", "Transfer", "Search"]
COLLECTION_POINTS = ["Org Group", "SR Group", "Salesrep", "Find", "Print", "CASH", "Transfer", "Search"]

# ── Default delays (seconds) ────────────────────────────────────────
# Keys used in workflows — every time.sleep() references one of these

TRANSACTION_DELAY_DEFAULTS = {
    "t_before_org":       ("Before Org Group",       0.5),
    "t_after_org":        ("After Org Group",        0.2),
    "t_after_sr":         ("After SR Group",         0.2),
    "t_click_salesrep":   ("After click Salesrep",   0.2),
    "t_after_write_code": ("After write code",       0.2),
    "t_before_find":      ("Before click Find",      0.2),
    "t_after_find":       ("After Find (wait)",      2.0),
    "t_after_transfer":   ("After click Transfer",   0.5),
    "t_transfer_wait":    ("Transfer wait (error)",  2.0),
    "t_after_enter":      ("After Enter confirm",    0.2),
    "t_after_search":     ("After Search (reset)",   0.5),
}

COLLECTION_DELAY_DEFAULTS = {
    "c_before_org":       ("Before Org Group",       0.5),
    "c_after_org":        ("After Org Group",        0.2),
    "c_after_sr":         ("After SR Group",         0.2),
    "c_click_salesrep":   ("After click Salesrep",   0.2),
    "c_after_write_code": ("After write code",       0.2),
    "c_before_find":      ("Before click Find",      0.2),
    "c_after_find":       ("After Find (wait)",     13.0),
    "c_after_print":      ("After Print (wait)",    13.0),
    "c_after_altf4":      ("After Alt+F4",           0.5),
    "c_click_cash":       ("After click CASH",       0.5),
    "c_after_tripleclick":("After triple-click",     0.5),
    "c_after_ctrlc":      ("After Ctrl+C",           0.5),
    "c_after_transfer":   ("After click Transfer",   3.0),
    "c_transfer_wait":    ("Transfer wait (error)",  2.0),
    "c_after_enter":      ("After Enter confirm",    0.2),
    "c_after_search":     ("After Search (reset)",   0.5),
}


def _load_delays() -> dict:
    """Load saved delays from JSON, or return defaults."""
    defaults = {}
    for key, (label, val) in TRANSACTION_DELAY_DEFAULTS.items():
        defaults[key] = val
    for key, (label, val) in COLLECTION_DELAY_DEFAULTS.items():
        defaults[key] = val

    if os.path.exists(DELAYS_FILE):
        try:
            with open(DELAYS_FILE, 'r') as f:
                saved = json.load(f)
            # Merge saved over defaults (handles new keys added later)
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def _save_delays(delays: dict):
    """Save delays to JSON."""
    os.makedirs("configs", exist_ok=True)
    with open(DELAYS_FILE, 'w') as f:
        json.dump(delays, f, indent=2)


class SFATask(BaseTask):
    name = "SFA CashVan"
    description = "Transfer Transaction & Transferred Collection with auto-validation"

    def __init__(self, parent_notebook, tab_name, hub_ref):
        # Load all delays
        self.delays = _load_delays()

        # Coordinates
        self.coords_transaction = load_coordinates(COORDS_FILE_TRANSACTION)
        self.coords_collection = load_coordinates(COORDS_FILE_COLLECTION)

        # Data
        self.folder_path = ""
        self.cv_data = []
        self.failed_cvs = []
        self.skipped_cvs = []
        self.completed_codes = set()

        # UI entries for delays (filled in setup_ui)
        self.delay_entries = {}

        super().__init__(parent_notebook, tab_name, hub_ref)

    # ══════════════════════════════════════════════════════════════════
    # UI
    # ══════════════════════════════════════════════════════════════════

    def setup_ui(self):
        # Description
        desc = ctk.CTkLabel(self.config_frame,
                            text="📦 SFA CashVan — Auto-fill Transaction or Collection from .xls files",
                            font=("Segoe UI", 12), text_color="#3498db")
        desc.pack(anchor="w", padx=10, pady=(5, 2))

        # ── Mode toggle ──
        mode_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        mode_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(mode_frame, text="Mode:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(0, 10))

        self.mode_var = ctk.StringVar(value="transaction")
        ctk.CTkRadioButton(mode_frame, text="Transfer Transaction",
                           variable=self.mode_var, value="transaction",
                           font=("Segoe UI", 12)).pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_frame, text="Transferred Collection",
                           variable=self.mode_var, value="collection",
                           font=("Segoe UI", 12)).pack(side="left", padx=10)

        # ── Folder picker ──
        folder_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        folder_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(folder_frame, text="Folder:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 10))

        self.folder_entry = ctk.CTkEntry(folder_frame, width=350, state="disabled",
                                          placeholder_text=f"Folder containing {PAYMENT_FILENAME} & {CVN_FILENAME}")
        self.folder_entry.pack(side="left", padx=(0, 10))

        ctk.CTkButton(folder_frame, text="Browse", width=90,
                      command=self._browse_folder).pack(side="left")

        # ── File detection status ──
        self.file_status = ctk.CTkLabel(self.config_frame, text="", font=("Segoe UI", 11))
        self.file_status.pack(anchor="w", padx=10, pady=(0, 5))

        # ── Coordinate setup ──
        coord_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        coord_frame.pack(fill="x", padx=10, pady=5)

        self.coord_trans_status = ctk.CTkLabel(
            coord_frame,
            text="✅ Transaction coords" if self.coords_transaction else "⚠️ No Transaction coords",
            font=("Segoe UI", 11),
            text_color="#2ecc71" if self.coords_transaction else "#e74c3c")
        self.coord_trans_status.pack(side="left", padx=(0, 5))

        ctk.CTkButton(coord_frame, text="Setup", width=70,
                      command=lambda: self._start_coord_capture("transaction")).pack(side="left", padx=(0, 20))

        self.coord_coll_status = ctk.CTkLabel(
            coord_frame,
            text="✅ Collection coords" if self.coords_collection else "⚠️ No Collection coords",
            font=("Segoe UI", 11),
            text_color="#2ecc71" if self.coords_collection else "#e74c3c")
        self.coord_coll_status.pack(side="left", padx=(0, 5))

        ctk.CTkButton(coord_frame, text="Setup", width=70,
                      command=lambda: self._start_coord_capture("collection")).pack(side="left")

        # ── Error popup capture ──
        error_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        error_frame.pack(fill="x", padx=10, pady=5)

        self.error_img_status = ctk.CTkLabel(
            error_frame,
            text="✅ Error image ready" if os.path.exists(ERROR_POPUP_IMAGE) else "⚠️ No error popup image",
            font=("Segoe UI", 11),
            text_color="#2ecc71" if os.path.exists(ERROR_POPUP_IMAGE) else "#e74c3c")
        self.error_img_status.pack(side="left", padx=(0, 5))

        ctk.CTkButton(error_frame, text="Capture Error Image", width=160,
                      command=self._start_error_capture).pack(side="left")

        ctk.CTkLabel(error_frame, text="(trigger an error in SFA first, then capture the Continue button)",
                     font=("Segoe UI", 10), text_color="gray").pack(side="left", padx=10)

        # ── Department skip filters ──
        filter_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        filter_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(filter_frame, text="Skip:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 10))

        self.skip_fdii = ctk.BooleanVar(value=False)
        self.skip_rcb = ctk.BooleanVar(value=False)
        self.skip_hpcii = ctk.BooleanVar(value=False)
        self.skip_hpciii = ctk.BooleanVar(value=False)

        ctk.CTkCheckBox(filter_frame, text="FDI&II", variable=self.skip_fdii,
                        font=("Segoe UI", 11)).pack(side="left", padx=8)
        ctk.CTkCheckBox(filter_frame, text="RCB", variable=self.skip_rcb,
                        font=("Segoe UI", 11)).pack(side="left", padx=8)
        ctk.CTkCheckBox(filter_frame, text="HPCII", variable=self.skip_hpcii,
                        font=("Segoe UI", 11)).pack(side="left", padx=8)
        ctk.CTkCheckBox(filter_frame, text="HPCIII", variable=self.skip_hpciii,
                        font=("Segoe UI", 11)).pack(side="left", padx=8)

        # ── CV filter (specific CVs only) ──
        cv_filter_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        cv_filter_frame.pack(fill="x", padx=10, pady=5)

        # Transaction CV filter
        trans_filter_col = ctk.CTkFrame(cv_filter_frame, fg_color="transparent")
        trans_filter_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ctk.CTkLabel(trans_filter_col, text="Transaction CVs (one per line):",
                     font=("Segoe UI", 10), text_color="#3498db").pack(anchor="w")
        self.cv_filter_transaction = ctk.CTkTextbox(trans_filter_col, height=60, width=200,
                                                     font=("Consolas", 10))
        self.cv_filter_transaction.pack(fill="x")

        # Collection CV filter
        coll_filter_col = ctk.CTkFrame(cv_filter_frame, fg_color="transparent")
        coll_filter_col.pack(side="left", fill="both", expand=True, padx=(10, 0))

        ctk.CTkLabel(coll_filter_col, text="Collection CVs (one per line):",
                     font=("Segoe UI", 10), text_color="#e67e22").pack(anchor="w")
        self.cv_filter_collection = ctk.CTkTextbox(coll_filter_col, height=60, width=200,
                                                    font=("Consolas", 10))
        self.cv_filter_collection.pack(fill="x")

        ctk.CTkLabel(cv_filter_frame, text="Leave empty\nto process all",
                     font=("Segoe UI", 9), text_color="gray").pack(side="left", padx=10)

        # ── Collection resume controls ──
        resume_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        resume_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(resume_frame, text="Collection:", font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 10))

        self.skip_completed = ctk.BooleanVar(value=True)
        self.skip_errors = ctk.BooleanVar(value=False)

        ctk.CTkCheckBox(resume_frame, text="Skip Completed", variable=self.skip_completed,
                        font=("Segoe UI", 11)).pack(side="left", padx=8)
        ctk.CTkCheckBox(resume_frame, text="Skip Errors", variable=self.skip_errors,
                        font=("Segoe UI", 11)).pack(side="left", padx=8)

    def build_delay_settings_in(self, parent_frame):
        """Build the two-column delay settings UI inside the given frame."""
        ctk.CTkLabel(parent_frame, text="SFA Step Delays",
                     font=("Segoe UI", 12, "bold"), text_color="#00d4ff").pack(anchor="w", padx=15, pady=(10, 5))

        cols_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        cols_frame.pack(fill="x", padx=10, pady=5)

        # Left column — Transaction
        left_col = ctk.CTkFrame(cols_frame, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        ctk.CTkLabel(left_col, text="Transaction Delays (sec)",
                     font=("Segoe UI", 12, "bold"), text_color="#3498db").pack(anchor="w", padx=5, pady=(0, 5))

        for key, (label, default_val) in TRANSACTION_DELAY_DEFAULTS.items():
            row = ctk.CTkFrame(left_col, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 11), width=180, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=60, font=("Segoe UI", 11))
            entry.insert(0, str(self.delays.get(key, default_val)))
            entry.pack(side="left", padx=(5, 0))
            self.delay_entries[key] = entry

        # Right column — Collection
        right_col = ctk.CTkFrame(cols_frame, fg_color="transparent")
        right_col.pack(side="left", fill="both", expand=True, padx=(10, 0))

        ctk.CTkLabel(right_col, text="Collection Delays (sec)",
                     font=("Segoe UI", 12, "bold"), text_color="#e67e22").pack(anchor="w", padx=5, pady=(0, 5))

        for key, (label, default_val) in COLLECTION_DELAY_DEFAULTS.items():
            row = ctk.CTkFrame(right_col, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 11), width=180, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=60, font=("Segoe UI", 11))
            entry.insert(0, str(self.delays.get(key, default_val)))
            entry.pack(side="left", padx=(5, 0))
            self.delay_entries[key] = entry

        # Save / Reset buttons
        btn_row = ctk.CTkFrame(parent_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=10)

        ctk.CTkButton(btn_row, text="💾 Save Delays", width=140, height=32,
                      fg_color="#27ae60", hover_color="#219a52",
                      font=("Segoe UI", 12, "bold"),
                      command=self._save_delays_from_ui).pack(side="left", padx=5)

        ctk.CTkButton(btn_row, text="↩ Reset Defaults", width=140, height=32,
                      fg_color="#95a5a6", hover_color="#7f8c8d",
                      font=("Segoe UI", 12, "bold"),
                      command=self._reset_delays).pack(side="left", padx=5)

    def _save_delays_from_ui(self):
        """Read all delay entries from UI, update self.delays, save to JSON."""
        for key, entry in self.delay_entries.items():
            try:
                val = float(entry.get())
                self.delays[key] = val
            except ValueError:
                pass  # Keep existing value
        _save_delays(self.delays)
        self.log("💾 Step delays saved to sfa_delays.json")

    def _reset_delays(self):
        """Reset all delays to defaults in UI and save."""
        for key, (label, default_val) in TRANSACTION_DELAY_DEFAULTS.items():
            self.delays[key] = default_val
            entry = self.delay_entries[key]
            entry.delete(0, "end")
            entry.insert(0, str(default_val))
        for key, (label, default_val) in COLLECTION_DELAY_DEFAULTS.items():
            self.delays[key] = default_val
            entry = self.delay_entries[key]
            entry.delete(0, "end")
            entry.insert(0, str(default_val))
        _save_delays(self.delays)
        self.log("↩ Step delays reset to defaults")

    def d(self, key: str) -> float:
        """Get delay value by key. Shorthand used in workflows."""
        return self.delays.get(key, 0.5)

    # ══════════════════════════════════════════════════════════════════
    # Folder & file loading
    # ══════════════════════════════════════════════════════════════════

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select folder containing .xls files")
        if not path:
            return

        self.folder_path = path
        self.folder_entry.configure(state="normal")
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, path)
        self.folder_entry.configure(state="disabled")

        payment_path = os.path.join(path, PAYMENT_FILENAME)
        cvn_path = os.path.join(path, CVN_FILENAME)

        found_payment = os.path.exists(payment_path)
        found_cvn = os.path.exists(cvn_path)

        if found_payment and found_cvn:
            self.file_status.configure(
                text=f"✅ Found both {PAYMENT_FILENAME} and {CVN_FILENAME}",
                text_color="#2ecc71")
            self._load_and_validate(payment_path, cvn_path)
        else:
            missing = []
            if not found_payment:
                missing.append(PAYMENT_FILENAME)
            if not found_cvn:
                missing.append(CVN_FILENAME)
            self.file_status.configure(
                text=f"❌ Missing: {', '.join(missing)}",
                text_color="#e74c3c")
            self.cv_data = []
            self.total_items = 0
            self.update_stats()

    @staticmethod
    def _find_columns(ws, target_headers: list[str]) -> tuple:
        """Auto-detect header row and column indices by header names."""
        target_lower = [h.lower().strip() for h in target_headers]
        for r in range(min(10, ws.nrows)):
            row_vals = {}
            for c in range(ws.ncols):
                val = str(ws.cell_value(r, c)).lower().strip()
                if val in target_lower:
                    row_vals[val] = c
            if all(t in row_vals for t in target_lower):
                result = {}
                for orig, low in zip(target_headers, target_lower):
                    result[orig] = row_vals[low]
                return r, result
        return None, None

    @staticmethod
    def _clean_name(name: str) -> str:
        """Strip Unicode diacritics/marks and normalize for comparison."""
        # Decompose Unicode, remove combining marks (accents, Arabic diacritics like kasra U+0650)
        normalized = unicodedata.normalize('NFD', name)
        cleaned = ''.join(c for c in normalized if unicodedata.category(c) not in ('Mn', 'Mc', 'Me'))
        return cleaned.upper().strip()

    def _load_and_validate(self, payment_path: str, cvn_path: str):
        """Load both .xls files, cross-validate, map departments."""
        if not HAS_XLRD:
            messagebox.showerror("Error", "xlrd library required for .xls files.\npip install xlrd")
            return

        try:
            # ── Load CV_payment_summary.xls ──
            wb_pay = xlrd.open_workbook(payment_path, on_demand=True)
            ws_pay = wb_pay.sheet_by_index(0)

            hdr_row, pay_cols = self._find_columns(ws_pay, ["SR Code", "SR name", "Collected"])
            if pay_cols is None:
                self.log(f"❌ Cannot find headers (SR Code, SR name, Collected) in {PAYMENT_FILENAME}")
                messagebox.showerror("Error", f"Cannot find required headers in {PAYMENT_FILENAME}.\n"
                                     f"Expected: SR Code, SR name, Collected")
                return

            self.log(f"📄 {PAYMENT_FILENAME}: headers at row {hdr_row}, columns: {pay_cols}")

            payment_data = {}
            for r in range(hdr_row + 1, ws_pay.nrows):
                code = str(ws_pay.cell_value(r, pay_cols["SR Code"])).strip()
                name = str(ws_pay.cell_value(r, pay_cols["SR name"])).strip()
                collected = ws_pay.cell_value(r, pay_cols["Collected"])

                if code and code not in ('', '0'):
                    if code.endswith('.0'):
                        code = code[:-2]
                    payment_data[code] = {'name': name, 'collected': collected}

            self.log(f"📄 Loaded {len(payment_data)} entries from {PAYMENT_FILENAME}")

            # ── Load CVN.xls ──
            wb_cvn = xlrd.open_workbook(cvn_path, on_demand=True)
            ws_cvn = wb_cvn.sheet_by_index(0)

            hdr_row_cvn, cvn_cols = self._find_columns(ws_cvn, ["SR Code", "SR name", "Department"])
            if cvn_cols is None:
                self.log(f"❌ Cannot find headers (SR Code, SR name, Department) in {CVN_FILENAME}")
                messagebox.showerror("Error", f"Cannot find required headers in {CVN_FILENAME}.\n"
                                     f"Expected: SR Code, SR name, Department")
                return

            self.log(f"📄 {CVN_FILENAME}: headers at row {hdr_row_cvn}, columns: {cvn_cols}")

            cvn_data = {}
            for r in range(hdr_row_cvn + 1, ws_cvn.nrows):
                code = str(ws_cvn.cell_value(r, cvn_cols["SR Code"])).strip()
                name = str(ws_cvn.cell_value(r, cvn_cols["SR name"])).strip()
                dept = str(ws_cvn.cell_value(r, cvn_cols["Department"])).strip()

                if code and code not in ('', '0'):
                    if code.endswith('.0'):
                        code = code[:-2]
                    cvn_data[code] = {'name': name, 'department': dept}

            self.log(f"📄 Loaded {len(cvn_data)} entries from {CVN_FILENAME}")

            # ── Cross-validate & merge ──
            self.cv_data = []
            self.skipped_cvs = []

            for code, pay_info in payment_data.items():
                if code not in cvn_data:
                    self.skipped_cvs.append({
                        'code': code, 'name': pay_info['name'],
                        'reason': f"Code not found in {CVN_FILENAME}"
                    })
                    continue

                cvn_info = cvn_data[code]

                if self._clean_name(pay_info['name']) != self._clean_name(cvn_info['name']):
                    self.skipped_cvs.append({
                        'code': code, 'name': pay_info['name'],
                        'reason': f"Name mismatch: '{pay_info['name']}' vs '{cvn_info['name']}' in {CVN_FILENAME}"
                    })
                    continue

                dept = cvn_info['department']
                if dept not in DEPT_TO_POSITION:
                    self.skipped_cvs.append({
                        'code': code, 'name': pay_info['name'],
                        'reason': f"Unknown department: '{dept}'"
                    })
                    continue

                self.cv_data.append({
                    'code': code,
                    'name': pay_info['name'],
                    'price': pay_info['collected'],
                    'department': dept,
                    'sr_group_position': DEPT_TO_POSITION[dept],
                })

            self.total_items = len(self.cv_data)
            self.update_stats()
            self.log(f"✅ {self.total_items} CVs ready to process")

            if self.skipped_cvs:
                self.log(f"⚠️ {len(self.skipped_cvs)} CVs skipped during validation:")
                for s in self.skipped_cvs:
                    self.log(f"   ⊘ {s['code']} ({s['name']}): {s['reason']}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load .xls files:\n{e}")
            self.log(f"❌ Load error: {e}")

    # ══════════════════════════════════════════════════════════════════
    # Progress tracking
    # ══════════════════════════════════════════════════════════════════

    def _get_completed_file(self) -> str:
        filename = COMPLETED_TRANSACTION_FILE if self.mode_var.get() == "transaction" else COMPLETED_COLLECTION_FILE
        return os.path.join(self.folder_path, filename)

    def _load_completed(self):
        self.completed_codes = set()
        path = self._get_completed_file()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    code = line.strip()
                    if code:
                        self.completed_codes.add(code)
        return self.completed_codes

    def _save_completed(self, code: str):
        path = self._get_completed_file()
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f"{code}\n")
        self.completed_codes.add(code)

    def _load_error_codes(self) -> set:
        """Load CV codes from Error_Transferred_Collection.txt."""
        error_codes = set()
        error_file = os.path.join(self.folder_path, "Error_Transferred_Collection.txt")
        if os.path.exists(error_file):
            with open(error_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("CV Code:"):
                        code = line.replace("CV Code:", "").strip()
                        if code:
                            error_codes.add(code)
        return error_codes

    # ══════════════════════════════════════════════════════════════════
    # Error popup detection
    # ══════════════════════════════════════════════════════════════════

    def _start_error_capture(self):
        self.log("📸 Capture Continue Button — in 3 seconds...")
        self.log("   Trigger an error in SFA first, leave the popup visible.")
        self.log("   Press 'S' on TOP-LEFT of the Continue button, then 'S' on BOTTOM-RIGHT.")
        threading.Thread(target=self._do_error_capture, daemon=True).start()

    def _do_error_capture(self):
        time.sleep(3)
        try:
            screenshot = pyautogui.screenshot()
            import keyboard

            self.log("👉 Hover over TOP-LEFT corner of the Continue button → press 'S'")
            while not keyboard.is_pressed('s'):
                time.sleep(0.05)
            x1, y1 = pyautogui.position()
            self.log(f"   ✅ Top-left: ({x1}, {y1})")
            time.sleep(0.8)

            self.log("👉 Hover over BOTTOM-RIGHT corner of the Continue button → press 'S'")
            while not keyboard.is_pressed('s'):
                time.sleep(0.05)
            x2, y2 = pyautogui.position()
            self.log(f"   ✅ Bottom-right: ({x2}, {y2})")
            time.sleep(0.5)

            region = screenshot.crop((x1, y1, x2, y2))
            os.makedirs("configs", exist_ok=True)
            region.save(ERROR_POPUP_IMAGE)

            self.log(f"💾 Continue button image saved to {ERROR_POPUP_IMAGE}")
            self.tab.after(0, lambda: self.error_img_status.configure(
                text="✅ Error image ready", text_color="#2ecc71"))

        except Exception as e:
            self.log(f"❌ Error capture failed: {e}")

    def _check_error_popup(self) -> bool:
        if not os.path.exists(ERROR_POPUP_IMAGE):
            return False
        try:
            location = pyautogui.locateOnScreen(ERROR_POPUP_IMAGE, confidence=0.8)
            if location:
                center = pyautogui.center(location)
                pyautogui.click(center)
                time.sleep(0.5)
                self.log("🔴 Error popup detected → clicked Continue to dismiss")
                return True
        except Exception:
            pass
        return False

    # ══════════════════════════════════════════════════════════════════
    # Coordinate capture
    # ══════════════════════════════════════════════════════════════════

    def _start_coord_capture(self, mode: str):
        if mode == "transaction":
            points = TRANSACTION_POINTS
            label = "Transaction"
        else:
            points = COLLECTION_POINTS
            label = "Collection"

        self.log(f"🎯 Starting {label} coordinate capture in 3 seconds... Switch to your SFA app!")
        threading.Thread(target=self._do_capture, args=(mode, points), daemon=True).start()

    def _do_capture(self, mode: str, points: list):
        time.sleep(3)
        save_path = COORDS_FILE_TRANSACTION if mode == "transaction" else COORDS_FILE_COLLECTION
        result = capture_coordinates(points, save_path, callback=self.log)

        if result:
            if mode == "transaction":
                self.coords_transaction = result
                self.tab.after(0, lambda: self.coord_trans_status.configure(
                    text="✅ Transaction coords", text_color="#2ecc71"))
            else:
                self.coords_collection = result
                self.tab.after(0, lambda: self.coord_coll_status.configure(
                    text="✅ Collection coords", text_color="#2ecc71"))

    # ══════════════════════════════════════════════════════════════════
    # Department filters
    # ══════════════════════════════════════════════════════════════════

    def _get_skipped_departments(self) -> set:
        skipped = set()
        if self.skip_fdii.get():
            skipped.add("FDI&II CASHVAN")
        if self.skip_rcb.get():
            skipped.add("RCB CASHVAN")
        if self.skip_hpcii.get():
            skipped.add("HPCII CASHVAN")
        if self.skip_hpciii.get():
            skipped.add("HPCIII CASHVAN")
        return skipped

    def _get_cv_filter(self) -> set:
        """Get CV codes from the filter textbox for the current mode. Empty set = process all."""
        if self.mode_var.get() == "transaction":
            text = self.cv_filter_transaction.get("1.0", "end")
        else:
            text = self.cv_filter_collection.get("1.0", "end")

        codes = set()
        for line in text.strip().splitlines():
            code = line.strip()
            if code:
                # Normalize: strip ".0" if pasted from Excel
                if code.endswith('.0'):
                    code = code[:-2]
                codes.add(code)
        return codes

    # ══════════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════════

    def validate(self) -> bool:
        if not self.folder_path:
            messagebox.showwarning("Warning", "Select a folder first!")
            return False

        if not self.cv_data:
            messagebox.showwarning("Warning", "No validated CV data to process!")
            return False

        mode = self.mode_var.get()

        if mode == "transaction":
            if not self.coords_transaction:
                messagebox.showwarning("Warning", "Setup Transaction coordinates first!")
                return False
        else:
            if not self.coords_collection:
                messagebox.showwarning("Warning", "Setup Collection coordinates first!")
                return False

        # Read delays from UI entries into self.delays
        self._save_delays_from_ui()

        self.failed_cvs = []
        return True

    # ══════════════════════════════════════════════════════════════════
    # Execution
    # ══════════════════════════════════════════════════════════════════

    def execute(self):
        mode = self.mode_var.get()
        mode_label = "Transfer Transaction" if mode == "transaction" else "Transferred Collection"
        coords = self.coords_transaction if mode == "transaction" else self.coords_collection

        self._load_completed()

        # Check if manual CV filter is active
        cv_filter = self._get_cv_filter()

        if cv_filter:
            # Manual filter: use ONLY these CVs, ignore completed/error status
            remaining = [cv for cv in self.cv_data if cv['code'] in cv_filter]
            self.log(f"🎯 CV filter active: {len(remaining)} CVs match ({', '.join(sorted(cv_filter))})")

            found_codes = {cv['code'] for cv in remaining}
            not_found = cv_filter - found_codes
            if not_found:
                self.log(f"⚠️ CV codes not found in data: {', '.join(sorted(not_found))}")

            already_done = 0
        else:
            remaining = list(self.cv_data)
            already_done = 0

            # Skip Completed — only for Collection when checkbox is checked, always for Transaction
            if mode == "transaction" or self.skip_completed.get():
                before = len(remaining)
                remaining = [cv for cv in remaining if cv['code'] not in self.completed_codes]
                skipped_count = before - len(remaining)
                if skipped_count > 0:
                    already_done = skipped_count
                    self.log(f"⏭️ Skipping {skipped_count} already completed CVs")
                    self.processed_count = skipped_count

            # Skip Errors — only for Collection when checkbox is checked
            if mode == "collection" and self.skip_errors.get():
                error_codes = self._load_error_codes()
                if error_codes:
                    before = len(remaining)
                    remaining = [cv for cv in remaining if cv['code'] not in error_codes]
                    err_skipped = before - len(remaining)
                    if err_skipped > 0:
                        self.log(f"⏭️ Skipping {err_skipped} CVs from error file")

        skipped_depts = self._get_skipped_departments()
        if skipped_depts and not cv_filter:
            # Only apply dept filter when NOT using manual CV filter
            before_filter = len(remaining)
            remaining = [cv for cv in remaining if cv['department'] not in skipped_depts]
            dept_skipped = before_filter - len(remaining)
            if dept_skipped > 0:
                self.log(f"⊘ Skipping {dept_skipped} CVs from filtered departments: {', '.join(skipped_depts)}")

        if not remaining:
            self.log("✅ All CVs already completed! Nothing to do.")
            self.update_stats()
            return

        self.total_items = len(self.cv_data)
        self.update_stats()

        self.log(f"🚀 Starting {mode_label}...")
        self.log(f"📋 {len(remaining)} CVs remaining (of {self.total_items} total)")

        has_error_img = os.path.exists(ERROR_POPUP_IMAGE)
        if has_error_img:
            self.log("🛡️ Error popup detection: ENABLED")
        else:
            self.log("⚠️ Error popup detection: DISABLED (no error image captured)")

        self.log("⏳ Starting in 3 seconds... Get ready!")
        if not self.interruptible_sleep(3):
            return

        for i, cv in enumerate(remaining):
            if not self.wait_if_paused():
                break

            current_num = already_done + i + 1
            self.update_progress(current_num, self.total_items)
            self.log(f"📌 [{current_num}/{self.total_items}] {cv['name']} (Code: {cv['code']}, Dept: {cv['department']})")

            try:
                if mode == "transaction":
                    success = self._process_transaction(cv, coords)
                else:
                    success = self._process_collection(cv, coords)

                if not self.is_running:
                    self.log(f"⏹️ Stopped during: {cv['name']}")
                    break

                if success:
                    self.processed_count += 1
                    self._save_completed(cv['code'])
                    self.log(f"✅ Done: {cv['name']}")
                else:
                    self.failed_count += 1
                    self.log(f"❌ Failed: {cv['name']}")
            except Exception as e:
                if not self.is_running:
                    break
                self.failed_count += 1
                self.log(f"❌ Error: {cv['name']} — {e}")

            self.update_stats()
            if not self.is_running:
                break
            time.sleep(self.d("t_after_search") if mode == "transaction" else self.d("c_after_search"))

        # Post-processing
        if mode == "collection" and self.failed_cvs:
            self._export_errors()

        total = self.processed_count + self.failed_count
        rate = (self.processed_count / total * 100) if total > 0 else 0
        self.log(f"{'='*40}")
        self.log(f"🎉 {mode_label} completed — {self.processed_count} OK / {self.failed_count} Failed ({rate:.0f}%)")
        if self.skipped_cvs:
            self.log(f"⊘ {len(self.skipped_cvs)} were skipped during validation (see log above)")

    # ══════════════════════════════════════════════════════════════════
    # Shared helpers
    # ══════════════════════════════════════════════════════════════════

    def _select_dropdown(self, coords: dict, key: str, position: int):
        coord = coords[key]
        if isinstance(coord, list):
            coord = tuple(coord)
        pyautogui.click(*coord)
        time.sleep(0.5)
        pyautogui.press('home')
        time.sleep(0.2)
        for _ in range(position - 1):
            pyautogui.press('down')
            time.sleep(0.3)
        pyautogui.press('enter')

    def _safe_click(self, coords: dict, key: str):
        coord = coords[key]
        if isinstance(coord, list):
            coord = tuple(coord)
        pyautogui.click(*coord)

    def _check_stop(self) -> bool:
        return not self.is_running

    def _handle_transfer_result(self, coords: dict, mode: str) -> bool:
        """After clicking Transfer: wait, check for error popup, recover."""
        wait_key = "t_transfer_wait" if mode == "transaction" else "c_transfer_wait"
        enter_key = "t_after_enter" if mode == "transaction" else "c_after_enter"
        search_key = "t_after_search" if mode == "transaction" else "c_after_search"

        if not self.interruptible_sleep(self.d(wait_key)):
            return False

        if self._check_error_popup():
            self.log("⚠️ SFA error after Transfer — recovering...")
            time.sleep(0.5)
            self._safe_click(coords, "Search")
            time.sleep(self.d(search_key))
            return False

        if self._check_stop():
            return False

        pyautogui.press('enter')
        time.sleep(self.d(enter_key))

        self._safe_click(coords, "Search")
        time.sleep(self.d(search_key))

        return True

    # ══════════════════════════════════════════════════════════════════
    # Transaction workflow
    # ══════════════════════════════════════════════════════════════════

    def _process_transaction(self, cv: dict, coords: dict) -> bool:
        try:
            time.sleep(self.d("t_before_org"))
            if self._check_stop(): return False

            self._select_dropdown(coords, "Org Group", 1)
            if self._check_stop(): return False

            time.sleep(self.d("t_after_org"))
            self._select_dropdown(coords, "SR Group", cv['sr_group_position'])
            if self._check_stop(): return False

            time.sleep(self.d("t_after_sr"))
            self._safe_click(coords, "Salesrep")
            time.sleep(self.d("t_click_salesrep"))
            pyautogui.write(cv['code'])
            if self._check_stop(): return False

            time.sleep(self.d("t_after_write_code"))
            self._safe_click(coords, "Find")
            if not self.interruptible_sleep(self.d("t_after_find")): return False

            self._safe_click(coords, "Transfer")
            time.sleep(self.d("t_after_transfer"))
            if self._check_stop(): return False
            return self._handle_transfer_result(coords, "transaction")

        except Exception as e:
            self.log(f"⚠️ UI error: {e}")
            return False

    # ══════════════════════════════════════════════════════════════════
    # Collection workflow
    # ══════════════════════════════════════════════════════════════════

    def _process_collection(self, cv: dict, coords: dict) -> bool:
        try:
            time.sleep(self.d("c_before_org"))
            if self._check_stop(): return False

            self._select_dropdown(coords, "Org Group", 2)
            if self._check_stop(): return False

            time.sleep(self.d("c_after_org"))
            self._select_dropdown(coords, "SR Group", cv['sr_group_position'])
            if self._check_stop(): return False

            time.sleep(self.d("c_after_sr"))
            self._safe_click(coords, "Salesrep")
            time.sleep(self.d("c_click_salesrep"))
            pyautogui.write(cv['code'])
            if self._check_stop(): return False

            time.sleep(self.d("c_after_write_code"))
            self._safe_click(coords, "Find")
            if not self.interruptible_sleep(self.d("c_after_find")): return False

            self._safe_click(coords, "Print")
            if not self.interruptible_sleep(self.d("c_after_print")): return False

            pyautogui.hotkey('alt', 'f4')
            self.log("✓ Closed print window with Alt+F4")
            time.sleep(self.d("c_after_altf4"))
            if self._check_stop(): return False

            # Copy CASH value
            self._safe_click(coords, "CASH")
            time.sleep(self.d("c_click_cash"))
            pyautogui.tripleClick()
            time.sleep(self.d("c_after_tripleclick"))
            pyperclip.copy('')
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(self.d("c_after_ctrlc"))
            if self._check_stop(): return False

            cash_value = pyperclip.paste()
            match, cash_rounded, excel_rounded = self._compare_values(cash_value, cv['price'])
            self.log(f"💰 CASH: '{cash_value}' → {cash_rounded} | Excel: '{cv['price']}' → {excel_rounded}")

            if match:
                self.log(f"✅ CASH matches: {cash_rounded} = {excel_rounded}")

                self._safe_click(coords, "Transfer")
                time.sleep(self.d("c_after_transfer"))
                if self._check_stop(): return False
                return self._handle_transfer_result(coords, "collection")
            else:
                self.log(f"❌ CASH mismatch: {cash_rounded} ≠ {excel_rounded}")
                self.failed_cvs.append({
                    'code': cv['code'],
                    'name': cv['name'],
                    'expected': cv['price'],
                    'expected_rounded': excel_rounded,
                    'found': cash_value,
                    'found_rounded': cash_rounded,
                })

                self._safe_click(coords, "Search")
                time.sleep(self.d("c_after_search"))
                return False

        except Exception as e:
            self.log(f"⚠️ UI error: {e}")
            return False

    # ══════════════════════════════════════════════════════════════════
    # Value comparison & error export
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _compare_values(cash_str, excel_price) -> tuple:
        """
        Compare CASH value with Excel price. Both rounded to whole numbers (SFA rounds).
        Returns (match: bool, cash_rounded: int, excel_rounded: int).
        """
        try:
            cash_clean = re.sub(r'[^\d.]', '', str(cash_str))
            excel_clean = re.sub(r'[^\d.]', '', str(excel_price))
            cash_num = round(float(cash_clean)) if cash_clean else 0
            excel_num = round(float(excel_clean)) if excel_clean else 0
            return (cash_num == excel_num, cash_num, excel_num)
        except Exception:
            return (False, 0, 0)

    def _export_errors(self):
        try:
            error_file = os.path.join(self.folder_path, "Error_Transferred_Collection.txt")

            with open(error_file, 'w', encoding='utf-8') as f:
                f.write("Error_Transferred_Collection.txt\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Total Errors: {len(self.failed_cvs)}\n\n")

                for failed in self.failed_cvs:
                    f.write(f"CV Code: {failed['code']}\n")
                    f.write(f"CV Name: {failed['name']}\n")
                    f.write(f"Expected (Excel): {failed['expected']}\n")
                    f.write(f"Expected (Rounded): {failed['expected_rounded']}\n")
                    f.write(f"Found (CASH): {failed['found']}\n")
                    f.write(f"Found (Rounded): {failed['found_rounded']}\n")
                    f.write("-" * 50 + "\n\n")

            self.log(f"📄 Errors exported to: {error_file}")

        except Exception as e:
            self.log(f"⚠️ Failed to export errors: {e}")
