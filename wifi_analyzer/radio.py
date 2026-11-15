"""Wi-Fi channel, signal, color, and de-duplication helpers."""

from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from .models import Network

def freq_to_channel(freq_mhz: int) -> Optional[int]:
    """Convert common 2.4/5/6 GHz center frequencies to channel numbers."""
    freq = int(freq_mhz)
    if 2412 <= freq <= 2472:
        return (freq - 2407) // 5
    if freq == 2484:
        return 14
    if 5000 <= freq <= 5895:
        return (freq - 5000) // 5
    if 5955 <= freq <= 7115:
        return (freq - 5950) // 5
    return None
def channel_band(channel: int) -> str:
    if 1 <= channel <= 14:
        return "2.4"
    if 30 <= channel <= 196:
        return "5"
    return "Other"
def matches_band(channel: int, selected_band: str) -> bool:
    return selected_band == "All" or channel_band(channel) == selected_band
def normalize_bssid(value: str) -> str:
    return value.strip().replace("-", ":").upper()
def signal_percent_to_dbm(percent: float) -> float:
    """Use the conventional Windows quality approximation: dBm = quality/2 - 100."""
    return max(-100.0, min(-30.0, float(percent) / 2.0 - 100.0))
def stable_color(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8", errors="ignore")).hexdigest()
    # Keep colors bright enough to remain visible on a black plot.
    r = 80 + int(digest[0:2], 16) * 175 // 255
    g = 80 + int(digest[2:4], 16) * 175 // 255
    b = 80 + int(digest[4:6], 16) * 175 // 255
    return f"#{r:02X}{g:02X}{b:02X}"
def deduplicate_networks(networks: Iterable[Network]) -> list[Network]:
    """Keep the strongest record for each BSSID and return a stable ordering."""
    by_bssid: dict[str, Network] = {}
    for network in networks:
        old = by_bssid.get(network.bssid)
        if old is None or network.rssi > old.rssi:
            by_bssid[network.bssid] = network
    return sorted(by_bssid.values(), key=lambda n: (n.ssid.casefold(), n.bssid))
