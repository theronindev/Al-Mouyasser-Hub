# Al-Mouyasser Hub

**Desktop automation suite for SFA, Oracle Forms, and web-based back-office workflows.**

Al-Mouyasser Hub is a Windows desktop application that consolidates repetitive data-entry
workflows into a single, tabbed control panel. Instead of manually keying hundreds of
CashVan transfers, item transfers, return orders, or task entries into legacy forms, the
Hub drives the UI for you — with per-step delay tuning, live progress tracking, validation
against source spreadsheets, and global pause / stop hotkeys that work even when the window
is not focused.

Built by [The Ronin Dev](https://www.theronindev.dev).

---

## Table of Contents

- [Features](#features)
- [Screens & Modules](#screens--modules)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Hub](#running-the-hub)
- [Hotkeys](#hotkeys)
- [Configuration](#configuration)
- [Input File Formats](#input-file-formats)
- [Building a Standalone Executable](#building-a-standalone-executable)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Extending the Hub](#extending-the-hub)
- [Troubleshooting](#troubleshooting)
- [Safety Notes](#safety-notes)
- [License](#license)

---

## Features

| | |
|---|---|
| **Unified launcher** | Six tabs, one window — every automation shares the same controls, stats, and logging. |
| **Global hotkeys** | Pause, stop, and emergency-stop any running task without switching windows. |
| **Per-step delay tuning** | Every `sleep` in a workflow is exposed as an editable field and persisted to JSON. |
| **Coordinate capture** | Point-and-capture screen coordinates with the `S` key — no hard-coded pixel hunting. |
| **Source validation** | CashVan runs cross-check `CV_payment_summary.xls` against `CVN.xls` before touching the form. |
| **Error detection** | Optional image-based popup detection halts a run when the target application throws an error. |
| **Resume support** | Completed records are written to checkpoint files so an interrupted run can pick up where it stopped. |
| **Live activity log** | Per-task log plus a collapsible global activity feed with timestamps. |
| **Progress & stats** | Total / processed / failed counters and a progress bar for every task. |

---

## Screens & Modules

| Tab | Module | What it does |
|---|---|---|
| **SFA** | `tasks/sfa_cashvan.py` | CashVan Transfer Transaction and Transferred Collection. Loads and cross-validates the payment summary against CVN data, filters by department / SR group, fills the SFA form, detects error popups, and exports failures to `Error_Transferred_Collection.txt`. |
| **CV Transfers** | `tasks/cv_transfers.py` | Oracle Forms item uploader (OAUPLD-style). Select the target window, paste item codes and quantities, and the Hub types `item → Enter → 1 → Enter → qty → Down` for each line. Manual control only — you watch the screen and press `P` on any error. |
| **Custom** | `tasks/custom_macro.py` | Build your own macro. Supply one value per line, then configure N steps of *Type from data*, *Type fixed text*, *Press key*, or *Mouse click*. Steps persist to `configs/custom_steps.json`. |
| **Tasks** | `tasks/tasks_automation.py` | Creates entries in a web task manager. Supports manual titles/descriptions or auto-generation from a built-in IT task pool, spread across a date range with configurable off-days and working hours. |
| **Returns** | `tasks/returns.py` | Processes return orders from CSV through the SFA Sale Order form — a 15-step fill → save → copy result → action → close cycle, with results exported at the end. |
| **Settings** | `hub.py` | Central editor for every SFA and CV Transfers step delay, saved to `configs/sfa_delays.json`. |

Two additional SFA variants — `tasks/sfa_transaction.py` and `tasks/sfa_collection.py` — share
their logic through `core/sfa_base.py` and are available for standalone use.

---

## Requirements

- **Windows** — the automations drive Windows desktop applications (Oracle Forms, SFA client).
  `pygetwindow` window targeting and `Alt+F4` handling are Windows-specific.
- **Python 3.10 or newer** (the codebase uses `list[str] | None` style type hints).
- A display session — this is a GUI application and cannot run headless.
- The `keyboard` package registers global hotkeys, which on some systems requires running
  the terminal as Administrator.

### Python dependencies

```
customtkinter >= 5.2.0     # modern themed Tk widgets
pyautogui     >= 0.9.54    # keyboard / mouse automation
openpyxl      >= 3.1.0     # .xlsx reading
xlrd          >= 2.0.1     # legacy .xls reading
pandas        >= 2.0.0     # CSV handling
keyboard      >= 0.13.5    # global hotkeys
pyperclip     >= 1.8.2     # clipboard capture
Pillow        >= 10.0.0    # screenshot / popup detection
PyGetWindow   >= 0.0.9     # window targeting
```

---

## Installation

```bash
git clone https://github.com/theronindev/Al-Mouyasser-Hub.git
cd Al-Mouyasser-Hub

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

---

## Running the Hub

From the project root:

```bash
python hub.py
```

Or double-click **`run_hub.bat`**, which activates the working directory and launches the same
entry point with a pause on exit so errors stay visible.

> **Run from the project root.** Config and checkpoint paths are resolved relative to the
> current working directory (`configs/`, `xls_files/`).

---

## Hotkeys

These are registered globally and work even when the Hub window is not focused.

| Key | Action |
|---|---|
| `P` | Pause / resume the task on the **active tab** |
| `Shift + P` | Stop the task on the **active tab** |
| `Esc` | **Emergency stop** — halts every running task, whichever tab is active |
| `S` | Capture the current cursor position (only during coordinate-capture mode) |

Because `P` and `Esc` are global, avoid typing in other applications while a run is in progress.

---

## Configuration

All runtime configuration lives in `configs/` and is created automatically on first use.

| File | Purpose |
|---|---|
| `sfa_delays.json` | Every step delay for SFA Transaction, SFA Collection, and CV Transfers. |
| `sfa_transaction_coords.json` | Screen coordinates: Org Group, SR Group, Salesrep, Find, Transfer, Search. |
| `sfa_collection_coords.json` | As above, plus Print and CASH. |
| `returns_coords.json` | Sale Order, Organization, Return Invoice Field, Copy Target Area, Action Button. |
| `tasks_coords.json` | Create Button, Title Field, Submit Button. |
| `custom_steps.json` | Saved step definitions for the Custom Macro builder. |
| `error_popup.png` | Reference image used to detect the target application's error dialog. |

### Capturing coordinates

Screen coordinates are resolution- and layout-specific, so they must be captured on the
machine that will run the automation:

1. Open the target application and arrange the window exactly as it will be during the run.
2. In the Hub, click the **Setup** / **Setup Coords** button on the relevant tab.
3. For each prompted point, hover the mouse over it and press **`S`**. Press **`Esc`** to cancel.
4. Coordinates are written to the matching JSON file and reused on every subsequent run.

Re-capture after any change to screen resolution, display scaling, or window position.

### Tuning delays

Open the **Settings** tab (or the expandable delay panel inside a task tab) and adjust any
step. Delays are in seconds and saved immediately. Longer waits — `After Find`, `After Print`
— exist to let the server respond; increase them on slow networks rather than lowering them.

---

## Input File Formats

### SFA CashVan

Point the tab at a folder containing both files:

| File | Required headers |
|---|---|
| `CV_payment_summary.xls` | `SR Code`, `SR name`, `Collected` |
| `CVN.xls` | `SR Code`, `SR name`, `Department` |

Headers are detected automatically wherever they appear in the sheet. Every payment row is
matched against CVN by code and name; mismatches and missing codes are skipped, reported in
the log, and written to `Error_Transferred_Collection.txt` in the same folder. Sample files
are included in `xls_files/`.

Progress checkpoints are written to `completed_transaction.txt` and `completed_collection.txt`
so an interrupted run can resume without reprocessing.

### Returns

A CSV with these columns:

```csv
Order Source Reference,Cons Billing Number,Child Code
```

### CV Transfers

Paste item codes and quantities directly into the two textboxes — one value per line, with
line numbers shown alongside. Both lists must be the same length.

### Custom Macro

One value per line in the data box; the configured steps run once per line.

---

## Building a Standalone Executable

A PyInstaller spec is included:

```bash
pip install pyinstaller
pyinstaller hub.spec
```

The binary lands in `dist/hub.exe`. `configs/` and `xls_files/` are **not** bundled — keep
them next to the executable, since the app resolves them relative to the working directory.

---

## Project Structure

```
Al-Mouyasser-Hub/
├── hub.py                  # Application entry point, tab shell, Settings tab
├── hub.spec                # PyInstaller build spec
├── run_hub.bat             # Windows launcher
├── requirements.txt
│
├── core/
│   ├── base_task.py        # BaseTask ABC — shared UI skeleton, threading, stats, logging
│   ├── sfa_base.py         # Shared SFA logic: Excel loading, validation, execution loop
│   ├── hotkeys.py          # Global hotkey manager (P / Shift+P / Esc)
│   └── coord_capture.py    # Interactive screen-coordinate capture utility
│
├── tasks/
│   ├── sfa_cashvan.py      # SFA tab — Transaction + Collection with cross-validation
│   ├── cv_transfers.py     # Oracle Forms item uploader
│   ├── custom_macro.py     # User-defined macro builder
│   ├── tasks_automation.py # Web task-manager automation
│   ├── returns.py          # Returns processing from CSV
│   ├── sfa_transaction.py  # Standalone Transfer Transaction variant
│   └── sfa_collection.py   # Standalone Transferred Collection variant
│
├── configs/                # Coordinates, delays, error-popup reference image
└── xls_files/              # Sample CashVan spreadsheets
```

---

## Architecture

The Hub is a thin shell around a plugin-style task model.

- **`hub.py`** builds the window, registers hotkeys, and instantiates one task object per tab.
  It also owns the global activity log that every task writes into.
- **`core/base_task.py`** defines `BaseTask`, an abstract class that supplies the common
  layout (config area, stats badges, progress bar, controls, log box), background-thread
  execution, and pause / stop / resume state. Subclasses implement `setup_ui()` and their
  own execution logic.
- **`core/sfa_base.py`** sits between `BaseTask` and the two SFA variants, factoring out
  Excel loading, file browsing, validation, and the record loop so each variant only supplies
  its coordinates, delays, and `_process_one()` implementation.
- **`core/hotkeys.py`** routes `P` and `Shift+P` to the task on the active tab, while `Esc`
  fans out to every running task.

Each run executes on its own thread; the UI stays responsive and updates are marshalled back
to the Tk main loop via `after(0, ...)`.

---

## Extending the Hub

To add a new automation tab:

1. Create `tasks/my_task.py` with a class inheriting from `BaseTask` (or `SFABaseTask` if it
   follows the SFA form pattern).
2. Set the class attributes `name` and `description`, and implement `setup_ui()` to build the
   tab's configuration controls inside `self.config_frame`.
3. Implement the execution logic, checking `self.is_running` and `self.is_paused` between
   steps so the global hotkeys remain responsive, and call `self.log(...)` for user-visible
   progress.
4. Register the tab in `hub.py`: add its name to the tab list in `_build_ui()` and instantiate
   it in `_register_tasks()`.

If the task needs screen coordinates, reuse `core/coord_capture.capture_coordinates()` and
persist them under `configs/`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Clicks land in the wrong place | Re-capture coordinates. Screen resolution, DPI scaling, or a moved window will invalidate saved points. |
| Hotkeys do nothing | The `keyboard` package needs elevated privileges on some systems — run the terminal as Administrator. |
| `Cannot find required headers` | Confirm the spreadsheet contains `SR Code`, `SR name`, and `Collected` / `Department`, and that `xlrd` is installed for `.xls` files. |
| Steps run ahead of the application | Increase the relevant delay in **Settings** — the target form is responding slower than the configured wait. |
| Error popups are missed | Recapture `configs/error_popup.png` from your own screen; the reference image must match the dialog pixel-for-pixel. |
| Run stops partway through | Check the activity log for the failing record, then restart — checkpoint files let the run resume from where it stopped. |

---

## Safety Notes

This tool controls the real mouse and keyboard and submits data to live business systems.

- **Test on non-production data first.** Verify coordinates and delays on a sandbox or a
  handful of records before a full run.
- **Do not use the machine during a run.** Any stray click or keystroke becomes part of the
  automation's input.
- **Keep `Esc` within reach.** It stops every running task immediately.
- **Review the log after every run.** Skipped and failed records are reported there and in the
  exported error files — they are not retried silently.

---

## License

Proprietary — internal use. All rights reserved.

---

<p align="center">Built by <a href="https://www.theronindev.dev">The Ronin Dev</a></p>
