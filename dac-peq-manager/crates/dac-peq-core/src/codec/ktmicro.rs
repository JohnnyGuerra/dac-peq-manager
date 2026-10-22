use crate::codec::safety::assert_safe_for_hardware_flash;
use crate::error::{DacError, Result};
use crate::models::{BiquadBand, PeqPreset};

pub const RPT_ID: u8 = 0x4B;
pub const RPT_LEN: usize = 11;

pub const CMD_READ: u8 = 0x52;   // 'R'
pub const CMD_WRITE: u8 = 0x57;  // 'W'
pub const CMD_CLEAR: u8 = 0x43;  // 'C' - Factory reset
pub const CMD_COMMIT: u8 = 0x53; // 'S' - NVRAM flash commit

pub const REG_DAC_EQ_EN: u8 = 0x24;
pub const REG_BAND_BASE: u8 = 0x26;
pub const REG_PREAMP: u8 = 0x66;
pub const REG_FILTER: u8 = 0x11;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KtReport([u8; RPT_LEN]);

impl KtReport {
    pub fn new(bytes: [u8; RPT_LEN]) -> Self {
        Self(bytes)
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.0
    }

    pub fn into_bytes(self) -> [u8; RPT_LEN] {
        self.0
    }
}

/// Encode a register write packet: [0x4B, addr, 0, 0, 0, 0x57, 0, b0, b1, b2, b3]
pub fn encode_write_register(addr: u8, val_bytes: [u8; 4]) -> KtReport {
    let mut pkt = [0u8; RPT_LEN];
    pkt[0] = RPT_ID;
    pkt[1] = addr;
    pkt[2] = 0x00;
    pkt[3] = 0x00;
    pkt[4] = 0x00;
    pkt[5] = CMD_WRITE;
    pkt[6] = 0x00;
    pkt[7] = val_bytes[0];
    pkt[8] = val_bytes[1];
    pkt[9] = val_bytes[2];
    pkt[10] = val_bytes[3];
    KtReport(pkt)
}

/// Encode a register read packet: [0x4B, addr, 0, 0, 0, 0x52, 0, 0, 0, 0, 0]
pub fn encode_read_register(addr: u8) -> KtReport {
    let mut pkt = [0u8; RPT_LEN];
    pkt[0] = RPT_ID;
    pkt[1] = addr;
    pkt[2] = 0x00;
    pkt[3] = 0x00;
    pkt[4] = 0x00;
    pkt[5] = CMD_READ;
    KtReport(pkt)
}

/// Encode factory reset command (0x43 CLEAR).
pub fn encode_factory_reset() -> KtReport {
    let mut pkt = [0u8; RPT_LEN];
    pkt[0] = RPT_ID;
    pkt[5] = CMD_CLEAR;
    KtReport(pkt)
}

/// Encode NVRAM flash commit command (0x53 COMMIT).
pub fn encode_nvram_commit() -> KtReport {
    let mut pkt = [0u8; RPT_LEN];
    pkt[0] = RPT_ID;
    pkt[5] = CMD_COMMIT;
    KtReport(pkt)
}

/// Encode a single PEQ band into its two 11-byte reports (Freq/Gain and Q/Type).
pub fn encode_biquad_band(
    band_index: usize,
    band: &BiquadBand,
    compensate_2x: bool,
) -> Result<(KtReport, KtReport)> {
    if !(1..=5).contains(&band_index) {
        return Err(DacError::InvalidFilter(format!(
            "KTMicro KT02H20 hardware is limited to 5 bands (requested band {band_index})"
        )));
    }

    let reg_a = REG_BAND_BASE + ((band_index - 1) * 2) as u8;
    let reg_b = reg_a + 1;

    // Center frequency (halved if 2X divisor quirk applies)
    let eff_freq = if compensate_2x {
        (band.freq / 2.0).round() as u16
    } else {
        band.freq.round() as u16
    };

    // Gain in tenths of a dB (signed 16-bit)
    let gain_tenth = (band.gain * 10.0).round() as i16;
    let freq_bytes = eff_freq.to_le_bytes();
    let gain_bytes = gain_tenth.to_le_bytes();

    // Register A: [gain_lo, gain_hi, freq_lo, freq_hi]
    let val_a = [gain_bytes[0], gain_bytes[1], freq_bytes[0], freq_bytes[1]];
    let rpt_a = encode_write_register(reg_a, val_a);

    // Q factor times 1000 (unsigned 16-bit)
    let q_1000 = (band.q * 1000.0).round() as u16;
    let q_bytes = q_1000.to_le_bytes();
    let type_id = band.filter_type.to_ktmicro_id();

    // Register B: [q_lo, q_hi, type_id, 0x00]
    let val_b = [q_bytes[0], q_bytes[1], type_id, 0x00];
    let rpt_b = encode_write_register(reg_b, val_b);

    Ok((rpt_a, rpt_b))
}

/// Encode complete flash payload sequence for KTMicro KT02H20.
/// Guardrail: If device is Kiwi Ears Allegro Mini (0x31B2:0x0111), registers 0x11 and 0x66
/// are strictly omitted to prevent iOS/YouTube Music volume control lockouts!
pub fn encode_preset_payload(
    preset: &PeqPreset,
    vid: u16,
    pid: u16,
    slot_id: u8,
    compensate_2x: bool,
    commit_nvram: bool,
) -> Result<Vec<KtReport>> {
    assert_safe_for_hardware_flash(vid, pid, None)?;

    let is_allegro_mini = vid == 0x31B2 && pid == 0x0111;
    let mut reports = Vec::new();

    // 1. Digital preamp (Register 0x66) - Omitted on Allegro Mini to prevent volume lockout
    if !is_allegro_mini && preset.preamp.abs() > 0.01 {
        let gain_byte = (preset.preamp * 2.0).round() as i8 as u8;
        reports.push(encode_write_register(REG_PREAMP, [gain_byte, 0x00, 0x00, 0x00]));
    }

    // 2. Encode up to 5 bands (Bands 1 to 5)
    for i in 0..5 {
        let dummy = BiquadBand::new(crate::models::FilterType::Peaking, 1000.0, 0.0, 1.0);
        let band = preset.bands.get(i).unwrap_or(&dummy);
        let (rpt_a, rpt_b) = encode_biquad_band(i + 1, band, compensate_2x)?;
        reports.push(rpt_a);
        reports.push(rpt_b);
    }

    // 3. Select PEQ Slot (Register 0x24)
    reports.push(encode_write_register(REG_DAC_EQ_EN, [slot_id, 0x00, 0x00, 0x00]));

    // 4. Commit to NVRAM flash if requested (0x53 COMMIT)
    if commit_nvram {
        reports.push(encode_nvram_commit());
    }

    Ok(reports)
}
