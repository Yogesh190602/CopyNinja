mod app;
mod css;
pub(crate) mod paste;

use crate::config::Config;

pub fn run(config: &Config) {
    app::run(config);
}
