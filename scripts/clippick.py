#!/usr/bin/env python3
"""
clippick.py - Windows 11-style clipboard history picker (Linux desktops)
Reads from JSON file and copies selected entry to clipboard.
"""

import sys
import os
import json
import time
import subprocess
import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib, Pango

DATA_FILE = Path.home() / ".clipboard_history.json"

CSS = """
/* ── Dark charcoal theme with blue accents ── */

window {
    background-color: #1e1e2e !important;
    font-family: "Inter", "Cantarell", sans-serif;
    font-size: 10pt;
    color: #cdd6f4;
}

/* ── Headerbar ── */
headerbar {
    background-color: #181825 !important;
    box-shadow: none;
    border-bottom: 1px solid #313244;
    min-height: 42px;
    padding: 0 14px;
}

.header-title {
    font-weight: 700;
    font-size: 13pt;
    color: #cdd6f4;
}

.entry-count {
    font-size: 8pt;
    font-weight: 600;
    color: #1e1e2e;
    background-color: #89b4fa;
    border-radius: 10px;
    padding: 1px 8px;
    margin-left: 8px;
    min-height: 16px;
}

/* ── Search ── */
.search-entry {
    border-radius: 20px;
    padding: 6px 16px;
    margin: 4px 0 6px 0;
    background-color: #313244 !important;
    border: 1.5px solid #45475a;
    min-height: 30px;
    font-size: 9.5pt;
    color: #cdd6f4 !important;
}

.search-entry:focus-within {
    border-color: #89b4fa;
    box-shadow: 0 0 0 2px rgba(137, 180, 250, 0.25);
    background-color: #313244 !important;
}

/* ── List ── */
list {
    background-color: transparent !important;
}

row {
    background-color: transparent !important;
    padding: 0;
    margin: 0;
    outline: none;
}

row:selected {
    background-color: transparent !important;
}

row:focus {
    outline: none;
    background-color: transparent !important;
}

/* ── Section headers ── */
.section-label {
    font-size: 8pt;
    font-weight: 700;
    color: #89b4fa;
    letter-spacing: 1px;
    padding: 10px 8px 4px 8px;
}

/* ── Clip cards ── */
.clip-card {
    background-color: #313244 !important;
    border-radius: 12px;
    padding: 10px 14px;
    margin: 2px 0;
    border: 1px solid #45475a;
    transition: all 150ms ease;
}

.clip-card:hover {
    background-color: #45475a !important;
    border-color: #585b70;
}

row:selected .clip-card {
    background-color: rgba(137, 180, 250, 0.15) !important;
    border-color: #89b4fa;
}

.clip-preview {
    color: #cdd6f4;
    font-size: 9.5pt;
}

.clip-time {
    font-size: 7.5pt;
    color: #6c7086;
    margin-top: 3px;
}

.pin-icon {
    opacity: 0.7;
    margin-right: 2px;
    min-width: 16px;
    color: #f9e2af;
}

.menu-btn {
    opacity: 0;
    min-width: 26px;
    min-height: 26px;
    padding: 0;
    border-radius: 8px;
    background: transparent !important;
    border: none;
    box-shadow: none;
    color: #bac2de;
    transition: opacity 150ms ease;
}

.menu-btn:hover {
    opacity: 1;
    background-color: rgba(205, 214, 244, 0.1) !important;
}

.clip-card:hover .menu-btn {
    opacity: 0.6;
}

row:selected .clip-card .menu-btn {
    opacity: 0.6;
}

/* ── Footer ── */
.footer-bar {
    border-top: 1px solid #313244;
    padding: 6px 4px;
    background-color: #181825 !important;
}

.clear-btn {
    color: #f38ba8;
    font-weight: 600;
    font-size: 9pt;
    background: transparent !important;
    border: none;
    box-shadow: none;
    padding: 4px 14px;
    border-radius: 8px;
    transition: all 150ms ease;
}

.clear-btn:hover {
    background-color: rgba(243, 139, 168, 0.12) !important;
}

.clear-btn-confirm {
    color: #1e1e2e !important;
    background-color: #f38ba8 !important;
    font-weight: 700;
}

.clear-btn-confirm:hover {
    background-color: #eba0ac !important;
}

/* ── Empty state ── */
.empty-box {
    padding: 60px 20px;
}

.empty-icon {
    opacity: 0.2;
    margin-bottom: 12px;
    color: #6c7086;
}

.empty-title {
    font-size: 11pt;
    font-weight: 600;
    color: #a6adc8;
    margin-bottom: 4px;
}

.empty-subtitle {
    font-size: 9pt;
    color: #6c7086;
}

/* ── Scrollbar ── */
scrollbar slider {
    background-color: rgba(205, 214, 244, 0.12);
    border-radius: 10px;
    min-width: 4px;
}

scrollbar slider:hover {
    background-color: rgba(205, 214, 244, 0.25);
}

scrollbar.overlay-indicator:not(.hovering) slider {
    min-width: 3px;
}

/* ── Keyboard hint ── */
.kbd-hint {
    font-size: 7.5pt;
    color: #585b70;
    padding: 0 4px;
}
"""


def _relative_time(timestamp):
    """Return human-readable relative time."""
    diff = time.time() - timestamp
    if diff < 60:
        return "just now"
    elif diff < 3600:
        m = int(diff / 60)
        return f"{m}m ago"
    elif diff < 86400:
        h = int(diff / 3600)
        return f"{h}h ago"
    else:
        d = int(diff / 86400)
        return f"{d}d ago"


class ClipPickApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.copyninja.picker")
        self.window = None
        self.listbox = None
        self.search_entry = None
        self.clear_btn = None
        self.count_label = None
        self._clear_confirm = False
        self._clear_timer_id = None
        self._ready = False

    def do_activate(self):
        self._install_css()
        self._setup_actions()

        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(380, 500)

        # Custom headerbar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(False)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        title_box.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label="Clipboard")
        title.add_css_class("header-title")
        title_box.append(title)

        self.count_label = Gtk.Label(label="0")
        self.count_label.add_css_class("entry-count")
        title_box.append(self.count_label)

        header.set_title_widget(title_box)
        self.window.set_titlebar(header)

        # Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Content area
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_top(8)
        content.set_margin_start(10)
        content.set_margin_end(10)

        # Search
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search clipboard…")
        self.search_entry.add_css_class("search-entry")
        self.search_entry.connect("search-changed", self._on_search_changed)
        content.append(self.search_entry)

        # Scrolled list
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_margin_top(2)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_filter_func(self._filter_func)
        self.listbox.connect("row-activated", self._on_row_activated)

        self._populate_list()

        scroller.set_child(self.listbox)
        content.append(scroller)
        vbox.append(content)

        # Footer
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        footer.add_css_class("footer-bar")
        footer.set_margin_start(10)
        footer.set_margin_end(10)
        footer.set_margin_bottom(6)

        kbd_hint = Gtk.Label(label="Esc close  ·  Enter copy  ·  Ctrl+P pin")
        kbd_hint.add_css_class("kbd-hint")
        kbd_hint.set_hexpand(True)
        kbd_hint.set_xalign(0)
        footer.append(kbd_hint)

        self.clear_btn = Gtk.Button(label="Clear all")
        self.clear_btn.add_css_class("clear-btn")
        self.clear_btn.add_css_class("flat")
        self.clear_btn.connect("clicked", self._on_clear_all)
        footer.append(self.clear_btn)

        vbox.append(footer)
        self.window.set_child(vbox)

        # Key controller
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.window.add_controller(key_ctrl)

        self.window.present()
        self.search_entry.grab_focus()

        # Enable focus-loss close after grace period
        GLib.timeout_add(500, self._enable_focus_close)

    def _install_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _setup_actions(self):
        toggle_pin = Gio.SimpleAction.new(
            "toggle-pin", GLib.VariantType.new("s")
        )
        toggle_pin.connect("activate", self._on_toggle_pin)
        self.add_action(toggle_pin)

        delete_entry = Gio.SimpleAction.new(
            "delete-entry", GLib.VariantType.new("s")
        )
        delete_entry.connect("activate", self._on_delete_entry)
        self.add_action(delete_entry)

    def _load_history(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_history(self, history):
        with open(DATA_FILE, "w") as f:
            json.dump(history, f)

    def _populate_list(self):
        # Clear existing rows
        while True:
            row = self.listbox.get_row_at_index(0)
            if row is None:
                break
            self.listbox.remove(row)

        history = self._load_history()

        pinned = [e for e in history if e.get("pinned")]
        unpinned = [e for e in history if not e.get("pinned")]
        total = len(history)

        # Update count badge
        if self.count_label:
            self.count_label.set_label(str(total))

        if not history:
            self._show_empty_state()
            return

        # Pinned section
        if pinned:
            self.listbox.append(self._build_section_header("PINNED"))
            for entry in pinned:
                self.listbox.append(self._build_row(entry))

        # Recent section
        if unpinned:
            label = "RECENT" if pinned else ""
            if label:
                self.listbox.append(self._build_section_header(label))
            for entry in unpinned:
                self.listbox.append(self._build_row(entry))

    def _show_empty_state(self):
        empty_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0
        )
        empty_box.add_css_class("empty-box")
        empty_box.set_halign(Gtk.Align.CENTER)
        empty_box.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("edit-paste-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("empty-icon")
        empty_box.append(icon)

        title = Gtk.Label(label="Nothing here yet")
        title.add_css_class("empty-title")
        empty_box.append(title)

        subtitle = Gtk.Label(label="Copy something to get started")
        subtitle.add_css_class("empty-subtitle")
        empty_box.append(subtitle)

        self.listbox.set_placeholder(empty_box)

    def _build_section_header(self, text):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        row._entry_hash = ""
        row._entry_text = ""
        row._entry_preview = ""
        row._is_header = True

        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.add_css_class("section-label")
        row.set_child(label)
        return row

    def _build_row(self, entry):
        row = Gtk.ListBoxRow()
        row._entry_hash = entry.get("hash", "")
        row._entry_text = entry.get("text", "")
        row._entry_preview = entry.get("preview", "")
        row._is_header = False

        # Card container
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.add_css_class("clip-card")

        # Pin icon
        if entry.get("pinned"):
            pin_icon = Gtk.Image.new_from_icon_name("view-pin-symbolic")
            pin_icon.set_pixel_size(14)
            pin_icon.add_css_class("pin-icon")
            pin_icon.set_valign(Gtk.Align.CENTER)
            card.append(pin_icon)

        # Text + time column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text_col.set_hexpand(True)

        preview = Gtk.Label(label=entry.get("preview", ""))
        preview.set_xalign(0)
        preview.set_ellipsize(Pango.EllipsizeMode.END)
        preview.set_max_width_chars(45)
        preview.set_lines(2)
        preview.set_wrap(True)
        preview.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        preview.add_css_class("clip-preview")
        text_col.append(preview)

        ts = entry.get("time")
        if ts:
            time_label = Gtk.Label(label=_relative_time(ts))
            time_label.set_xalign(0)
            time_label.add_css_class("clip-time")
            text_col.append(time_label)

        card.append(text_col)

        # Three-dot menu
        menu_btn = self._build_menu_button(entry)
        menu_btn.set_valign(Gtk.Align.CENTER)
        card.append(menu_btn)

        row.set_child(card)
        return row

    def _build_menu_button(self, entry):
        entry_hash = entry.get("hash", "")
        is_pinned = entry.get("pinned", False)

        menu = Gio.Menu()
        pin_label = "Unpin" if is_pinned else "Pin"
        menu.append(pin_label, f"app.toggle-pin('{entry_hash}')")
        menu.append("Delete", f"app.delete-entry('{entry_hash}')")

        popover = Gtk.PopoverMenu.new_from_model(menu)

        btn = Gtk.MenuButton()
        btn.set_icon_name("view-more-symbolic")
        btn.set_popover(popover)
        btn.add_css_class("menu-btn")
        btn.add_css_class("flat")
        return btn

    def _filter_func(self, row):
        if getattr(row, "_is_header", False):
            return True
        if self.search_entry is None:
            return True
        query = self.search_entry.get_text().lower().strip()
        if not query:
            return True
        preview = getattr(row, "_entry_preview", "")
        return query in preview.lower()

    def _on_search_changed(self, entry):
        self.listbox.invalidate_filter()

    def _on_row_activated(self, listbox, row):
        if getattr(row, "_is_header", False):
            return
        text = getattr(row, "_entry_text", "")
        if text:
            self._copy_to_clipboard(text)
            self.hold()
            self.window.set_visible(False)
            GLib.timeout_add(200, self._paste_and_quit)

    def _copy_to_clipboard(self, text):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)

    def _paste_and_quit(self):
        self._simulate_paste()
        GLib.timeout_add(300, self._do_quit)
        return False

    def _do_quit(self):
        self.quit()
        return False

    def _simulate_paste(self):
        """Simulate Ctrl+V to auto-paste into the focused window."""
        session = os.environ.get("XDG_SESSION_TYPE", "unknown")
        if session == "wayland" and shutil.which("wtype"):
            try:
                subprocess.Popen(
                    ["wtype", "-M", "ctrl", "-k", "v"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        elif session == "x11" and shutil.which("xdotool"):
            try:
                subprocess.Popen(
                    ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        return False

    def _on_key_pressed(self, controller, keyval, keycode, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK

        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            selected = self.listbox.get_selected_row()
            if selected and not getattr(selected, "_is_header", False):
                text = getattr(selected, "_entry_text", "")
                if text:
                    self._copy_to_clipboard(text)
                    self.hold()
                    self.window.set_visible(False)
                    GLib.timeout_add(200, self._paste_and_quit)
            return True

        if ctrl:
            if keyval in (Gdk.KEY_p, Gdk.KEY_P):
                selected = self.listbox.get_selected_row()
                if selected and not getattr(selected, "_is_header", False):
                    h = getattr(selected, "_entry_hash", "")
                    self.activate_action(
                        "toggle-pin", GLib.Variant.new_string(h)
                    )
                return True

            if keyval in (Gdk.KEY_d, Gdk.KEY_D):
                selected = self.listbox.get_selected_row()
                if selected and not getattr(selected, "_is_header", False):
                    h = getattr(selected, "_entry_hash", "")
                    self.activate_action(
                        "delete-entry", GLib.Variant.new_string(h)
                    )
                return True

            if keyval in (Gdk.KEY_l, Gdk.KEY_L):
                self._do_clear_all()
                return True

        return False

    def _enable_focus_close(self):
        self._ready = True
        self.window.connect("notify::is-active", self._on_active_changed)
        return False

    def _on_active_changed(self, window, pspec):
        if self._ready and not window.is_active():
            GLib.timeout_add(150, self._check_still_unfocused)

    def _check_still_unfocused(self):
        if self.window and not self.window.is_active():
            self.quit()
        return False

    def _on_toggle_pin(self, action, param):
        entry_hash = param.get_string()
        history = self._load_history()
        for entry in history:
            if entry.get("hash") == entry_hash:
                entry["pinned"] = not entry.get("pinned", False)
                break
        self._save_history(history)
        self._populate_list()

    def _on_delete_entry(self, action, param):
        entry_hash = param.get_string()
        history = self._load_history()
        history = [e for e in history if e.get("hash") != entry_hash]
        self._save_history(history)
        self._populate_list()

    def _on_clear_all(self, btn):
        if self._clear_confirm:
            self._do_clear_all()
        else:
            self._clear_confirm = True
            self.clear_btn.set_label("Confirm clear")
            self.clear_btn.add_css_class("clear-btn-confirm")
            if self._clear_timer_id:
                GLib.source_remove(self._clear_timer_id)
            self._clear_timer_id = GLib.timeout_add(
                3000, self._reset_clear_confirm
            )

    def _reset_clear_confirm(self):
        self._clear_confirm = False
        if self.clear_btn:
            self.clear_btn.set_label("Clear all")
            self.clear_btn.remove_css_class("clear-btn-confirm")
        self._clear_timer_id = None
        return False

    def _do_clear_all(self):
        history = self._load_history()
        pinned = [e for e in history if e.get("pinned")]
        self._save_history(pinned)
        self._populate_list()
        self._reset_clear_confirm()


app = ClipPickApp()
app.run(sys.argv)
