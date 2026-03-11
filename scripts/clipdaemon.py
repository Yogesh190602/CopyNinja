#!/usr/bin/env python3
"""
clipdaemon.py - Clipboard history daemon for Linux desktops (Wayland & X11)
Monitors the system clipboard directly using wl-paste (Wayland) or xclip (X11),
and also accepts text via D-Bus.
"""

import json
import time
import hashlib
import subprocess
import os
import shutil
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


def detect_session_type():
    """Detect whether the session is Wayland or X11."""
    return os.environ.get("XDG_SESSION_TYPE", "unknown")


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

    # Start clipboard watcher
    session = detect_session_type()
    if session == "wayland" and shutil.which("wl-paste"):
        _start_wayland_watcher()
    elif session == "x11" and shutil.which("xclip"):
        _start_x11_watcher()
    else:
        print(f"Warning: No clipboard watcher available for session type '{session}'")
        print("Clipboard monitoring via D-Bus only.")


# ── Wayland clipboard watcher (wl-paste --watch) ─────────────────────────

_wl_proc = None


def _start_wayland_watcher():
    """Spawn wl-paste --watch to get notified on clipboard changes."""
    global _wl_proc
    try:
        _wl_proc = subprocess.Popen(
            ["wl-paste", "--type", "text/plain", "--watch", "cat"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        # Watch stdout fd for incoming data
        channel = GLib.IOChannel.unix_new(_wl_proc.stdout.fileno())
        channel.set_encoding(None)
        channel.set_flags(GLib.IOFlags.NONBLOCK)
        GLib.io_add_watch(channel, GLib.IOCondition.IN, _on_wl_clip_data)
        print("Wayland clipboard watcher started (wl-paste --watch)")
    except Exception as e:
        print(f"Failed to start Wayland watcher: {e}")


_wl_buffer = b""


def _on_wl_clip_data(channel, condition):
    """Called when wl-paste --watch writes new clipboard content to stdout."""
    global _wl_buffer
    try:
        data = channel.read(65536)
        if data[0] == GLib.IOStatus.NORMAL:
            _wl_buffer += data[1]
            # wl-paste --watch cat outputs clipboard content then waits for next change
            # Process accumulated buffer after a short delay to batch reads
            GLib.timeout_add(50, _process_wl_buffer)
        elif data[0] == GLib.IOStatus.EOF:
            # Process any remaining data
            if _wl_buffer:
                _process_wl_buffer()
            return False
    except Exception:
        pass
    return True


def _process_wl_buffer():
    """Process accumulated wl-paste buffer."""
    global _wl_buffer
    if _wl_buffer:
        try:
            text = _wl_buffer.decode("utf-8", errors="replace")
            _wl_buffer = b""
            process_text(text)
        except Exception:
            _wl_buffer = b""
    return False


# ── X11 clipboard watcher (xclip polling) ────────────────────────────────

_x11_last_hash = None


def _start_x11_watcher():
    """Poll X11 clipboard every 500ms using xclip."""
    global _x11_last_hash
    # Get initial clipboard content hash
    text = _x11_get_clipboard()
    if text:
        _x11_last_hash = get_hash(text)
    GLib.timeout_add(500, _x11_poll)
    print("X11 clipboard watcher started (xclip polling)")


def _x11_get_clipboard():
    """Read current X11 clipboard content via xclip."""
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    return None


def _x11_poll():
    """Poll X11 clipboard for changes."""
    global _x11_last_hash
    text = _x11_get_clipboard()
    if text and text.strip():
        h = get_hash(text.strip())
        if h != _x11_last_hash:
            _x11_last_hash = h
            process_text(text)
    return True  # keep polling


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
    finally:
        if _wl_proc:
            _wl_proc.terminate()


if __name__ == "__main__":
    main()
