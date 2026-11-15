"""Command-line entry point for Wi-Fi Analyzer."""

from __future__ import annotations

import argparse

from .scanners import make_scanner

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wi-Fi channel analyzer and RSSI AP Hunter")
    parser.add_argument("--interface", help="Linux Wi-Fi interface to scan (for example wlan1)")
    return parser.parse_args()
def main() -> None:
    """Parse arguments, construct the GUI, and start Tk's event loop."""
    args = parse_args()

    # Load GUI dependencies only after argument parsing so commands such as
    # ``--help`` remain usable on headless systems without Tk installed.
    import tkinter as tk

    from .app import WifiAnalyzerApp

    root = tk.Tk()
    WifiAnalyzerApp(root, make_scanner(interface=args.interface))
    root.mainloop()
