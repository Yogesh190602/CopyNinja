#!/usr/bin/env python3
"""
clipdaemon.py - Simple clipboard history daemon for GNOME Wayland
Polls clipboard using wl-paste with smart timing.
"""

import os
import sys
import json
import time
import signal
import hashlib
import subprocess
from pathlib import Path

DATA_FILE = Path.home() / ".clipboard_history.json"
MAX_ENTRIES = 50


def load_history():
    """Load history from JSON file."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    """Save history to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(history, f)


def get_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:12]


def is_wl_running():
    """Check if wl-clipboard is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "wl-clipboard"], capture_output=True, timeout=1
        )
        return result.returncode == 0
    except Exception:
        return False


def process_text(text):
    """Process clipboard text."""
    if not text or not text.strip():
        return

    text = text.strip()
    text_hash = get_hash(text)

    history = load_history()

    # Check if already exists
    for entry in history:
        if entry.get("hash") == text_hash:
            # Move to top
            history.remove(entry)
            history.insert(0, entry)
            save_history(history)
            return

    # Add new entry
    preview = text[:100].replace("\n", " ")
    entry = {"text": text, "preview": preview, "hash": text_hash, "time": time.time()}

    history.insert(0, entry)

    # Limit entries
    if len(history) > MAX_ENTRIES:
        history = history[:MAX_ENTRIES]

    save_history(history)


def run_daemon():
    """Run the daemon loop."""
    print("Clipboard daemon started")

    last_content = ""

    while True:
        # Skip if wl-clipboard is running
        if not is_wl_running():
            try:
                result = subprocess.run(
                    ["wl-paste"], capture_output=True, text=True, timeout=0.5
                )
                text = result.stdout.strip()

                # Only process if different from last
                if text and text != last_content:
                    last_content = text
                    process_text(text)
            except Exception:
                pass

        time.sleep(2)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        process_text(
            subprocess.run(
                ["wl-paste"], capture_output=True, text=True, timeout=1
            ).stdout
        )
        return

    run_daemon()


if __name__ == "__main__":
    main()
