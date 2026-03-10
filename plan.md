# Plan: Windows-like Clipboard History (Simple)

## What We Want

1. Copy text anywhere → automatically saved to `~/.clipboard_history.json`
2. Press **Win+Shift+V** in any input field → compact popup opens with history
3. Click any entry → it gets **pasted directly** into the input field (not just copied)
4. Escape or click outside → popup closes

## Current State

- `clipdaemon.py` — polls `wl-paste` every 2s, saves to JSON. Works but wasteful.
- `clippick.py` — GTK4 picker with dark Catppuccin Mocha theme. Uses native `Gdk.Clipboard.set()` (no wl-copy).
- `install.sh` — installs scripts, systemd service, GNOME keybinding. Works.
- `uninstall.sh` — removes everything. Works.
- JSON file at `~/.clipboard_history.json` — already in place, no DB.

## What Needs to Change

### 1. `clipdaemon.py` — Use `wl-paste --watch` instead of polling

**Why:** Polling every 2s wastes CPU and misses fast copies. `wl-paste --watch` triggers instantly on clipboard change.

**Change:**
- Replace the `while True: sleep(2)` poll loop with `wl-paste --watch cat` subprocess
- Read stdout line-by-line, each line = new clipboard content
- Rest stays the same (hash, dedup, save to JSON)

### 2. `clippick.py` — Auto-paste + cleaner UI

**Auto-paste (the key feature):**
- After `Gdk.Clipboard.set(text)`, simulate **Ctrl+V** using `wtype` (Wayland keystroke tool)
- Flow: click entry → `clipboard.set(text)` → close window → small delay → `wtype -M ctrl -k v` → text pasted
- New dependency: `wtype` (Arch: `wtype` package)

**UI (already done):**
- Dark Catppuccin Mocha theme with blue accents
- Compact 380x500 flyout, custom headerbar with entry count badge
- Pill-shaped search bar, card rows with hover/selection effects
- Three-dot menu per row (Pin/Delete), section headers (PINNED/RECENT)
- Relative timestamps, 2-line preview, keyboard hints in footer
- Close on focus loss (500ms grace period + 150ms debounce)
- All keyboard shortcuts: Escape, Enter, Ctrl+P/D/L
- Native `Gdk.Clipboard.set()` — no wl-copy

### 3. `install.sh` — Add `wtype` + `wl-clipboard` dependency check

- Add `wtype` and `wl-clipboard` to dependency checks
- Auto-install via pacman if missing
- Rest stays the same

### 4. `uninstall.sh` — No changes needed

Already handles everything correctly.

## Files to Modify

| File | Change |
|------|--------|
| `scripts/clipdaemon.py` | Replace poll loop with `wl-paste --watch` |
| `scripts/clippick.py` | Add auto-paste via `wtype` |
| `install.sh` | Add `wtype` and `wl-clipboard` dependency checks |
| `uninstall.sh` | No changes |

## New Dependency

- `wtype` — Wayland keystroke simulator (for auto-paste Ctrl+V)
- `wl-clipboard` — already used (`wl-paste` for daemon)

## Flow After Changes

```
User copies text → wl-paste --watch fires → daemon saves to JSON
User presses Win+Shift+V → picker opens
User clicks entry → Gdk.Clipboard.set(text) → window closes → wtype sends Ctrl+V → text pasted
```

## Verification

1. Copy some text in any app
2. Open a text editor or browser input
3. Press Win+Shift+V — picker should appear
4. Click an entry — text should be pasted directly into the input field
5. Click outside the picker — it should close without pasting
6. Press Escape — should close without pasting
