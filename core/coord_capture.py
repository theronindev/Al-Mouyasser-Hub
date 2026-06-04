"""
Universal Coordinate Capture Tool
Shared utility for tasks that need screen coordinate setup.
Uses keyboard 'S' key to capture, ESC to cancel.
"""

import pyautogui
import keyboard
import time
import json
import os


def capture_coordinates(points: list[str], save_path: str, callback=None) -> dict | None:
    """
    Capture screen coordinates interactively.
    
    Args:
        points: List of point names to capture, e.g. ["Create Button", "Title Field"]
        save_path: Path to save the coords JSON file
        callback: Optional function(message: str) for status updates
    
    Returns:
        Dict of {point_name: (x, y)} or None if cancelled
    """
    coords = {}
    
    def log(msg):
        if callback:
            callback(msg)
        print(msg)

    log(f"🎯 Coordinate Capture Mode — {len(points)} points to capture")
    log("Press 'S' to capture each point. Press 'ESC' to cancel.")

    for i, point_name in enumerate(points):
        log(f"👉 [{i+1}/{len(points)}] Hover over: {point_name} → press 'S'")
        
        # Wait for S or ESC
        while True:
            if keyboard.is_pressed('esc'):
                log("❌ Capture cancelled.")
                return None
            if keyboard.is_pressed('s'):
                pos = pyautogui.position()
                coords[point_name] = (pos.x, pos.y)
                log(f"✅ Captured '{point_name}' at ({pos.x}, {pos.y})")
                time.sleep(0.8)  # Debounce
                break
            time.sleep(0.05)

    # Save
    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else '.', exist_ok=True)
    with open(save_path, 'w') as f:
        json.dump(coords, f, indent=2)
    
    log(f"💾 Coordinates saved to {save_path}")
    return coords


def load_coordinates(path: str) -> dict | None:
    """Load previously saved coordinates."""
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return None
