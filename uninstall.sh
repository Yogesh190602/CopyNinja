#!/usr/bin/env bash
# uninstall.sh — Remove cliphist-x11 from the system
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "  This will completely remove cliphist-x11 from your system."
echo ""
read -rp "  Continue? [y/N] " answer
[[ "$answer" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# Stop and disable the systemd service
if systemctl --user is-active cliphist.service &>/dev/null; then
    systemctl --user stop cliphist.service
    info "Stopped cliphist service."
fi

if systemctl --user is-enabled cliphist.service &>/dev/null; then
    systemctl --user disable cliphist.service
    info "Disabled cliphist service."
fi

rm -f "$HOME/.config/systemd/user/cliphist.service"
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
info "cliphist-x11 has been uninstalled."
echo ""
