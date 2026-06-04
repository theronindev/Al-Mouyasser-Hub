"""
Unified Hotkey Manager
Handles: P (pause/resume), Shift+P (stop), ESC (universal emergency stop)
Only acts on the currently active task tab.
"""

import keyboard


class HotkeyManager:
    def __init__(self, hub_ref):
        self.hub = hub_ref
        self._registered = False

    def register(self):
        """Register all global hotkeys."""
        if self._registered:
            return
        keyboard.add_hotkey('p', self._on_pause, suppress=False)
        keyboard.add_hotkey('shift+p', self._on_stop, suppress=False)
        keyboard.add_hotkey('esc', self._on_emergency_stop, suppress=False)
        self._registered = True

    def unregister(self):
        """Remove all hotkeys."""
        if not self._registered:
            return
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._registered = False

    def _get_active_task(self):
        """Get the task object for the currently visible tab."""
        return self.hub.get_active_task()

    def _on_pause(self):
        task = self._get_active_task()
        if task and task.is_running:
            task.tab.after(0, task.toggle_pause)

    def _on_stop(self):
        task = self._get_active_task()
        if task and task.is_running:
            task.tab.after(0, task.stop)

    def _on_emergency_stop(self):
        """ESC = universal stop — stops ANY running task regardless of active tab."""
        for task in self.hub.get_all_tasks():
            if task.is_running:
                task.tab.after(0, task.stop)
