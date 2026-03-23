use log::{debug, warn};
use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Duration;

/// Write text to the system clipboard synchronously using wl-copy or xclip.
/// Returns true if the clipboard was successfully set.
pub fn write_clipboard_sync(text: &str) -> bool {
    // Try wl-copy (Wayland) — blocks until compositor accepts
    if let Ok(mut child) = Command::new("wl-copy")
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    {
        if let Some(mut stdin) = child.stdin.take() {
            let _ = stdin.write_all(text.as_bytes());
            drop(stdin);
        }
        if let Ok(status) = child.wait() {
            if status.success() {
                debug!("Clipboard set via wl-copy (sync)");
                return true;
            }
        }
        debug!("wl-copy failed, trying xclip");
    } else {
        debug!("wl-copy not found, trying xclip");
    }

    // Fallback: xclip (X11/XWayland)
    if let Ok(mut child) = Command::new("xclip")
        .args(["-selection", "clipboard"])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    {
        if let Some(mut stdin) = child.stdin.take() {
            let _ = stdin.write_all(text.as_bytes());
            drop(stdin);
        }
        if let Ok(status) = child.wait() {
            if status.success() {
                debug!("Clipboard set via xclip (sync)");
                return true;
            }
        }
    }

    warn!("Both wl-copy and xclip failed to set clipboard");
    false
}

/// Write an image file to the system clipboard using wl-copy or xclip.
/// Returns true if the clipboard was successfully set.
pub fn write_image_clipboard_sync(path: &Path, mime: &str) -> bool {
    let data = match std::fs::read(path) {
        Ok(d) => d,
        Err(e) => {
            warn!("Failed to read image file {}: {}", path.display(), e);
            return false;
        }
    };

    // Try wl-copy with MIME type
    if let Ok(mut child) = Command::new("wl-copy")
        .args(["--type", mime])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    {
        if let Some(mut stdin) = child.stdin.take() {
            let _ = stdin.write_all(&data);
            drop(stdin);
        }
        if let Ok(status) = child.wait() {
            if status.success() {
                debug!("Image clipboard set via wl-copy ({})", mime);
                return true;
            }
        }
    }

    // Fallback: xclip with target type
    if let Ok(mut child) = Command::new("xclip")
        .args(["-selection", "clipboard", "-t", mime, "-i"])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    {
        if let Some(mut stdin) = child.stdin.take() {
            let _ = stdin.write_all(&data);
            drop(stdin);
        }
        if let Ok(status) = child.wait() {
            if status.success() {
                debug!("Image clipboard set via xclip ({})", mime);
                return true;
            }
        }
    }

    warn!("Failed to set image clipboard");
    false
}

/// Show a desktop notification when auto-paste is unavailable.
pub fn notify_copy_only() {
    let _ = Command::new("notify-send")
        .args(["-a", "CopyNinja", "Copied to clipboard", "Auto-paste unavailable"])
        .spawn();
}

/// Check if the focused window is a terminal emulator.
/// Terminals need Ctrl+Shift+V instead of Ctrl+V for paste.
fn is_terminal_focused() -> bool {
    // Try hyprctl (Hyprland)
    if let Ok(output) = Command::new("hyprctl")
        .args(["activewindow", "-j"])
        .output()
    {
        if output.status.success() {
            if let Ok(json) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                if let Some(class) = json.get("class").and_then(|v| v.as_str()) {
                    let result = is_terminal_class(class);
                    debug!("hyprctl detected class '{}', terminal={}", class, result);
                    return result;
                }
            }
        }
    }

    // Try xdotool (X11/XWayland)
    if let Ok(output) = Command::new("xdotool")
        .args(["getactivewindow", "getwindowclassname"])
        .output()
    {
        if output.status.success() {
            let class = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !class.is_empty() && !class.contains("null") {
                let result = is_terminal_class(&class);
                debug!("xdotool detected class '{}', terminal={}", class, result);
                return result;
            }
        }
    }

    // On GNOME Wayland, xdotool can't detect window class.
    // Default to true (Ctrl+Shift+V) since it works in both terminals
    // and GNOME apps (GNOME treats Ctrl+Shift+V as paste everywhere).
    if is_gnome_wayland() {
        debug!("GNOME Wayland: cannot detect window class, defaulting to Ctrl+Shift+V");
        return true;
    }

    debug!("Could not detect focused window class, assuming non-terminal");
    false
}

/// Check if a window class name belongs to a known terminal emulator.
fn is_terminal_class(class: &str) -> bool {
    let class = class.to_lowercase();

    const TERMINALS: &[&str] = &[
        "alacritty", "kitty", "foot", "wezterm", "ghostty",
        "konsole", "tilix", "terminator", "sakura",
        "guake", "yakuake", "tilda", "contour", "rio",
        "xterm", "urxvt", "rxvt", "st", "st-256color",
    ];

    if TERMINALS.iter().any(|t| class == *t) {
        return true;
    }

    // Catch variants like "gnome-terminal", "xfce4-terminal",
    // "org.gnome.Terminal", "org.kde.konsole", etc.
    class.contains("terminal") || class.contains("konsole")
}

/// Detect if we're running on GNOME Wayland.
/// On GNOME Wayland, xdotool triggers a "Remote Desktop" permission dialog
/// instead of actually pasting, so we must skip it entirely.
fn is_gnome_wayland() -> bool {
    let session = std::env::var("XDG_SESSION_TYPE").unwrap_or_default();
    let desktop = std::env::var("XDG_CURRENT_DESKTOP").unwrap_or_default();
    let result = session == "wayland" && desktop.to_lowercase().contains("gnome");
    if result {
        debug!("Detected GNOME Wayland — xdotool will be skipped");
    }
    result
}

/// Wait until the CopyNinja picker window no longer has focus.
/// Polls every 50ms via xdotool (works on XWayland under GNOME), gives up after ~1s.
fn wait_for_focus_loss() {
    for i in 0..20 {
        std::thread::sleep(Duration::from_millis(50));
        if let Ok(output) = Command::new("xdotool")
            .args(["getactivewindow", "getwindowclassname"])
            .output()
        {
            if output.status.success() {
                let class = String::from_utf8_lossy(&output.stdout).trim().to_lowercase();
                if !class.contains("copyninja") {
                    debug!("Focus left picker after {}ms (active: '{}')", (i + 1) * 50, class);
                    return;
                }
            } else {
                // xdotool failed (e.g. no XWayland window focused) — previous window likely has focus
                debug!("xdotool returned error, assuming focus moved away");
                return;
            }
        } else {
            // xdotool not available, fall back to fixed delay
            debug!("xdotool not found for focus polling, using fixed delay");
            std::thread::sleep(Duration::from_millis(200));
            return;
        }
    }
    debug!("Focus poll timed out after 1s, proceeding anyway");
}

/// Simulate paste in the previously focused window.
/// Fallback chain:
///   1. wtype Ctrl+V        — wlroots Wayland (Hyprland, Sway)
///   2. xdotool Ctrl+V      — X11 only (skipped on GNOME Wayland)
///   3. ydotool key Ctrl+V   — GNOME Wayland (instant paste via uinput)
///   4. ydotool type         — fallback (types text char-by-char via uinput)
///   5. copy-only notify     — total failure
/// Uses Ctrl+Shift+V for terminal emulators in steps 1-3.
pub fn simulate_paste(text: &str) {
    let terminal = is_terminal_focused();
    let gnome_wayland = is_gnome_wayland();
    if terminal {
        debug!("Terminal detected — will use Ctrl+Shift+V");
    }

    // 1. Try wtype (native Wayland — Hyprland, Sway, wlroots compositors)
    let wtype_args: &[&str] = if terminal {
        &["-M", "ctrl", "-M", "shift", "-k", "v"]
    } else {
        &["-M", "ctrl", "-k", "v"]
    };
    match Command::new("wtype").args(wtype_args).output() {
        Ok(output) if output.status.success() => {
            debug!("Auto-paste via wtype succeeded");
            return;
        }
        Ok(output) => {
            debug!("wtype failed (status {})", output.status);
        }
        Err(_) => {
            debug!("wtype not found");
        }
    }

    // 2. Try xdotool (X11 only) — skip on GNOME Wayland where it
    // triggers Remote Desktop dialog instead of pasting
    if !gnome_wayland {
        std::thread::sleep(Duration::from_millis(50));
        let _ = Command::new("xdotool")
            .args(["keyup", "super", "Super_L", "Super_R", "shift", "Shift_L", "Shift_R", "ctrl", "alt"])
            .output();
        std::thread::sleep(Duration::from_millis(50));
        let xdotool_key = if terminal { "ctrl+shift+v" } else { "ctrl+v" };
        match Command::new("xdotool")
            .args(["key", xdotool_key])
            .output()
        {
            Ok(output) if output.status.success() => {
                debug!("Auto-paste via xdotool succeeded");
                return;
            }
            Ok(output) => {
                debug!("xdotool failed (status {}), trying ydotool", output.status);
            }
            Err(_) => {
                debug!("xdotool not found, trying ydotool");
            }
        }
    }

    // For ydotool paths (3 & 4): wait until the previous window has focus,
    // then re-detect terminal (earlier detection ran before focus returned)
    wait_for_focus_loss();
    let terminal = is_terminal_focused();
    if terminal {
        debug!("Terminal detected after focus return — will use Ctrl+Shift+V");
    }

    // 3. ydotool key Ctrl+V (GNOME Wayland — instant paste from clipboard via uinput)
    // evdev keycodes: KEY_LEFTCTRL=29, KEY_LEFTSHIFT=42, KEY_V=47
    {
        let ydotool_key_args: &[&str] = if terminal {
            &["key", "29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]
        } else {
            &["key", "29:1", "47:1", "47:0", "29:0"]
        };
        match Command::new("ydotool").args(ydotool_key_args).output() {
            Ok(output) if output.status.success() => {
                debug!("Auto-paste via ydotool key succeeded");
                return;
            }
            Ok(output) => {
                debug!("ydotool key failed (status {}), trying ydotool type", output.status);
            }
            Err(_) => {
                debug!("ydotool not found");
            }
        }
    }

    // 4. ydotool type (fallback — types text char-by-char via uinput, zero delays)
    match Command::new("ydotool")
        .args(["type", "--key-delay", "0", "--key-hold", "0", "--file", "-"])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(mut child) => {
            if let Some(mut stdin) = child.stdin.take() {
                let _ = stdin.write_all(text.as_bytes());
                drop(stdin);
            }
            match child.wait() {
                Ok(status) if status.success() => {
                    debug!("Auto-paste via ydotool type succeeded");
                    return;
                }
                Ok(status) => {
                    warn!("ydotool type failed (status {})", status);
                }
                Err(e) => {
                    warn!("ydotool type wait failed ({})", e);
                }
            }
        }
        Err(_) => {
            debug!("ydotool not found");
        }
    }

    warn!("No paste tool available (wtype/xdotool/ydotool) — copied to clipboard only");
    notify_copy_only();
}
