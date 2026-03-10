# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

cliphist-x11 is a lightweight clipboard history manager for **GNOME Wayland**. It provides a Super+Shift+V clipboard panel (similar to Windows 11) using a native GTK UI, supporting text and image entries with pin, delete, search, and clear-all actions.

## Architecture

Two Python scripts communicate through a shared SQLite database:

- **clipdaemon.py** — Background daemon (runs as systemd user service). Listens to the GDK clipboard via GTK, deduplicates via SHA-256 hashing, and stores text/image entries in `~/.local/share/cliphist/history.db`. Images are saved as PNG files in `~/.local/share/cliphist/images/`.
- **clippick.py** — GTK-based picker invoked by a GNOME keybinding. Reads entries from the same SQLite DB and sets the clipboard to the selected item. No auto-paste (Windows-like behavior).

Config constants (MAX_ENTRIES, MAX_IMAGES) are at the top of `clipdaemon.py`. The `clippick.py` DATA_DIR/DB_PATH must match the daemon's paths.

## Key Files

- `scripts/clipdaemon.py` — Daemon: DB schema, GDK clipboard listener, image saving, entry pruning
- `scripts/clippick.py` — Picker: GTK UI, search, pin/delete/clear, clipboard set
- `systemd/cliphist.service` — Systemd user unit (GNOME Wayland)
- `install.sh` — Installs scripts and service, sets GNOME Super+Shift+V keybinding

## Installation & Service Commands

```bash
./install.sh                              # full install (GNOME Wayland)
systemctl --user status cliphist          # daemon status
systemctl --user restart cliphist         # restart daemon
journalctl --user -u cliphist -f          # live logs
```

## Dependencies

`python`, `python-gobject`, `gtk4`, `libnotify`.

## Development Notes

- No build step, tests, or linter configured — the project is two standalone Python 3 scripts using GTK via PyGObject.
- The DB schema lives in `clipdaemon.py:init_db()` — single `history` table with columns: id, type (text/image), content, preview, hash (UNIQUE), pinned, created.
- The UI is intentionally copy-only (no auto-paste) to match Windows Win+V behavior.
