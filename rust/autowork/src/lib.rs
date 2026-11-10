//! Offline foundation for the native-Octet application, not the installed runner.
pub mod execution;
pub mod planning;
pub mod runtime;
pub mod state;
pub mod task_store;

pub const ENGINE: &str = "native-Octet";
pub const ENGINE_REVISION: &str = "4d7a3e3ff83b300a57b20f9ac70cfa20cb3242ee";
pub const CONTRACT_VERSION: u32 = 1;

#[derive(Debug)]
pub struct Unavailable(pub &'static str);

impl std::fmt::Display for Unavailable {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} is unavailable (not implemented)", self.0)
    }
}

impl std::error::Error for Unavailable {}

impl From<std::io::Error> for Unavailable {
    fn from(_: std::io::Error) -> Self { Self("filesystem operation failed") }
}

impl From<task_store::StoreError> for Unavailable {
    fn from(_: task_store::StoreError) -> Self { Self("task-store operation failed") }
}

impl From<state::StateError> for Unavailable {
    fn from(_: state::StateError) -> Self { Self("journal operation failed") }
}

pub type Result<T> = std::result::Result<T, Unavailable>;
