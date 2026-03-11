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
import threading
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


def _import_graphical_env():
    """Try to import WAYLAND_DISPLAY / DISPLAY from the graphical session via loginctl."""
    try:
        result = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True, timeout=3, text=True,
        )
        for line in result.stdout.strip().splitlines():
            sid = line.split()[0]
            stype = subprocess.run(
                ["loginctl", "show-session", sid, "-p", "Type", "--value"],
                capture_output=True, timeout=3, text=True,
            ).stdout.strip()
            if stype in ("wayland", "x11"):
                # Get environment from this session's leader PID
                spid = subprocess.run(
                    ["loginctl", "show-session", sid, "-p", "Leader", "--value"],
                    capture_output=True, timeout=3, text=True,
                ).stdout.strip()
                if spid:
                    env_path = Path(f"/proc/{spid}/environ")
                    if env_path.exists():
                        env_data = env_path.read_bytes().split(b"\0")
                        for item in env_data:
                            if item.startswith(b"WAYLAND_DISPLAY="):
                                os.environ["WAYLAND_DISPLAY"] = item.split(b"=", 1)[1].decode()
                            elif item.startswith(b"DISPLAY="):
                                os.environ["DISPLAY"] = item.split(b"=", 1)[1].decode()
                            elif item.startswith(b"XDG_RUNTIME_DIR="):
                                os.environ.setdefault("XDG_RUNTIME_DIR", item.split(b"=", 1)[1].decode())
                return stype
    except Exception:
        pass
    return None


def detect_session_type():
    """Detect whether the session is Wayland or X11."""
    # 1. Check XDG_SESSION_TYPE
    session = os.environ.get("XDG_SESSION_TYPE", "unknown")
    if session in ("wayland", "x11"):
        return session

    # 2. Check display env vars
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"

    # 3. Try loginctl to find graphical session and import its env vars
    detected = _import_graphical_env()
    if detected:
        return detected

    # 4. Check running compositor processes as last resort
    try:
        for proc in ("Hyprland", "sway", "mutter", "kwin_wayland", "weston"):
            r = subprocess.run(["pgrep", "-x", proc], capture_output=True, timeout=2)
            if r.returncode == 0:
                return "wayland"
        for proc in ("Xorg", "i3", "openbox", "xfwm4"):
            r = subprocess.run(["pgrep", "-x", proc], capture_output=True, timeout=2)
            if r.returncode == 0:
                return "x11"
    except Exception:
        pass

    return "unknown"


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
    print("D-Bus object registered", flush=True)

    # Start clipboard watcher (with retry if no display yet)
    _try_start_watcher()


# ── Watcher startup with retry ────────────────────────────────────────────

_watcher_started = False
_retry_count = 0
_MAX_RETRIES = 60  # retry for up to 5 minutes (every 5s)


def _try_start_watcher():
    """Try to start clipboard watcher. Retry every 5s if no display available."""
    global _watcher_started, _retry_count

    session = detect_session_type()

    if session == "wayland" and shutil.which("wl-paste"):
        if _start_wayland_watcher():
            _watcher_started = True
            return
    elif session == "x11" and shutil.which("xclip"):
        if _start_x11_watcher():
            _watcher_started = True
            return

    _retry_count += 1
    if _retry_count <= _MAX_RETRIES:
        print(f"No display found (attempt {_retry_count}/{_MAX_RETRIES}), retrying in 5s…", flush=True)
        GLib.timeout_add_seconds(5, _retry_start_watcher)
    else:
        print("Warning: Could not connect to clipboard after max retries.", flush=True)
        print("Clipboard monitoring via D-Bus only.", flush=True)


def _retry_start_watcher():
    """GLib callback to retry watcher startup."""
    if not _watcher_started:
        _try_start_watcher()
    return False  # don't repeat this timeout


# ── Wayland clipboard watcher (wl-paste --watch) ─────────────────────────

_wl_proc = None


def _start_wayland_watcher():
    """Spawn wl-paste --watch and read clipboard changes in a background thread."""
    global _wl_proc
    try:
        # wl-paste --watch echo "" prints an empty line each time clipboard changes
        # We then fetch the actual content with wl-paste --no-newline
        _wl_proc = subprocess.Popen(
            ["wl-paste", "--type", "text/plain", "--watch", "echo", ""],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Check if it started successfully (give it a moment)
        try:
            _wl_proc.wait(timeout=0.5)
            # If it exited immediately, it failed (no display, etc.)
            stderr = _wl_proc.stderr.read().decode(errors="replace").strip()
            print(f"wl-paste exited immediately: {stderr}", flush=True)
            _wl_proc = None
            return False
        except subprocess.TimeoutExpired:
            pass  # still running = good

        # Start background thread to read notifications
        thread = threading.Thread(target=_wayland_reader, args=(_wl_proc,), daemon=True)
        thread.start()
        print("Wayland clipboard watcher started (wl-paste --watch)", flush=True)
        return True
    except Exception as e:
        print(f"Failed to start Wayland watcher: {e}", flush=True)
        _wl_proc = None
        return False


def _wayland_reader(proc):
    """Background thread: reads wl-paste --watch notifications, fetches content."""
    for _ in proc.stdout:
        # Each line means clipboard changed — fetch current content
        try:
            result = subprocess.run(
                ["wl-paste", "--type", "text/plain", "--no-newline"],
                capture_output=True, timeout=2,
            )
            if result.returncode == 0:
                text = result.stdout.decode("utf-8", errors="replace")
                if text.strip():
                    GLib.idle_add(process_text, text)
        except Exception:
            pass


# ── X11 clipboard watcher (xclip polling) ────────────────────────────────

_x11_last_hash = None


def _start_x11_watcher():
    """Poll X11 clipboard every 500ms using xclip."""
    global _x11_last_hash
    # Test if xclip can connect to the display
    try:
        test = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, timeout=2,
        )
        if test.returncode != 0 and b"Can't open display" in test.stderr:
            print("xclip cannot connect to display", flush=True)
            return False
    except Exception:
        return False
    # Get initial clipboard content hash
    text = _x11_get_clipboard()
    if text:
        _x11_last_hash = get_hash(text)
    GLib.timeout_add(500, _x11_poll)
    print("X11 clipboard watcher started (xclip polling)", flush=True)
    return True


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
    print("Clipboard daemon started (D-Bus)", flush=True)


def _on_name_lost(_connection, _name):
    print("D-Bus name lost — another instance may be running", flush=True)
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
