use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum DacError {
    #[error("Safety Guard Violation: {0}")]
    SafetyGuard(String),

    #[error("Invalid Filter: {0}")]
    InvalidFilter(String),

    #[error("Serialization Error: {0}")]
    Serialization(String),

    #[error("Device Communication Error: {0}")]
    Communication(String),
}

pub type Result<T> = std::result::Result<T, DacError>;
