"""Signal-history and proximity calculations for AP Hunter."""

from __future__ import annotations

import time
from collections import deque
from typing import Optional

from .radio import normalize_bssid

class SignalTracker:
    def __init__(self, history_size: int = 12, alpha: float = 0.35):
        self.history_size = history_size
        self.alpha = alpha
        self.target_bssid: Optional[str] = None
        self.reset()
    def reset(self) -> None:
        self.samples: deque[float] = deque(maxlen=self.history_size)
        self.current: Optional[float] = None
        self.smoothed: Optional[float] = None
        self.proximity: Optional[float] = None
        self.peak: Optional[float] = None
        self.sample_count = 0
        self.started_at = time.monotonic()
        self.misses = 0
    def set_target(self, bssid: str) -> None:
        self.target_bssid = normalize_bssid(bssid)
        self.reset()
    def add(self, rssi: float, signal_percent: Optional[float] = None) -> float:
        value = float(rssi)
        raw_score = (
            max(0.0, min(100.0, float(signal_percent)))
            if signal_percent is not None
            else (max(-90.0, min(-30.0, value)) + 90.0) / 60.0 * 100.0
        )
        self.current = value
        self.smoothed = value if self.smoothed is None else self.alpha * value + (1 - self.alpha) * self.smoothed
        self.proximity = (
            raw_score
            if self.proximity is None
            else self.alpha * raw_score + (1 - self.alpha) * self.proximity
        )
        self.peak = value if self.peak is None else max(self.peak, value)
        self.samples.append(value)
        self.sample_count += 1
        self.misses = 0
        return self.score
    def miss(self) -> None:
        self.misses += 1
    @property
    def score(self) -> float:
        return self.proximity if self.proximity is not None else 0.0
    @property
    def average(self) -> Optional[float]:
        return sum(self.samples) / len(self.samples) if self.samples else None
    @property
    def trend(self) -> str:
        if len(self.samples) < 6:
            return "Scanning…"
        values = list(self.samples)
        half = len(values) // 2
        old_average = sum(values[:half]) / half
        new_average = sum(values[half:]) / (len(values) - half)
        delta = new_average - old_average
        if delta > 2.0:
            return "↑ Getting warmer"
        if delta < -2.0:
            return "↓ Getting colder"
        return "→ Steady"
    @property
    def elapsed(self) -> str:
        seconds = max(0, int(time.monotonic() - self.started_at))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
