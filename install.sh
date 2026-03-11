#!/usr/bin/env bash
# install.sh — One-shot installer for CopyNinja (Linux desktops: Wayland & X11)
# Run as your normal user (NOT root).
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 0. Detect session ────────────────────────────────────────────────────
SESSION_TYPE="${XDG_SESSION_TYPE:-unknown}"
DESKTOP="${XDG_CURRENT_DESKTOP:-unknown}"

# If XDG vars aren't set (SSH, TTY, etc.), detect from running processes
if [[ "$SESSION_TYPE" == "unknown" || "$SESSION_TYPE" == "tty" ]]; then
    # Try loginctl to get the graphical session type
    if command -v loginctl &>/dev/null; then
        GRAPHICAL_SESSION=$(loginctl list-sessions --no-legend 2>/dev/null \
            | awk '{print $1}' \
            | while read -r sid; do
                stype=$(loginctl show-session "$sid" -p Type --value 2>/dev/null)
                if [[ "$stype" == "wayland" || "$stype" == "x11" ]]; then
                    echo "$stype"
                    break
                fi
            done)
        if [[ -n "${GRAPHICAL_SESSION:-}" ]]; then
            SESSION_TYPE="$GRAPHICAL_SESSION"
        fi
    fi
    # Fallback: check for Wayland/X11 compositor processes
    if [[ "$SESSION_TYPE" == "unknown" || "$SESSION_TYPE" == "tty" ]]; then
        if pgrep -x "Hyprland|sway|mutter|kwin_wayland|weston" &>/dev/null; then
            SESSION_TYPE="wayland"
        elif pgrep -x "Xorg|Xwayland|i3|openbox|xfwm4" &>/dev/null; then
            SESSION_TYPE="x11"
        fi
    fi
fi

if [[ "$DESKTOP" == "unknown" ]]; then
    # Detect DE/WM from running processes
    if pgrep -x "gnome-shell" &>/dev/null; then
        DESKTOP="GNOME"
    elif pgrep -x "Hyprland" &>/dev/null; then
        DESKTOP="Hyprland"
    elif pgrep -x "sway" &>/dev/null; then
        DESKTOP="sway"
    elif pgrep -x "i3" &>/dev/null; then
        DESKTOP="i3"
    elif pgrep -x "plasmashell" &>/dev/null; then
        DESKTOP="KDE"
    elif pgrep -x "xfce4-session" &>/dev/null; then
        DESKTOP="XFCE"
    fi
fi

info "Detected session: $SESSION_TYPE ($DESKTOP)"

if [[ "$SESSION_TYPE" != "wayland" && "$SESSION_TYPE" != "x11" ]]; then
    warn "Could not detect session type. Proceeding anyway — installing both Wayland and X11 tools."
    SESSION_TYPE="both"
fi

# ── 1. Check dependencies ────────────────────────────────────────────────
info "Checking dependencies…"

MISSING=()
PACKAGES_TO_INSTALL=()

# Always required
for cmd in python3 notify-send; do
    command -v "$cmd" &>/dev/null || MISSING+=("$cmd")
done

# Session-specific tools
# xclip + xdotool always needed (fallback for GNOME Wayland via XWayland + X11)
command -v xclip &>/dev/null || MISSING+=("xclip")
command -v xdotool &>/dev/null || MISSING+=("xdotool")
if [[ "$SESSION_TYPE" == "wayland" || "$SESSION_TYPE" == "both" ]]; then
    command -v wl-paste &>/dev/null || MISSING+=("wl-paste")
    command -v wtype &>/dev/null || MISSING+=("wtype")
fi

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

# Map missing commands to package names
for cmd in "${MISSING[@]}"; do
    case "$cmd" in
        python3)     PACKAGES_TO_INSTALL+=("python") ;;
        notify-send) PACKAGES_TO_INSTALL+=("libnotify") ;;
        wl-paste)    PACKAGES_TO_INSTALL+=("wl-clipboard") ;;
        wtype)       PACKAGES_TO_INSTALL+=("wtype") ;;
        xclip)       PACKAGES_TO_INSTALL+=("xclip") ;;
        xdotool)     PACKAGES_TO_INSTALL+=("xdotool") ;;
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

# ── 2. Install scripts ───────────────────────────────────────────────────
info "Installing scripts to ~/.local/bin…"
mkdir -p "$HOME/.local/bin"

cp "$SCRIPT_DIR/scripts/clipdaemon.py" "$HOME/.local/bin/clipdaemon.py"
cp "$SCRIPT_DIR/scripts/clippick.py"   "$HOME/.local/bin/clippick.py"
chmod +x "$HOME/.local/bin/clipdaemon.py"
chmod +x "$HOME/.local/bin/clippick.py"

# ── 3. Install systemd user service ──────────────────────────────────────
info "Installing systemd user service…"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"
cp "$SCRIPT_DIR/systemd/copyninja.service" "$SYSTEMD_DIR/copyninja.service"

systemctl --user daemon-reload
systemctl --user enable copyninja.service
systemctl --user restart copyninja.service
info "Daemon started and enabled on login."
if [[ "$SESSION_TYPE" != "wayland" && "$SESSION_TYPE" != "x11" ]]; then
    info "Note: Daemon will auto-detect the display and start monitoring once a graphical session is available."
fi

# ── 4. Hotkey setup (DE-specific) ────────────────────────────────────────
CLIPHIST_CMD="$HOME/.local/bin/clippick.py"
PICK_CMD="bash -c 'sleep 0.1 && /usr/bin/python3 $CLIPHIST_CMD'"
COPYNINJA_MARKER="# CopyNinja keybinding"

setup_gnome_keybinding() {
    if ! command -v gsettings &>/dev/null; then
        warn "gsettings not found — skipping GNOME keybinding setup."
        return
    fi
    info "Setting Super+Shift+V keybinding (GNOME)…"
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
    gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${NEW_PATH}" command "$PICK_CMD"
    gsettings set "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${NEW_PATH}" binding '<Shift><Super>v'
    info "Keybinding set: Super+Shift+V → clippick.py"
}

setup_wm_keybinding() {
    local config_file="$1"
    local bind_line="$2"

    if [[ ! -f "$config_file" ]]; then
        warn "Config file not found: $config_file — skipping keybinding setup."
        echo "  Add this line manually: $bind_line"
        return
    fi

    # Avoid duplicates
    if grep -qF "$COPYNINJA_MARKER" "$config_file" 2>/dev/null; then
        info "Keybinding already present in $config_file"
        return
    fi

    echo "" >> "$config_file"
    echo "$COPYNINJA_MARKER" >> "$config_file"
    echo "$bind_line" >> "$config_file"
    info "Keybinding added to $config_file"
}

case "$DESKTOP" in
    *GNOME*)
        setup_gnome_keybinding
        ;;
    *Hyprland*|*hyprland*)
        setup_wm_keybinding \
            "$HOME/.config/hypr/hyprland.conf" \
            "bind = SUPER SHIFT, V, exec, $PICK_CMD"
        ;;
    *sway*|*Sway*)
        setup_wm_keybinding \
            "$HOME/.config/sway/config" \
            "bindsym Mod4+Shift+v exec $PICK_CMD"
        ;;
    *i3*|*I3*)
        setup_wm_keybinding \
            "$HOME/.config/i3/config" \
            "bindsym Mod4+Shift+v exec $PICK_CMD"
        ;;
    *)
        warn "Automatic keybinding setup not supported for '$DESKTOP'."
        echo "  Please bind Super+Shift+V to this command manually:"
        echo "  $PICK_CMD"
        ;;
esac

# ── Done ──────────────────────────────────────────────────────────────────
info "Installation complete!"
echo ""
echo "  Daemon status:  systemctl --user status copyninja"
echo "  History file:   ~/.clipboard_history.json"
echo ""
echo "  Usage:"
echo "    - Copy text normally, it will be saved automatically"
echo "    - Press Super+Shift+V to open picker"
echo "    - Click on any entry to copy and auto-paste"
echo ""
info "Everything is ready — no logout needed. Enjoy CopyNinja!"
