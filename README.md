# cliphist-x11 — Clipboard History Manager for GNOME Wayland

A lightweight clipboard history panel for GNOME Wayland, similar to Windows 11's Win+V.
Supports text and images, with pin, delete, search, and clear-all.

This build targets **GNOME Wayland only**.

---

## Architecture

```
Copy in any app
      │
      ▼
  GNOME Wayland clipboard
      │
      ▼
┌─────────────────────────────────┐
│  clipdaemon.py  (background)    │  ← systemd user service
│                                 │
│  listens to GDK clipboard       │
│  hashes content (dedup)         │
│  stores in SQLite               │
│  prunes old entries             │
└────────────┬────────────────────┘
             │
             ▼
    ~/.local/share/cliphist/
    ├── history.db       ← SQLite (text + image metadata)
    └── images/          ← PNG files for image entries

─────────────────────────────────────────────

Super+Shift+V
      │
      ▼
┌─────────────────────────────────┐
│  clippick.py (GTK picker)       │
│                                 │
│  reads history.db               │
│  shows Windows-like UI          │
│  selection copies to clipboard  │
└────────────┬────────────────────┘
             │
             ▼
      Clipboard updated
      (manual paste via Ctrl+V)
```

---

## Installation

```bash
git clone <repo>
cd cliphist-x11
chmod +x install.sh
./install.sh
```

The installer sets the GNOME shortcut:
- `Super+Shift+V` → opens clipboard history

---

## Dependencies (Arch Linux)

| Package           | Purpose                         |
|------------------|---------------------------------|
| `python`         | Run daemon + picker             |
| `python-gobject` | GTK bindings                    |
| `gtk4`           | Native UI + clipboard access    |
| `libnotify`      | `notify-send` alerts            |

Install all at once:
```bash
sudo pacman -S python python-gobject gtk4 libnotify
```

---

## File Layout

```
~/.local/bin/
├── clipdaemon.py     ← background daemon
└── clippick.py       ← GTK picker (bind to Super+Shift+V)

~/.config/systemd/user/
└── cliphist.service  ← auto-starts daemon on login

~/.local/share/cliphist/
├── history.db        ← SQLite history store
├── daemon.log        ← daemon log file
└── images/           ← saved clipboard images (PNG)
```

---

## Keybindings (inside picker)

| Key       | Action                          |
|-----------|---------------------------------|
| `Enter`   | Copy selected item              |
| `Ctrl+D`  | Delete selected item            |
| `Ctrl+P`  | Pin/unpin selected item         |
| `Ctrl+L`  | Clear all (press twice to confirm) |
| `Escape`  | Close without copying           |
| Type      | Live search/filter              |

---

## Configuration

Edit the top of `clipdaemon.py` to change:

```python
MAX_ENTRIES = 50    # max text entries stored
MAX_IMAGES  = 10    # max image entries stored
```

---

## Daemon Commands

```bash
# Status
systemctl --user status cliphist

# Logs (live)
journalctl --user -u cliphist -f

# Restart
systemctl --user restart cliphist

# Disable autostart
systemctl --user disable cliphist
```

---

## Windows Comparison

| Windows Win+V               | This tool                       |
|----------------------------|----------------------------------|
| Clipboard history panel    | GTK picker UI                    |
| Click entry to copy        | Click/Enter to copy              |
| Manual paste (Ctrl+V)      | Manual paste (Ctrl+V)            |
| Cloud sync                 | Local-only SQLite                |
```
