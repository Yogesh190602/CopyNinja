# CopyNinja — Clipboard History Manager for GNOME Wayland

A lightweight clipboard history panel for GNOME Wayland, inspired by Windows 11's Win+V.
Press **Super+Shift+V** to open a native GTK picker with search, pin, delete, and clear-all.

---

## How It Works

CopyNinja uses a **GNOME Shell extension** to detect clipboard changes instantly — no polling, no `wl-paste` subprocess hacks. Clipboard text is relayed to a background daemon over **D-Bus**, which stores it in a local JSON file.

```
Copy in any app
      │
      ▼
  GNOME Wayland clipboard
      │
      ▼
┌─────────────────────────────────┐
│  GNOME Shell Extension          │  ← detects clipboard owner-changed
│  (copyninja-clip@copyninja)     │
└────────────┬────────────────────┘
             │  D-Bus call
             ▼
┌─────────────────────────────────┐
│  clipdaemon.py  (background)    │  ← systemd user service
│                                 │
│  receives text via D-Bus        │
│  deduplicates (MD5 hash)        │
│  stores in JSON                 │
│  prunes old entries             │
└────────────┬────────────────────┘
             │
             ▼
    ~/.clipboard_history.json

─────────────────────────────────────────────

Super+Shift+V
      │
      ▼
┌─────────────────────────────────┐
│  clippick.py  (GTK picker)      │
│                                 │
│  reads clipboard_history.json   │
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
git clone https://github.com/Yogesh190602/CopyNinja.git
cd CopyNinja
chmod +x install.sh
./install.sh
```

> **Note:** Log out and back in after first install for the GNOME Shell extension to load.

The installer:
- Installs dependencies (Arch/Fedora/Ubuntu)
- Copies scripts to `~/.local/bin/`
- Installs the GNOME Shell extension
- Enables the systemd user service
- Sets the `Super+Shift+V` keybinding

---

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

---

## Dependencies

| Package           | Purpose                      |
|-------------------|------------------------------|
| `python`          | Run daemon + picker          |
| `python-gobject`  | GTK / GLib / D-Bus bindings  |
| `gtk4`            | Native UI + clipboard access |
| `libnotify`       | `notify-send` alerts         |

Install all at once (Arch):
```bash
sudo pacman -S python python-gobject gtk4 libnotify
```

---

## File Layout

```
~/.local/bin/
├── clipdaemon.py                          ← D-Bus daemon
└── clippick.py                            ← GTK picker

~/.config/systemd/user/
└── copyninja.service                      ← auto-starts daemon on login

~/.local/share/gnome-shell/extensions/
└── copyninja-clip@copyninja/
    ├── extension.js                       ← clipboard relay
    └── metadata.json

~/.clipboard_history.json                  ← clipboard history store
```

---

## Keybindings (inside picker)

| Key       | Action                             |
|-----------|------------------------------------|
| `Enter`   | Copy selected item                 |
| `Ctrl+D`  | Delete selected item               |
| `Ctrl+P`  | Pin/unpin selected item            |
| `Ctrl+L`  | Clear all (press twice to confirm) |
| `Escape`  | Close without copying              |
| Type      | Live search/filter                 |

---

## Configuration

Edit the top of `clipdaemon.py`:

```python
MAX_ENTRIES = 50    # max entries stored
```

---

## Service Commands

```bash
# Status
systemctl --user status copyninja

# Logs (live)
journalctl --user -u copyninja -f

# Restart
systemctl --user restart copyninja

# Disable autostart
systemctl --user disable copyninja
```

---

## Windows Comparison

| Windows Win+V                | CopyNinja                        |
|------------------------------|----------------------------------|
| Clipboard history panel      | GTK picker UI                    |
| Click entry to copy          | Click/Enter to copy              |
| Manual paste (Ctrl+V)        | Manual paste (Ctrl+V)            |
| Cloud sync                   | Local-only JSON                  |
| Polling-based                | Event-driven (D-Bus)             |

---

## License

GPL-2.0-or-later
