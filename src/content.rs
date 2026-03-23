use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Clipboard content type — text or image.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ClipContent {
    Text {
        text: String,
        preview: String,
    },
    Image {
        /// Path to the full image file
        path: PathBuf,
        /// MIME type (e.g. "image/png")
        mime: String,
    },
}

impl ClipContent {
    /// Get a display preview string for this content.
    pub fn preview(&self) -> &str {
        match self {
            ClipContent::Text { preview, .. } => preview,
            ClipContent::Image { mime, .. } => mime,
        }
    }

    /// Check if this is a text entry.
    pub fn is_text(&self) -> bool {
        matches!(self, ClipContent::Text { .. })
    }

    /// Get the text content if this is a text entry.
    pub fn text(&self) -> Option<&str> {
        match self {
            ClipContent::Text { text, .. } => Some(text),
            ClipContent::Image { .. } => None,
        }
    }

}
