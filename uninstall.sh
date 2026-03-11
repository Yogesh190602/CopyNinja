#!/usr/bin/env bash
# uninstall.sh — Remove CopyNinja from the system
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

DESKTOP="${XDG_CURRENT_DESKTOP:-unknown}"
COPYNINJA_MARKER="# CopyNinja keybinding"

echo ""
echo "  This will completely remove CopyNinja from your system."
echo ""
read -rp "  Continue? [y/N] " answer
[[ "$answer" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# Stop and disable the systemd service
if systemctl --user is-active copyninja.service &>/dev/null; then
    systemctl --user stop copyninja.service
    info "Stopped copyninja service."
fi

if systemctl --user is-enabled copyninja.service &>/dev/null; then
    systemctl --user disable copyninja.service
    info "Disabled copyninja service."
fi

rm -f "$HOME/.config/systemd/user/copyninja.service"
systemctl --user daemon-reload
info "Removed systemd unit file."

# Remove scripts
rm -f "$HOME/.local/bin/clipdaemon.py"
rm -f "$HOME/.local/bin/clippick.py"
info "Removed scripts."

# Remove keybinding (DE-specific)
remove_gnome_keybinding() {
    if ! command -v gsettings &>/dev/null; then return; fi
    EXISTING=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "@as []")

    for path_entry in $(echo "$EXISTING" | tr -d "[]',"); do
        slot_name=$(gsettings get "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${path_entry}" name 2>/dev/null || true)
        if [[ "$slot_name" == "'Clipboard History'" ]]; then
            gsettings reset "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${path_entry}" name
            gsettings reset "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${path_entry}" command
            gsettings reset "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${path_entry}" binding

            NEW_LIST=$(echo "$EXISTING" | sed "s|, '${path_entry}'||; s|'${path_entry}', ||; s|'${path_entry}'||")
            gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$NEW_LIST"
            info "Removed GNOME keybinding (Super+Shift+V)."
            break
        fi
    done
}

remove_wm_keybinding() {
    local config_file="$1"
    if [[ -f "$config_file" ]] && grep -qF "$COPYNINJA_MARKER" "$config_file" 2>/dev/null; then
        # Remove the marker line and the line after it
        sed -i "/$COPYNINJA_MARKER/{N;d;}" "$config_file"
        # Remove any trailing blank line left behind
        sed -i -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$config_file"
        info "Removed keybinding from $config_file"
    fi
}

case "$DESKTOP" in
    *GNOME*)
        remove_gnome_keybinding
        ;;
    *Hyprland*|*hyprland*)
        remove_wm_keybinding "$HOME/.config/hypr/hyprland.conf"
        ;;
    *sway*|*Sway*)
        remove_wm_keybinding "$HOME/.config/sway/config"
        ;;
    *i3*|*I3*)
        remove_wm_keybinding "$HOME/.config/i3/config"
        ;;
    *)
        warn "Could not auto-remove keybinding for '$DESKTOP'. Please remove the Super+Shift+V binding manually."
        ;;
esac

# Remove legacy GNOME extension (from older installs)
EXT_UUID="copyninja-clip@copyninja"
EXT_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
if [[ -d "$EXT_DIR" ]]; then
    gnome-extensions disable "$EXT_UUID" 2>/dev/null || true
    rm -rf "$EXT_DIR"
    info "Removed legacy GNOME Shell extension."
fi

# Remove legacy autostart entry
rm -f "$HOME/.config/autostart/copyninja-enable.desktop"

# Remove clipboard history
read -rp "  Delete clipboard history (~/.clipboard_history.json)? [y/N] " del_data
if [[ "$del_data" =~ ^[Yy]$ ]]; then
    rm -f "$HOME/.clipboard_history.json"
    info "Removed history file."
fi

echo ""
info "CopyNinja has been uninstalled."
echo ""
