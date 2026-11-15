"""Platform-specific Wi-Fi scanner implementations."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from typing import Optional

from .models import Network, ScanResult
from .radio import (
    deduplicate_networks,
    freq_to_channel,
    matches_band,
    normalize_bssid,
    signal_percent_to_dbm,
)

class BaseScanner:
    description = "Wi-Fi scanner"

    def scan(self, selected_band: str) -> ScanResult:
        raise NotImplementedError

    def scan_target(self, selected_band: str, target_bssid: str) -> ScanResult:
        """Return only a selected radio; subclasses may optimize parsing further."""
        target = normalize_bssid(target_bssid)
        result = self.scan(selected_band)
        result.networks = [network for network in result.networks if network.bssid == target]
        return result


class WindowsScanner(BaseScanner):
    description = "Windows WLAN (netsh)"

    @staticmethod
    def _run_netsh() -> tuple[Optional[subprocess.CompletedProcess[str]], str]:
        try:
            completed = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=20,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"Windows Wi-Fi scan failed: {exc}"
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            return None, detail or "netsh returned an error."
        return completed, ""

    @staticmethod
    def _parse(output: str, selected_band: str, target_bssid: Optional[str] = None) -> list[Network]:
        """Parse netsh once; target mode stops as soon as the selected BSSID is complete."""
        target = normalize_bssid(target_bssid) if target_bssid else None
        networks: list[Network] = []
        current_ssid = "<hidden>"
        current_security = "Unknown"
        current: dict[str, object] = {}

        def flush() -> bool:
            nonlocal current
            found_target = False
            if {"bssid", "signal", "channel"}.issubset(current):
                bssid = str(current["bssid"])
                channel = int(current["channel"])
                if (target is None or bssid == target) and matches_band(channel, selected_band):
                    quality = float(current["signal"])
                    networks.append(
                        Network(
                            ssid=current_ssid,
                            bssid=bssid,
                            channel=channel,
                            rssi=signal_percent_to_dbm(quality),
                            width=int(current.get("width", 20)),
                            security=current_security,
                            signal_percent=quality,
                        )
                    )
                    found_target = target is not None
            current = {}
            return found_target

        for raw_line in output.replace("\r", "").splitlines():
            line = raw_line.strip()
            match = re.match(r"SSID\s+\d+\s*:\s*(.*)$", line, re.IGNORECASE)
            if match:
                if flush():
                    break
                current_ssid = match.group(1).strip() or "<hidden>"
                current_security = "Unknown"
                continue
            match = re.match(r"Authentication\s*:\s*(.*)$", line, re.IGNORECASE)
            if match:
                current_security = match.group(1).strip() or "Unknown"
                continue
            match = re.match(r"BSSID\s+\d+\s*:\s*([0-9A-Fa-f:-]{17})", line, re.IGNORECASE)
            if match:
                if flush():
                    break
                current["bssid"] = normalize_bssid(match.group(1))
                continue
            match = re.match(r"Signal\s*:\s*(\d+)%", line, re.IGNORECASE)
            if match:
                current["signal"] = int(match.group(1))
                continue
            match = re.match(r"Channel\s*:\s*(\d+)", line, re.IGNORECASE)
            if match:
                current["channel"] = int(match.group(1))
                continue
            match = re.match(r"Channel width\s*:\s*(\d+)", line, re.IGNORECASE)
            if match:
                current["width"] = int(match.group(1))
        else:
            flush()
        return deduplicate_networks(networks)

    def scan(self, selected_band: str) -> ScanResult:
        completed, error = self._run_netsh()
        if completed is None:
            return ScanResult([], error=error)
        networks = self._parse(completed.stdout, selected_band)
        return ScanResult(networks, status=f"Found {len(networks)} access point radios.")

    def scan_target(self, selected_band: str, target_bssid: str) -> ScanResult:
        completed, error = self._run_netsh()
        if completed is None:
            return ScanResult([], error=error)
        networks = self._parse(completed.stdout, selected_band, target_bssid)
        return ScanResult(networks, status="Target sampled." if networks else "Target not seen.")


class LinuxScanner(BaseScanner):
    def __init__(self, interface: Optional[str] = None):
        self.interface = interface or self._find_interface()
        self.description = f"Linux Wi-Fi ({self.interface or 'no interface'})"
    @staticmethod
    def _find_interface() -> Optional[str]:
        if shutil.which("iw"):
            try:
                completed = subprocess.run(
                    ["iw", "dev"], capture_output=True, text=True, timeout=5, check=False
                )
                interfaces = re.findall(r"^\s*Interface\s+(\S+)", completed.stdout, re.MULTILINE)
                if interfaces:
                    for preferred in ("wlan1", "wlan0"):
                        if preferred in interfaces:
                            return preferred
                    return interfaces[0]
            except (OSError, subprocess.TimeoutExpired):
                pass
        if shutil.which("nmcli"):
            try:
                completed = subprocess.run(
                    ["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                for line in completed.stdout.splitlines():
                    if line.endswith(":wifi"):
                        return line.rsplit(":", 1)[0].replace("\\:", ":")
            except (OSError, subprocess.TimeoutExpired):
                pass
        return None
    def scan(self, selected_band: str) -> ScanResult:
        return self._scan(selected_band)

    def scan_target(self, selected_band: str, target_bssid: str) -> ScanResult:
        return self._scan(selected_band, normalize_bssid(target_bssid))

    def _scan(self, selected_band: str, target_bssid: Optional[str] = None) -> ScanResult:
        if not self.interface:
            return ScanResult([], error="No Linux Wi-Fi interface was detected.")
        iw_error = ""
        if shutil.which("iw"):
            result = self._scan_iw(selected_band, target_bssid)
            if result.networks:
                return result
            iw_error = result.error
        if shutil.which("nmcli"):
            result = self._scan_nmcli(selected_band, target_bssid)
            if result.networks or not result.error:
                return result
            if iw_error:
                result.error = f"{iw_error} | nmcli: {result.error}"
            return result
        return ScanResult(
            [],
            error=iw_error
            or "Neither 'iw' nor 'nmcli' is available. Install iw or NetworkManager.",
        )

    def _scan_iw(self, selected_band: str, target_bssid: Optional[str] = None) -> ScanResult:
        try:
            completed = subprocess.run(
                ["iw", "dev", self.interface, "scan"],
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ScanResult([], error=f"iw scan failed: {exc}")
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            hint = " Grant scan permission/CAP_NET_ADMIN or run the app with appropriate privileges."
            return ScanResult([], error=(detail or "iw scan returned an error.") + hint)
        networks: list[Network] = []
        for cell in re.split(r"(?m)^BSS\s+", completed.stdout)[1:]:
            bssid_match = re.match(r"([0-9A-Fa-f:]{17})", cell)
            ssid_match = re.search(r"(?m)^\s*SSID:\s*(.*)$", cell)
            freq_match = re.search(r"(?m)^\s*freq:\s*(\d+)", cell)
            signal_match = re.search(r"(?m)^\s*signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", cell)
            if not (bssid_match and freq_match and signal_match):
                continue
            bssid = normalize_bssid(bssid_match.group(1))
            if target_bssid and bssid != target_bssid:
                continue
            channel = freq_to_channel(int(freq_match.group(1)))
            if channel is None or not matches_band(channel, selected_band):
                continue
            width_match = re.search(r"(?:channel\s+)?width:\s*(\d+)\s*MHz", cell, re.IGNORECASE)
            security = "Open"
            if re.search(r"(?m)^\s*RSN:", cell):
                security = "WPA2/WPA3"
            elif re.search(r"(?m)^\s*WPA:", cell):
                security = "WPA"
            networks.append(
                Network(
                    ssid=(ssid_match.group(1).strip() if ssid_match else "") or "<hidden>",
                    bssid=bssid,
                    channel=channel,
                    rssi=float(signal_match.group(1)),
                    width=int(width_match.group(1)) if width_match else 20,
                    security=security,
                )
            )
        result = deduplicate_networks(networks)
        return ScanResult(result, status=f"Found {len(result)} access point radios.")
    @staticmethod
    def _split_nmcli(line: str) -> list[str]:
        fields: list[str] = []
        current: list[str] = []
        escaped = False
        for char in line:
            if escaped:
                current.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == ":":
                fields.append("".join(current))
                current = []
            else:
                current.append(char)
        fields.append("".join(current))
        return fields
    def _scan_nmcli(self, selected_band: str, target_bssid: Optional[str] = None) -> ScanResult:
        try:
            completed = subprocess.run(
                [
                    "nmcli",
                    "-t",
                    "--escape",
                    "yes",
                    "-f",
                    "SSID,BSSID,CHAN,SIGNAL,FREQ,SECURITY",
                    "device",
                    "wifi",
                    "list",
                    "ifname",
                    self.interface,
                    "--rescan",
                    "yes",
                ],
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ScanResult([], error=f"nmcli scan failed: {exc}")
        if completed.returncode != 0:
            return ScanResult([], error=completed.stderr.strip() or "nmcli returned an error.")
        networks: list[Network] = []
        for line in completed.stdout.splitlines():
            fields = self._split_nmcli(line)
            if len(fields) != 6:
                continue
            ssid, bssid_text, channel_text, signal_text, freq_text, security = fields
            try:
                bssid = normalize_bssid(bssid_text)
                if target_bssid and bssid != target_bssid:
                    continue
                channel = int(channel_text) if channel_text else freq_to_channel(int(freq_text))
                if channel is None or not matches_band(channel, selected_band):
                    continue
                networks.append(
                    Network(
                        ssid=ssid or "<hidden>",
                        bssid=bssid,
                        channel=channel,
                        rssi=signal_percent_to_dbm(float(signal_text)),
                        width=20,
                        security=security or "Open",
                        signal_percent=float(signal_text),
                    )
                )
            except ValueError:
                continue
        result = deduplicate_networks(networks)
        return ScanResult(result, status=f"Found {len(result)} access point radios.")
class UnsupportedScanner(BaseScanner):
    def __init__(self, system_name: str):
        self.description = f"Unsupported platform ({system_name})"
    def scan(self, selected_band: str) -> ScanResult:
        return ScanResult([], error=f"Wi-Fi scanning is not implemented for {platform.system()}.")
def make_scanner(interface: Optional[str] = None) -> BaseScanner:
    system = platform.system()
    if system == "Windows":
        return WindowsScanner()
    if system == "Linux":
        return LinuxScanner(interface)
    return UnsupportedScanner(system)
