# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CopyNinja is a lightweight clipboard history manager for **GNOME Wayland**. It provides a Super+Shift+V clipboard panel (similar to Windows 11) using a native GTK UI, supporting text entries with pin, delete, search, and clear-all actions.

## Architecture

A GNOME Shell extension detects clipboard changes and relays text to a background daemon over D-Bus. The daemon stores entries in a JSON file. A GTK picker reads that file to display history.

- **extension/extension.js** — GNOME Shell extension. Listens for `Meta.Selection` owner-changed events and sends text to the daemon via D-Bus (`com.copyninja.Daemon.NewEntry`).
- **clipdaemon.py** — Background daemon (systemd user service). Owns the `com.copyninja.Daemon` D-Bus name, deduplicates via MD5 hashing, stores entries in `~/.clipboard_history.json`.
- **clippick.py** — GTK-based picker invoked by a GNOME keybinding. Reads `~/.clipboard_history.json` and sets the clipboard to the selected item. No auto-paste (Windows-like behavior).

Config constant `MAX_ENTRIES` is at the top of `clipdaemon.py`.

## Key Files

- `scripts/clipdaemon.py` — Daemon: D-Bus service, JSON storage, dedup, entry pruning
- `scripts/clippick.py` — Picker: GTK UI, search, pin/delete/clear, clipboard set
- `extension/extension.js` — GNOME Shell extension: clipboard relay via D-Bus
- `extension/metadata.json` — Extension metadata (UUID, shell version)
- `systemd/copyninja.service` — Systemd user unit (GNOME Wayland)
- `install.sh` — Installs scripts, extension, and service; sets GNOME Super+Shift+V keybinding
- `uninstall.sh` — Removes everything

## Installation & Service Commands

```bash
./install.sh                              # full install (GNOME Wayland)
systemctl --user status copyninja         # daemon status
systemctl --user restart copyninja        # restart daemon
journalctl --user -u copyninja -f         # live logs
```

## Dependencies

`python`, `python-gobject`, `gtk4`, `libnotify`.

## Development Notes

- No build step, tests, or linter configured — two Python 3 scripts + one GNOME Shell extension (ES module).
- The daemon is event-driven (GLib.MainLoop + D-Bus) — no polling or subprocesses.
- The UI is intentionally copy-only (no auto-paste) to match Windows Win+V behavior.
