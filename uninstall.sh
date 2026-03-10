#!/usr/bin/env bash
# uninstall.sh — Remove copyninja from the system
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "  This will completely remove copyninja from your system."
echo ""
read -rp "  Continue? [y/N] " answer
[[ "$answer" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# Disable and remove the GNOME Shell extension
EXT_UUID="copyninja-clip@copyninja"
if gnome-extensions disable "$EXT_UUID" 2>/dev/null; then
    info "Disabled GNOME Shell extension."
fi
rm -rf "$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
info "Removed GNOME Shell extension."

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

# Remove GNOME keybinding
if command -v gsettings &>/dev/null; then
    CUSTOM_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
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
fi

# Remove clipboard history
read -rp "  Delete clipboard history (~/.clipboard_history.json)? [y/N] " del_data
if [[ "$del_data" =~ ^[Yy]$ ]]; then
    rm -f "$HOME/.clipboard_history.json"
    info "Removed history file."
fi

echo ""
info "copyninja has been uninstalled."
echo ""
