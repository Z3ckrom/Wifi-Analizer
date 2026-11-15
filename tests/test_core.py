from wifi_analyzer.models import Network
from wifi_analyzer.radio import (
    channel_band,
    deduplicate_networks,
    freq_to_channel,
    matches_band,
    normalize_bssid,
    signal_percent_to_dbm,
    stable_color,
)
from wifi_analyzer.tracker import SignalTracker


def test_frequency_to_channel_conversion():
    assert freq_to_channel(2412) == 1
    assert freq_to_channel(2472) == 13
    assert freq_to_channel(2484) == 14
    assert freq_to_channel(5180) == 36
    assert freq_to_channel(5955) == 1
    assert freq_to_channel(5935) is None


def test_band_helpers_preserve_existing_behavior():
    assert channel_band(1) == "2.4"
    assert channel_band(14) == "2.4"
    assert channel_band(36) == "5"
    assert channel_band(200) == "Other"
    assert matches_band(6, "2.4")
    assert matches_band(149, "5")
    assert matches_band(6, "All")


def test_signal_and_bssid_helpers():
    assert normalize_bssid("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"
    assert signal_percent_to_dbm(0) == -100.0
    assert signal_percent_to_dbm(100) == -50.0
    assert stable_color("AA:BB:CC:DD:EE:FF") == stable_color("AA:BB:CC:DD:EE:FF")


def test_deduplication_keeps_strongest_bssid_record():
    weak = Network("Office", "AA:BB:CC:DD:EE:FF", 1, -80)
    strong = Network("Office", "AA:BB:CC:DD:EE:FF", 1, -45)
    other = Network("Guest", "11:22:33:44:55:66", 6, -60)
    result = deduplicate_networks([weak, other, strong])
    assert len(result) == 2
    assert next(item for item in result if item.bssid == strong.bssid).rssi == -45


def test_signal_tracker_smoothing_and_trend():
    tracker = SignalTracker(history_size=12, alpha=0.35)
    tracker.set_target("aa-bb-cc-dd-ee-ff")
    for value in (-80, -79, -78, -65, -64, -63):
        tracker.add(value)
    assert tracker.target_bssid == "AA:BB:CC:DD:EE:FF"
    assert tracker.current == -63
    assert tracker.sample_count == 6
    assert tracker.trend == "↑ Getting warmer"
    assert tracker.average is not None
