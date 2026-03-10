#!/usr/bin/env python3
"""
clipdaemon.py - Clipboard history daemon for GNOME Wayland
Receives clipboard text from the GNOME Shell extension via D-Bus.
No polling, no subprocesses — pure event-driven.
"""

import json
import time
import hashlib
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

DATA_FILE = Path.home() / ".clipboard_history.json"
MAX_ENTRIES = 50

DBUS_NAME = "com.copyninja.Daemon"
DBUS_PATH = "/com/copyninja/Daemon"

INTROSPECTION_XML = """
<node>
  <interface name="com.copyninja.Daemon">
    <method name="NewEntry">
      <arg direction="in" type="s" name="text"/>
    </method>
  </interface>
</node>
"""


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


def _handle_method_call(_connection, _sender, _path, _iface, method, params, invocation):
    if method == "NewEntry":
        text = params.unpack()[0]
        process_text(text)
        invocation.return_value(None)


def _on_bus_acquired(connection, _name):
    node_info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
    connection.register_object(
        DBUS_PATH,
        node_info.interfaces[0],
        _handle_method_call,
        None,
        None,
    )
    print("D-Bus object registered")


def _on_name_acquired(_connection, _name):
    print("Clipboard daemon started (D-Bus)")


def _on_name_lost(_connection, _name):
    print("D-Bus name lost — another instance may be running")
    loop.quit()


loop = None


def main():
    global loop
    loop = GLib.MainLoop()

    Gio.bus_own_name(
        Gio.BusType.SESSION,
        DBUS_NAME,
        Gio.BusNameOwnerFlags.NONE,
        _on_bus_acquired,
        _on_name_acquired,
        _on_name_lost,
    )

    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()


if __name__ == "__main__":
    main()
