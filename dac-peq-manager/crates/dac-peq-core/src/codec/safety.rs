use crate::error::{DacError, Result};

pub const CONEXANT_VID: u16 = 0x0572;
pub const CONEXANT_PID: u16 = 0x1B08;

pub const KNOWN_CONEXANT_DEVICES: &[(u16, u16)] = &[
    (0x0572, 0x1B08), // JCALLY JM6 / JM6 Pro
    (0x3302, 0x3365), // TTGK CX31993 384kHz HiFi Audio
];

/// Returns true if the device is a Conexant CX31993 fixed mask ROM DAC.
pub fn is_conexant_cx31993(vid: u16, pid: u16, product_name: Option<&str>) -> bool {
    if vid == CONEXANT_VID {
        return true;
    }
    for &(k_vid, k_pid) in KNOWN_CONEXANT_DEVICES {
        if vid == k_vid && pid == k_pid {
            return true;
        }
    }
    if let Some(name) = product_name {
        let lower = name.to_lowercase();
        if lower.contains("cx31993") || lower.contains("conexant") {
            return true;
        }
    }
    false
}

/// Safety guard to enforce that Conexant hardware cannot be flashed with KTMicro HID commands.
pub fn assert_safe_for_hardware_flash(vid: u16, pid: u16, product_name: Option<&str>) -> Result<()> {
    if is_conexant_cx31993(vid, pid, product_name) {
        return Err(DacError::SafetyGuard(format!(
            "Device 0x{:04X}:0x{:04X} is a Conexant CX31993 DAC with fixed mask ROM. \
            Attempting HID register writes will corrupt OTP descriptors. \
            Hardware flashing is strictly blocked. Use host-side DSP (PipeWire/Wavelet).",
            vid, pid
        )));
    }
    Ok(())
}
