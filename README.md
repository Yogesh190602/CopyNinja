# CopyNinja — Clipboard History Manager for Linux

A lightweight clipboard history panel for Linux desktops (Wayland & X11), inspired by Windows 11's Win+V.
Press **Super+Shift+V** to open a native GTK picker with search, pin, delete, and clear-all.

Supports **GNOME, KDE Plasma, Hyprland, Sway, i3, XFCE**, and more.

---

## How It Works

CopyNinja's daemon monitors the system clipboard directly — no GNOME extension needed. On Wayland it uses `wl-paste --watch` (event-driven), on X11 it polls via `xclip`. Clipboard text is stored in a local JSON file.

```
Copy in any app
      │
      ▼
  System clipboard
      │
      ▼
┌─────────────────────────────────┐
│  clipdaemon.py  (background)    │  ← systemd user service
│                                 │
│  Wayland: wl-paste --watch      │
│  X11: xclip polling (500ms)     │
│  + D-Bus input                  │
│                                 │
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
│  auto-pastes via wtype/xdotool  │
└────────────┬────────────────────┘
             │
             ▼
      Clipboard updated + auto-pasted
```

---

## Installation

```bash
git clone https://github.com/Yogesh190602/CopyNinja.git
cd CopyNinja
chmod +x install.sh
./install.sh
```

The installer:
- Detects your session type (Wayland/X11) and desktop environment
- Installs session-appropriate dependencies (Arch Linux)
- Copies scripts to `~/.local/bin/`
- Enables the systemd user service
- Sets the `Super+Shift+V` keybinding (automatic for GNOME, Hyprland, Sway, i3; manual instructions for others)

No logout required.

---

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

---

## Dependencies

| Package           | Purpose                              | Session   |
|-------------------|--------------------------------------|-----------|
| `python`          | Run daemon + picker                  | All       |
| `python-gobject`  | GTK / GLib / D-Bus bindings          | All       |
| `gtk4`            | Native UI + clipboard access         | All       |
| `libnotify`       | `notify-send` alerts                 | All       |
| `wl-clipboard`    | Clipboard monitoring (`wl-paste`)    | Wayland   |
| `wtype`           | Auto-paste via simulated Ctrl+V      | Wayland   |
| `xclip`           | Clipboard monitoring                 | X11       |
| `xdotool`         | Auto-paste via simulated Ctrl+V      | X11       |

Install for Wayland (Arch):
```bash
sudo pacman -S python python-gobject gtk4 libnotify wl-clipboard wtype
```

Install for X11 (Arch):
```bash
sudo pacman -S python python-gobject gtk4 libnotify xclip xdotool
```

---

## File Layout

```
~/.local/bin/
├── clipdaemon.py                          ← clipboard daemon
└── clippick.py                            ← GTK picker

~/.config/systemd/user/
└── copyninja.service                      ← auto-starts daemon on login

~/.clipboard_history.json                  ← clipboard history store
```

---

## Keybindings (inside picker)

| Key       | Action                             |
|-----------|------------------------------------|
| `Enter`   | Copy selected item and auto-paste  |
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

## Supported Keybinding Setup

| Desktop Environment | Keybinding Setup          |
|---------------------|---------------------------|
| GNOME               | Automatic (gsettings)     |
| Hyprland            | Automatic (hyprland.conf) |
| Sway                | Automatic (sway config)   |
| i3                  | Automatic (i3 config)     |
| KDE / XFCE / Other  | Manual (instructions shown) |

---

## Windows Comparison

| Windows Win+V                | CopyNinja                        |
|------------------------------|----------------------------------|
| Clipboard history panel      | GTK picker UI                    |
| Click entry to copy          | Click/Enter to copy + auto-paste |
| Auto-paste                   | Auto-paste via `wtype`/`xdotool` |
| Cloud sync                   | Local-only JSON                  |
| Polling-based                | Event-driven (Wayland) / polling (X11) |

---

## License

GPL-2.0-or-later
