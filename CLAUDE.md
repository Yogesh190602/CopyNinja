# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CopyNinja is a lightweight clipboard history manager for **Linux desktops (Wayland & X11)**. It provides a Super+Shift+V clipboard panel (similar to Windows 11) using a native GTK UI, supporting text entries with pin, delete, search, and clear-all actions.

## Architecture

The daemon monitors the system clipboard directly — using `wl-paste --watch` on Wayland or `xclip` polling on X11. It stores entries in a JSON file. A GTK picker reads that file to display history.

- **clipdaemon.py** — Background daemon (systemd user service). Monitors the clipboard (Wayland via `wl-paste --watch`, X11 via `xclip` polling), also accepts text via D-Bus (`com.copyninja.Daemon.NewEntry`), deduplicates via MD5 hashing, stores entries in `~/.clipboard_history.json`.
- **clippick.py** — GTK-based picker invoked by a keybinding. Reads `~/.clipboard_history.json`, copies the selected item to the clipboard. User pastes manually with Ctrl+V.

Config constant `MAX_ENTRIES` is at the top of `clipdaemon.py`.

## Key Files

- `scripts/clipdaemon.py` — Daemon: clipboard monitoring, D-Bus service, JSON storage, dedup, entry pruning
- `scripts/clippick.py` — Picker: GTK UI, search, pin/delete/clear, clipboard set
- `systemd/copyninja.service` — Systemd user unit
- `install.sh` — Installs scripts and service; sets DE-specific Super+Shift+V keybinding (GNOME, Hyprland, Sway, i3)
- `uninstall.sh` — Removes everything

## Installation & Service Commands

```bash
./install.sh                              # full install (any Linux DE)
systemctl --user status copyninja         # daemon status
systemctl --user restart copyninja        # restart daemon
journalctl --user -u copyninja -f         # live logs
```

## Dependencies

**Always:** `python`, `python-gobject`, `gtk4`, `libnotify`
**Wayland:** `wl-clipboard` (provides `wl-paste`)
**X11:** `xclip`

## Development Notes

- No build step, tests, or linter configured — two Python 3 scripts.
- The daemon is event-driven on Wayland (`wl-paste --watch` + GLib.IOChannel) and polling-based on X11 (`xclip` every 500ms).
- The picker copies the selected item to clipboard. User pastes manually with Ctrl+V.
