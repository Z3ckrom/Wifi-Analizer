# Wi-Fi Analyzer + AP Hunter


## Install

Python 3.10 or newer is recommended.

```bash
python -m pip install -r requirements_wifi_analyzer.txt
```

Tkinter is included with normal Windows Python installations. On Debian/Ubuntu Linux, install it and the scan tools if needed:

```bash
sudo apt install python3-tk iw network-manager
```

## Run

```bash
python wifi_analyzer_ap_hunter.py
```

To select a specific Linux adapter:

```bash
python wifi_analyzer_ap_hunter.py --interface wlan1
```

## Use AP Hunter

1. Scan the applicable band.
2. Open **AP Hunter**.
3. Select the SSID.
4. Select the target BSSID/radio. This is important because multiple radios can advertise the same SSID.
5. Select **Start tracking** and move slowly while watching the smoothed value, trend and gauge.
6. Use **Reset peak/history** after changing location or direction.

You can also double-click a row in the Channel Analyzer table to preselect that radio in AP Hunter.

## Linux permissions

An active scan through `iw` generally requires root or `CAP_NET_ADMIN`. The app intentionally does not put `sudo` inside a GUI subprocess because that can hang while waiting for a password. Grant the account/process the appropriate permission, run in an authorized elevated environment, or let the app use the NetworkManager (`nmcli`) fallback.

## Important limitations

- RSSI is a relative proximity indicator, not a reliable physical distance. Walls, reflections, people, client orientation, AP transmit power and antenna patterns all change readings.
- This feature locates a selected AP; it does not prove that the AP is rogue. Rogue classification requires an approved inventory and additional checks.
- Windows `netsh` output parsing expects the standard English field labels (`SSID`, `BSSID`, `Signal`, `Channel`, and `Authentication`).
- Scan cadence is constrained by the operating system and Wi-Fi adapter. The tracker requests a scan about every 1.2 seconds, but some drivers update less frequently.
- Use only on networks and at locations where you are authorized to scan.
