use dac_peq_core::*;

#[test]
fn test_rbj_biquad_peaking_response() {
    let filt = calculate_rbj_biquad(FilterType::Peaking, 1000.0, 6.0, 1.414, 48000.0);
    // At center frequency (1000 Hz), response should be exactly +6.0 dB
    let resp_center = filt.response_at(1000.0);
    assert!((resp_center - 6.0).abs() < 1e-4);

    // Far from center frequency (e.g. 50 Hz), response should be close to 0 dB
    let resp_low = filt.response_at(50.0);
    assert!(resp_low.abs() < 0.2);
}

#[test]
fn test_rbj_low_shelf_response() {
    let filt = calculate_rbj_biquad(FilterType::LowShelf, 100.0, 4.0, 0.71, 48000.0);
    // At deep sub-bass (20 Hz), low shelf should provide ~+4.0 dB
    let resp_20 = filt.response_at(20.0);
    assert!((resp_20 - 4.0).abs() < 0.2);

    // Above shelf frequency (e.g. 5 kHz), gain should be near 0 dB
    let resp_high = filt.response_at(5000.0);
    assert!(resp_high.abs() < 0.1);
}

#[test]
fn test_preset_deserialization_and_preamp() {
    let json_data = r#"{
        "name": "Test Preset",
        "preamp": -2.5,
        "bands": [
            {"type": "PK", "freq": 1000.0, "gain": 3.0, "q": 1.0},
            {"type": "LSQ", "freq": 100.0, "gain": 2.0, "q": 0.71}
        ]
    }"#;

    let preset: PeqPreset = serde_json::from_str(json_data).expect("Failed to parse preset");
    assert_eq!(preset.name, "Test Preset");
    assert_eq!(preset.preamp, -2.5);
    assert_eq!(preset.bands.len(), 2);
    assert_eq!(preset.bands[0].filter_type, FilterType::Peaking);
    assert_eq!(preset.bands[1].filter_type, FilterType::LowShelf);

    let rec_preamp = calculate_recommended_preamp(&preset.bands, 0.5, 48000.0);
    assert!(rec_preamp <= -3.0);
}

#[test]
fn test_coordinate_descent_decimation() {
    // 10 bands down to 5 bands
    let mut bands = Vec::new();
    for i in 1..=10 {
        bands.push(BiquadBand::new(
            FilterType::Peaking,
            100.0 * i as f64,
            (i as f64 * 0.5) - 2.0,
            1.0,
        ));
    }

    let decimated = decimate_bands(&bands, 5, true, 48000.0);
    assert_eq!(decimated.len(), 5);

    let diff = calculate_curve_difference(&bands, 0.0, &decimated, 0.0, 48000.0, 100);
    assert!(diff.rms_db < 3.0);
}

#[test]
fn test_cx31993_safety_guard_blocks_flashing() {
    let preset = PeqPreset {
        name: "Test".into(),
        description: None,
        preamp: 0.0,
        slot_id: Some(3),
        bands: vec![BiquadBand::new(FilterType::Peaking, 1000.0, 1.0, 1.0)],
        full_bands: None,
    };

    // Attempting to encode KTMicro flash payload for Conexant VID 0x0572 must fail!
    let res = encode_preset_payload(&preset, CONEXANT_VID, CONEXANT_PID, 3, false, true);
    assert!(res.is_err());
    match res {
        Err(DacError::SafetyGuard(msg)) => {
            assert!(msg.contains("Conexant CX31993"));
            assert!(msg.contains("fixed mask ROM"));
        }
        _ => panic!("Expected SafetyGuard error"),
    }
}

#[test]
fn test_allegro_mini_guardrail_omits_preamp_register_0x66() {
    let preset = PeqPreset {
        name: "Allegro Test".into(),
        description: None,
        preamp: -3.0, // Non-zero preamp
        slot_id: Some(3),
        bands: vec![BiquadBand::new(FilterType::Peaking, 1000.0, 1.0, 1.0)],
        full_bands: None,
    };

    // For Kiwi Ears Allegro Mini (0x31B2:0x0111), register 0x66 must NOT be emitted
    let reports = encode_preset_payload(&preset, 0x31B2, 0x0111, 3, true, true)
        .expect("Payload generation failed");

    // Check that no packet targets address 0x66
    for r in &reports {
        let bytes = r.as_bytes();
        assert_ne!(bytes[1], REG_PREAMP, "Register 0x66 write detected on Allegro Mini!");
        assert_ne!(bytes[1], REG_FILTER, "Register 0x11 write detected on Allegro Mini!");
    }

    // Last report must be 0x53 COMMIT
    let last = reports.last().unwrap().as_bytes();
    assert_eq!(last[0], RPT_ID);
    assert_eq!(last[5], CMD_COMMIT);
}

#[test]
fn test_exporters_pipewire_and_apo() {
    let preset = PeqPreset {
        name: "BASN Test".into(),
        description: Some("Test bass tune".into()),
        preamp: -2.0,
        slot_id: Some(3),
        bands: vec![
            BiquadBand::new(FilterType::LowShelf, 50.0, 2.5, 0.71),
            BiquadBand::new(FilterType::Peaking, 2200.0, 1.5, 1.3),
        ],
        full_bands: None,
    };

    let pw = format_pipewire_filter_chain(&preset, DEFAULT_CX31993_SINK)
        .expect("PipeWire format failed");
    assert!(pw.contains("libpipewire-module-filter-chain"));
    assert!(pw.contains("eq_band1_fl"));
    assert!(pw.contains("bq_lowshelf"));
    assert!(pw.contains("preamp_fl"));

    let apo = format_equalizer_apo(&preset);
    assert!(apo.contains("Preamp: -2.0 dB"));
    assert!(apo.contains("Filter 1: ON LSC Fc 50.0 Hz Gain +2.5 dB Q 0.71"));

    let wav = format_wavelet_graphiceq(&preset);
    assert!(wav.starts_with("GraphicEQ: 20.0 "));
}
