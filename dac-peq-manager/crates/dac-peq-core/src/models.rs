use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::str::FromStr;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FilterType {
    Peaking,
    LowShelf,
    HighShelf,
    Bypass,
}

impl FilterType {
    pub fn as_str(&self) -> &'static str {
        match self {
            FilterType::Peaking => "PK",
            FilterType::LowShelf => "LSQ",
            FilterType::HighShelf => "HSQ",
            FilterType::Bypass => "BYPASS",
        }
    }

    pub fn to_ktmicro_id(&self) -> u8 {
        match self {
            FilterType::Peaking => 0,
            FilterType::LowShelf => 3,
            FilterType::HighShelf => 4,
            FilterType::Bypass => 0,
        }
    }
}

impl FromStr for FilterType {
    type Err = std::convert::Infallible;

    fn from_str(s: &str) -> std::result::Result<Self, Self::Err> {
        let clean = s.to_uppercase().replace(['-', ' '], "_");
        match clean.as_str() {
            "PK" | "PEAK" | "PEAKING" => Ok(FilterType::Peaking),
            "LSQ" | "LOW_SHELF" | "LOWSHELF" => Ok(FilterType::LowShelf),
            "HSQ" | "HIGH_SHELF" | "HIGHSHELF" => Ok(FilterType::HighShelf),
            _ => Ok(FilterType::Bypass),
        }
    }
}

impl Serialize for FilterType {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(self.as_str())
    }
}

impl<'de> Deserialize<'de> for FilterType {
    fn deserialize<D>(deserializer: D) -> std::result::Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        Ok(FilterType::from_str(&s).unwrap_or(FilterType::Peaking))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BiquadBand {
    #[serde(default)]
    pub index: Option<usize>,
    #[serde(rename = "type")]
    pub filter_type: FilterType,
    pub freq: f64,
    pub gain: f64,
    pub q: f64,
}

impl BiquadBand {
    pub fn new(filter_type: FilterType, freq: f64, gain: f64, q: f64) -> Self {
        Self {
            index: None,
            filter_type,
            freq,
            gain,
            q,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PeqPreset {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub preamp: f64,
    #[serde(default)]
    pub slot_id: Option<u8>,
    pub bands: Vec<BiquadBand>,
    #[serde(default)]
    pub full_bands: Option<Vec<BiquadBand>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CurveDifference {
    pub rms_db: f64,
    pub max_diff_db: f64,
    pub max_diff_freq: f64,
    pub pinna_rms_db: f64,
}
