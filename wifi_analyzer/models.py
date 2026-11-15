"""Core data models shared by scanners and the user interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Network:
    ssid: str
    bssid: str
    channel: int
    rssi: float
    width: int = 20
    security: str = "Unknown"
    # Windows and nmcli report quality percent rather than true RSSI. Preserve it
    # so the Hunter can use the native measurement without pretending it is dBm.
    signal_percent: Optional[float] = None
    @property
    def band(self) -> str:
        return "2.4" if 1 <= self.channel <= 14 else "5"
@dataclass
class ScanResult:
    networks: list[Network]
    status: str = ""
    error: str = ""
