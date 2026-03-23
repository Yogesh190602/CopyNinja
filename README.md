# CopyNinja

A lightweight clipboard history manager for Linux desktops (Wayland & X11). Provides a **Super+Shift+V** clipboard panel — similar to Windows 11 — with a native GTK4 UI, search, pin, delete, and auto-paste.

Supports **text and images**, **cross-device sync**, and a **runtime config file**.

## Features

- **Clipboard monitoring** — event-driven on Wayland (`wl-paste --watch`), polling on X11 (`xclip`)
- **Text & image support** — captures both text and images (PNG, JPEG, WebP, GIF, BMP) from clipboard
- **GTK4 picker** — dark Catppuccin Mocha theme, live search, image thumbnails, relative timestamps
- **Pin entries** — keep frequently used snippets at the top (protected from pruning)
- **Auto-paste** — pastes into the previously focused window after selection (configurable)
- **Terminal-aware** — uses Ctrl+Shift+V in terminals, Ctrl+V elsewhere
- **Deduplication** — duplicate content is moved to the top, not stored twice
- **Cross-device sync** — optional file-based sync via Syncthing, Nextcloud, or any cloud folder
- **Crash recovery** — automatic backup rotation, recovers from corrupt history files
- **Runtime config** — TOML config file, no rebuild needed to change settings
- **Multi-DE support** — GNOME, KDE, Hyprland, Sway, i3, and more
- **Systemd integration** — auto-starts on login, restarts on failure
- **CI/CD** — GitHub Actions for build, lint, test, and release

## Architecture

```
Daemon (copyninja daemon)             Picker (copyninja pick)
 - monitors clipboard (text + images)  - reads ~/.clipboard_history.json
 - detects MIME types automatically     - shows text previews & image thumbnails
 - deduplicates via MD5 hash           - copies selected entry to clipboard
 - stores entries as JSON              - auto-pastes via wtype/xdotool/ydotool
 - runs as systemd user service        - invoked by Super+Shift+V keybinding
 - optional sync watcher               - writes tombstones for sync deletes
```

**Auto-paste fallback chain:**

| Priority | Tool | Environment |
|----------|------|-------------|
| 1 | `wtype` Ctrl+V | wlroots Wayland (Hyprland, Sway) |
| 2 | `xdotool` Ctrl+V | X11 (skipped on GNOME Wayland) |
| 3 | `ydotool key` Ctrl+V | GNOME Wayland (instant via uinput) |
| 4 | `ydotool type` | Fallback (char-by-char via uinput) |
| 5 | Copy-only + notification | If all tools unavailable |

## Installation

### Dependencies

| Package | Purpose | Arch Linux |
|---------|---------|------------|
| `gtk4` | UI framework | `sudo pacman -S gtk4` |
| `wl-clipboard` | Wayland clipboard access | `sudo pacman -S wl-clipboard` |
| `wtype` | Wayland auto-paste | `sudo pacman -S wtype` |
| `xclip` | X11 clipboard access | `sudo pacman -S xclip` |
| `xdotool` | X11 auto-paste | `sudo pacman -S xdotool` |
| `ydotool` | GNOME Wayland auto-paste | `sudo pacman -S ydotool` |
| `libnotify` | Notifications | `sudo pacman -S libnotify` |
| `rustup` | Rust toolchain | `sudo pacman -S rustup && rustup default stable` |

### Install

```bash
cd copyninja-rs
./install.sh
```

This will:
1. Build the release binary with `cargo build --release`
2. Install to `~/.local/bin/copyninja`
3. Set up the systemd user service
4. Configure the Super+Shift+V keybinding for your DE

### Uninstall

```bash
./uninstall.sh
```

## Usage

The daemon starts automatically on login. Open the picker with **Super+Shift+V**.

### Picker Keybindings

| Key | Action |
|-----|--------|
| `Enter` | Copy & auto-paste selected entry |
| `Ctrl+P` | Toggle pin on selected entry |
| `Ctrl+D` | Delete selected entry |
| `Ctrl+L` | Clear all (two-step confirmation) |
| `Escape` | Close picker |
| Type anything | Live search filter |

### Service Commands

```bash
systemctl --user status copyninja       # Check daemon status
systemctl --user restart copyninja      # Restart daemon
journalctl --user -u copyninja -f       # Live logs
copyninja --version                      # Show version
```

### D-Bus Interface

Add entries programmatically:

```bash
dbus-send --session /com/copyninja/Daemon com.copyninja.Daemon.NewEntry string:"Some text"
```

## Configuration

Create `~/.config/copyninja/config.toml` to customize settings. All fields are optional — missing fields use defaults.

```toml
max_entries = 50          # Max clipboard history entries
max_backups = 3           # Number of backup files for crash recovery
log_level = "info"        # Logging: error, warn, info, debug
auto_paste = true         # Auto-paste after selecting an entry
max_image_size_mb = 10    # Max image size to capture

# Optional: cross-device sync
[sync]
enabled = false
sync_dir = ""             # e.g. "~/Syncthing/copyninja"
```

| Setting | Default | Description |
|---------|---------|-------------|
| `max_entries` | 50 | Maximum clipboard history entries |
| `max_backups` | 3 | Backup file count for crash recovery |
| `history_file` | `~/.clipboard_history.json` | History file path |
| `log_level` | `info` | Log verbosity |
| `auto_paste` | `true` | Auto-paste after selection |
| `image_dir` | `~/.local/share/copyninja/images/` | Image storage directory |
| `max_image_size_mb` | 10 | Max image size to capture (MB) |
| `sync.enabled` | `false` | Enable cross-device sync |
| `sync.sync_dir` | _(empty)_ | Path to sync folder |

## Cross-Device Sync

CopyNinja supports syncing clipboard history across machines using any file-sync tool (Syncthing, Nextcloud, Dropbox, etc.).

### Setup

1. Create a shared folder (e.g. `~/Syncthing/copyninja`)
2. Add to your config:
   ```toml
   [sync]
   enabled = true
   sync_dir = "/home/youruser/Syncthing/copyninja"
   ```
3. Restart the daemon: `systemctl --user restart copyninja`
4. Repeat on other machines

### How it works

- Each clipboard entry is exported as an individual JSON file in `sync_dir/entries/`
- File-sync tools handle file creation/deletion atomically — no merge conflicts
- Deleted entries create tombstone files in `sync_dir/deleted/` to prevent re-import
- Pinned state uses OR logic: if pinned on any device, it stays pinned everywhere
- A unique device ID is generated per machine in `~/.config/copyninja/device_id`

## Desktop Environment Support

| DE | Clipboard | Auto-paste | Keybinding |
|----|-----------|------------|------------|
| Hyprland | wl-paste | wtype | Auto-configured |
| Sway | wl-paste | wtype | Auto-configured |
| GNOME (Wayland) | wl-paste | ydotool | Auto-configured |
| KDE (Wayland) | wl-paste | wtype/ydotool | Manual |
| i3 (X11) | xclip | xdotool | Auto-configured |
| XFCE (X11) | xclip | xdotool | Manual |

## Project Structure

```
copyninja-rs/
├── src/
│   ├── main.rs              # CLI entry point (daemon/pick subcommands)
│   ├── config.rs             # TOML config loading with defaults
│   ├── content.rs            # ClipContent enum (Text/Image)
│   ├── storage.rs            # History storage, backup rotation, dedup, pruning
│   ├── sync.rs               # Cross-device sync (export, import, tombstones, watcher)
│   ├── daemon/
│   │   ├── mod.rs            # Daemon orchestration + retry loop
│   │   ├── session.rs        # Wayland/X11 session detection
│   │   ├── wayland.rs        # wl-paste --watch + MIME type detection
│   │   ├── x11.rs            # xclip polling + MIME type detection
│   │   └── dbus.rs           # D-Bus service
│   └── picker/
│       ├── mod.rs            # Picker entry point
│       ├── app.rs            # GTK4 UI, search, keybindings, image thumbnails
│       ├── paste.rs          # Auto-paste fallback chain + image clipboard
│       └── css.rs            # Catppuccin Mocha theme
├── Cargo.toml
├── CHANGELOG.md
├── install.sh
└── uninstall.sh
```

## Development

```bash
cargo build --release        # Build
cargo test                   # Run 18 unit tests
cargo clippy                 # Lint
cargo fmt                    # Format
```

CI runs automatically on push/PR via GitHub Actions (`.github/workflows/ci.yml`).

## Known Limitations

- **GNOME Wayland auto-paste** — `ydotool key` Ctrl+V may not work on all GNOME versions; falls back to character-by-character typing
- **Image auto-paste** — images are copied to clipboard only (no keyboard simulation); paste manually with Ctrl+V
- **Sync conflicts** — concurrent writes from multiple devices within the same second may cause a race; file-sync tools handle this gracefully in practice

## License

MIT
