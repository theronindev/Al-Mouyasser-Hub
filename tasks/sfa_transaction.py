"""
Task: SFA Transfer Transaction
Org Group: 1st item, SR Group: 4th item.
All shared logic lives in core/sfa_base.py.
"""

import pyautogui
import time

from core.sfa_base import SFABaseTask


class SFATransactionTask(SFABaseTask):
    name = "SFA Transaction"
    description = "Transfer Transaction — Org Group (1st), SR Group (4th)"

    def __init__(self, parent_notebook, tab_name, hub_ref):
        # Config
        self.config = {
            'sr_group_position': 4,
            'delay_short': 0.2,
            'delay_medium': 0.5,
            'delay_long': 2.0,
        }

        # Coordinates — Transfer Transaction
        self.coords = {
            'org_group': (804, 358),
            'sr_group': (800, 395),
            'salesrep': (803, 522),
            'find': (1029, 693),
            'transfer': (1336, 367),
            'search': (1420, 370),
        }

        # UI customization
        self.task_color = "#3498db"
        self.task_description = "📦 Transfer Transaction — Load Excel → Auto-fill SFA forms"
        self.delay_label = "Find Delay (sec):"

        super().__init__(parent_notebook, tab_name, hub_ref)

    def _process_one(self, cv: dict) -> bool:
        """Transfer Transaction workflow — EXACT logic preserved."""
        try:
            time.sleep(self.config['delay_medium'])

            # Org Group — 1st item
            self.select_dropdown_item(self.coords['org_group'], 1)

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
            time.sleep(self.config['delay_long'])

            # Transfer
            pyautogui.click(*self.coords['transfer'])
            time.sleep(self.config['delay_medium'])
            pyautogui.press('enter')
            time.sleep(self.config['delay_short'])

            # Search (reset for next)
            pyautogui.click(*self.coords['search'])
            time.sleep(self.config['delay_medium'])

            return True

        except Exception as e:
            self.log(f"⚠️ UI error: {e}")
            return False
