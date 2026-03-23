pub mod dbus;
pub mod session;
pub mod wayland;
pub mod x11;

use log::{error, info, warn};
use session::SessionType;
use std::time::Duration;

pub fn run(config: &crate::config::Config) {
    // Start sync watcher if enabled
    crate::sync::start_watcher(config.sync.clone());

    let rt = tokio::runtime::Runtime::new().expect("Failed to create tokio runtime");
    rt.block_on(async {
        if let Err(e) = run_async().await {
            error!("Daemon fatal error: {}", e);
            std::process::exit(1);
        }
    });
}

async fn run_async() -> anyhow::Result<()> {
    info!("CopyNinja daemon starting");

    let _conn = dbus::setup().await?;
    info!("D-Bus service registered: com.copyninja.Daemon");

    // Retry loop: try to start clipboard watcher for up to 5 minutes
    const MAX_RETRIES: u32 = 60;
    for attempt in 0..MAX_RETRIES {
        let session = session::detect();
        info!(
            "Session type: {:?} (attempt {}/{})",
            session,
            attempt + 1,
            MAX_RETRIES
        );

        match session {
            SessionType::Wayland => {
                // Try native Wayland watcher first
                match wayland::start().await {
                    Ok(()) => return Ok(()),
                    Err(e) => {
                        warn!("Wayland watcher failed: {}", e);
                        // Fall back to X11 (XWayland) like GNOME Wayland
                        info!("Trying X11/XWayland fallback...");
                        match x11::start().await {
                            Ok(()) => return Ok(()),
                            Err(e) => warn!("X11 fallback failed: {}", e),
                        }
                    }
                }
            }
            SessionType::X11 => match x11::start().await {
                Ok(()) => return Ok(()),
                Err(e) => warn!("X11 watcher failed: {}", e),
            },
            SessionType::Unknown => {
                warn!("No graphical session detected yet");
            }
        }

        if attempt < MAX_RETRIES - 1 {
            info!("Retrying in 5 seconds...");
            tokio::time::sleep(Duration::from_secs(5)).await;
        }
    }

    anyhow::bail!("Failed to start clipboard watcher after {} attempts", MAX_RETRIES)
}
