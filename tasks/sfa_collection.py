"""
Task: SFA Transferred Collection
Org Group: 2nd item, SR Group: 4th item.
CASH validation, Print→Alt+F4 close, error export.
All shared logic lives in core/sfa_base.py.
"""

import pyautogui
import pyperclip
import time
import re
import os
from datetime import datetime

from core.sfa_base import SFABaseTask


class SFACollectionTask(SFABaseTask):
    name = "SFA Collection"
    description = "Transferred Collection — Org Group (2nd), SR Group (4th), CASH validation"

    def __init__(self, parent_notebook, tab_name, hub_ref):
        # Config
        self.config = {
            'sr_group_position': 4,
            'delay_short': 0.2,
            'delay_medium': 0.5,
            'delay_long': 13.0,
        }

        # Coordinates — Transferred Collection
        self.coords = {
            'org_group': (843, 445),
            'sr_group': (841, 475),
            'salesrep': (836, 516),
            'find': (1182, 600),
            'print': (1342, 291),
            'cash': (1300, 804),
            'transfer': (1257, 291),
            'search': (1420, 294),
        }

        # UI customization
        self.task_color = "#e67e22"
        self.task_description = "📋 Transferred Collection — Load Excel → Validate CASH → Transfer"
        self.delay_label = "Find/Print Delay (sec):"

        self.failed_cvs = []

        super().__init__(parent_notebook, tab_name, hub_ref)

    def _validate_extra(self) -> bool:
        """Reset failed CVs list before each run."""
        self.failed_cvs = []
        return True

    def _on_complete(self):
        """Export errors after run completes."""
        if self.failed_cvs:
            self._export_errors()
            self.log(f"📄 {len(self.failed_cvs)} mismatched entries exported to Error file")

    def _process_one(self, cv: dict) -> bool:
        """Transferred Collection workflow — EXACT logic preserved."""
        try:
            time.sleep(self.config['delay_medium'])

            # Org Group — 2nd item
            self.select_dropdown_item(self.coords['org_group'], 2)

            # SR Group — 4th item
            time.sleep(self.config['delay_short'])
            self.select_dropdown_item(self.coords['sr_group'], self.config['sr_group_position'])

            # Salesrep code
            time.sleep(self.config['delay_short'])
            pyautogui.click(*self.coords['salesrep'])
            time.sleep(self.config['delay_short'])
            pyautogui.write(cv['code'])

            # Find
            time.sleep(self.config['delay_short'])
            pyautogui.click(*self.coords['find'])
            time.sleep(self.config['delay_long'])  # 13s wait

            # Print
            pyautogui.click(*self.coords['print'])
            time.sleep(self.config['delay_long'])  # 13s wait for print window

            # Close print window (Alt+F4)
            pyautogui.hotkey('alt', 'f4')
            self.log("✓ Closed print window with Alt+F4")
            time.sleep(self.config['delay_medium'])

            # Copy CASH value
            pyautogui.click(*self.coords['cash'])
            time.sleep(self.config['delay_short'])
            pyperclip.copy('')
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(self.config['delay_short'])

            cash_value = pyperclip.paste()

            # Compare CASH with Excel price
            if self._compare_values(cash_value, cv['price']):
                self.log(f"✅ CASH matches: {cash_value} = {cv['price']}")

                # Transfer
                pyautogui.click(*self.coords['transfer'])
                time.sleep(self.config['delay_medium'])

                # Confirmation Enter
                pyautogui.press('enter')
                time.sleep(self.config['delay_short'])

                # Search (reset)
                pyautogui.click(*self.coords['search'])
                time.sleep(self.config['delay_medium'])

                return True
            else:
                self.log(f"❌ CASH mismatch: Expected {cv['price']}, Found {cash_value}")
                self.failed_cvs.append({
                    'code': cv['code'],
                    'name': cv['name'],
                    'expected': cv['price'],
                    'found': cash_value
                })

                # Search to continue
                pyautogui.click(*self.coords['search'])
                time.sleep(self.config['delay_medium'])

                return False

        except Exception as e:
            self.log(f"⚠️ UI error: {e}")
            return False

    # ── Collection-specific helpers ─────────────────────────────────

    @staticmethod
    def _compare_values(cash_str, excel_price) -> bool:
        """Compare CASH value with Excel price (strip formatting). Exact logic preserved."""
        try:
            cash_clean = re.sub(r'[^\d.]', '', str(cash_str))
            excel_clean = re.sub(r'[^\d.]', '', str(excel_price))
            cash_num = float(cash_clean) if cash_clean else 0
            excel_num = float(excel_clean) if excel_clean else 0
            return cash_num == excel_num
        except Exception:
            return False

    def _export_errors(self):
        """Export failed CVs to Error_Transferred_Collection.txt."""
        try:
            error_file = os.path.join(
                os.path.dirname(self.excel_file),
                "Error_Transferred_Collection.txt"
            )

            with open(error_file, 'w', encoding='utf-8') as f:
                f.write("Error_Transferred_Collection.txt\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Total Errors: {len(self.failed_cvs)}\n\n")

                for failed in self.failed_cvs:
                    f.write(f"CV Code: {failed['code']}\n")
                    f.write(f"CV Name: {failed['name']}\n")
                    f.write(f"Expected (Excel): {failed['expected']}\n")
                    f.write(f"Found (CASH): {failed['found']}\n")
                    f.write("-" * 50 + "\n\n")

            self.log(f"📄 Errors exported to: {error_file}")

        except Exception as e:
            self.log(f"⚠️ Failed to export errors: {e}")
