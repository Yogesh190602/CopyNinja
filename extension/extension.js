// SPDX-License-Identifier: GPL-2.0-or-later
// CopyNinja Clipboard Relay — GNOME Shell Extension (GNOME 45+)
// Listens for clipboard owner changes via Meta.Selection and relays
// text content to the CopyNinja daemon over D-Bus.

import St from 'gi://St';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const DBUS_NAME = 'com.copyninja.Daemon';
const DBUS_PATH = '/com/copyninja/Daemon';
const DBUS_IFACE = 'com.copyninja.Daemon';

export default class CopyNinjaExtension extends Extension {
    _selectionSignalId = null;

    enable() {
        const selection = global.get_display().get_selection();

        this._selectionSignalId = selection.connect('owner-changed', (_sel, selType, _source) => {
            if (selType !== Meta.SelectionType.SELECTION_CLIPBOARD)
                return;

            const clipboard = St.Clipboard.get_default();
            clipboard.get_text(St.ClipboardType.CLIPBOARD, (_cb, text) => {
                if (!text || text.trim().length === 0)
                    return;

                // Fire-and-forget D-Bus call to the daemon
                try {
                    const bus = Gio.bus_get_sync(Gio.BusType.SESSION, null);
                    bus.call(
                        DBUS_NAME,
                        DBUS_PATH,
                        DBUS_IFACE,
                        'NewEntry',
                        new GLib.Variant('(s)', [text]),
                        null,
                        Gio.DBusCallFlags.NO_AUTO_START,
                        -1,
                        null,
                        null,  // no callback — fire and forget
                    );
                } catch (e) {
                    // Daemon may not be running yet; silently ignore
                }
            });
        });
    }

    disable() {
        if (this._selectionSignalId !== null) {
            const selection = global.get_display().get_selection();
            selection.disconnect(this._selectionSignalId);
            this._selectionSignalId = null;
        }
    }
}
