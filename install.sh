#!/usr/bin/env bash
# install.sh — One-shot installer for copyninja (GNOME Wayland)
# Run as your normal user (NOT root).
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 0. Validate session ───────────────────────────────────────────────────
if [[ "${XDG_SESSION_TYPE:-}" != "wayland" ]]; then
    error "This build targets GNOME Wayland only. Current session: ${XDG_SESSION_TYPE:-unknown}."
fi
if [[ "${XDG_CURRENT_DESKTOP:-}" != *"GNOME"* ]]; then
    error "This build targets GNOME Wayland only. Current desktop: ${XDG_CURRENT_DESKTOP:-unknown}."
fi
info "Detected session: GNOME Wayland"

# ── 1. Check dependencies ──────────────────────────────────────────────────
info "Checking dependencies…"

MISSING=()
PACKAGES_TO_INSTALL=()

for cmd in python3 notify-send gsettings; do
    command -v "$cmd" &>/dev/null || MISSING+=("$cmd")
done

# Check GTK4 + PyGObject
if ! python3 - <<'PY' &>/dev/null; then
import gi
try:
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk  # noqa: F401
    print("ok")
except Exception as e:
    raise SystemExit(1)
PY
    MISSING+=("gtk4" "python-gobject")
    PACKAGES_TO_INSTALL+=("gtk4" "python-gobject")
fi

# Map common missing commands to package names
for cmd in "${MISSING[@]}"; do
    case "$cmd" in
        python3)     PACKAGES_TO_INSTALL+=("python") ;;
        notify-send) PACKAGES_TO_INSTALL+=("libnotify") ;;
        gsettings)   PACKAGES_TO_INSTALL+=("glib2") ;;
    esac
done

# Deduplicate
if [[ ${#PACKAGES_TO_INSTALL[@]} -gt 0 ]]; then
    PACKAGES_TO_INSTALL=($(printf '%s\n' "${PACKAGES_TO_INSTALL[@]}" | sort -u))
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
    warn "Missing: ${MISSING[*]}"
    echo "Packages needed: ${PACKAGES_TO_INSTALL[*]}"
    echo ""
    read -rp "Auto-install now? [y/N] " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        sudo pacman -S --needed --noconfirm "${PACKAGES_TO_INSTALL[@]}"
        info "Dependencies installed."
    else
        error "Please install missing dependencies manually, then re-run."
    fi
else
    info "All dependencies found."
fi

# ── 2. Install scripts ─────────────────────────────────────────────────────
info "Installing scripts to ~/.local/bin…"
mkdir -p "$HOME/.local/bin"

cp "$SCRIPT_DIR/scripts/clipdaemon.py" "$HOME/.local/bin/clipdaemon.py"
cp "$SCRIPT_DIR/scripts/clippick.py"   "$HOME/.local/bin/clippick.py"
chmod +x "$HOME/.local/bin/clipdaemon.py"
chmod +x "$HOME/.local/bin/clippick.py"

# ── 3. Install GNOME Shell extension ──────────────────────────────────────
info "Installing GNOME Shell extension…"
EXT_UUID="copyninja-clip@copyninja"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
mkdir -p "$EXT_DIR"
cp "$SCRIPT_DIR/extension/metadata.json" "$EXT_DIR/metadata.json"
cp "$SCRIPT_DIR/extension/extension.js"  "$EXT_DIR/extension.js"
info "Extension installed to $EXT_DIR"

# Enable the extension via gsettings (works even before shell has loaded it)
ENABLED_EXTS=$(gsettings get org.gnome.shell enabled-extensions 2>/dev/null || echo "@as []")
if echo "$ENABLED_EXTS" | grep -q "$EXT_UUID"; then
    info "Extension already enabled."
else
    if [[ "$ENABLED_EXTS" == "@as []" ]]; then
        NEW_EXTS="['$EXT_UUID']"
    else
        NEW_EXTS=$(echo "$ENABLED_EXTS" | sed "s|]|, '$EXT_UUID']|")
    fi
    gsettings set org.gnome.shell enabled-extensions "$NEW_EXTS"
    info "Extension enabled via gsettings (takes effect on next login)."
fi

# ── 4. Install systemd user service ────────────────────────────────────────
info "Installing systemd user service…"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"
cp "$SCRIPT_DIR/systemd/copyninja.service" "$SYSTEMD_DIR/copyninja.service"

systemctl --user daemon-reload
systemctl --user enable --now copyninja.service
systemctl --user restart copyninja
info "Daemon started and enabled on login."

# ── 5. Hotkey setup (GNOME) ───────────────────────────────────────────────
info "Setting Super+Shift+V keybinding automatically…"
CLIPHIST_CMD="$HOME/.local/bin/clippick.py"
CUSTOM_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

EXISTING=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "@as []")
FOUND_SLOT=""
for path_entry in $(echo "$EXISTING" | tr -d "[]',"); do
    slot_name=$(gsettings get "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${path_entry}" name 2>/dev/null)
    if [[ "$slot_name" == "'Clipboard History'" ]]; then
        FOUND_SLOT="$path_entry"
        break
    fi
done

if [[ -n "$FOUND_SLOT" ]]; then
    NEW_PATH="$FOUND_SLOT"
else
    SLOT=0
    while echo "$EXISTING" | grep -q "custom${SLOT}/" 2>/dev/null; do
        SLOT=$((SLOT + 1))
    done
    NEW_PATH="${CUSTOM_PATH}/custom${SLOT}/"

    if [[ "$EXISTING" == "@as []" ]]; then
        NEW_LIST="['${NEW_PATH}']"
    else
        NEW_LIST=$(echo "$EXISTING" | sed "s|]|, '${NEW_PATH}']|")
    fi
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_LIST"
fi

gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${NEW_PATH}" name 'Clipboard History'
gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${NEW_PATH}" command "bash -c 'sleep 0.1 && /usr/bin/python3 $CLIPHIST_CMD'"
gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${NEW_PATH}" binding '<Shift><Super>v'
info "Keybinding set: Super+Shift+V → clippick.py"

# ── Done ───────────────────────────────────────────────────────────────────
info "Installation complete!"
echo ""
echo "  Daemon status:  systemctl --user status copyninja"
echo "  History file:   ~/.clipboard_history.json"
echo ""
echo "  Usage:"
echo "    - Copy text normally, it will be saved automatically"
echo "    - Press Super+Shift+V to open picker"
echo "    - Click on any entry to copy it to clipboard"
echo "    - Press Ctrl+V to paste in any app"
echo ""
warn "Logging out in 3 seconds so the GNOME Shell extension can load…"
sleep 3
gnome-session-quit --logout --no-prompt
