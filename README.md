# Wi-Fi Analyzer + AP Hunter

This is a behavior-preserving restructure of the attached 1,048-line `Source-Code.py` application.
The original single-file entry command remains available, while implementation details are grouped
by responsibility in the `wifi_analyzer` package.

## Requirements

- Python 3.9+
- Tkinter (usually installed through the operating system, such as `python3-tk` on Debian/Ubuntu)
- NumPy and Matplotlib
- Windows: `netsh` WLAN support
- Linux: `iw` and/or NetworkManager's `nmcli`

## Run without installing

```bash
python Source-Code.py
```

An explicit Linux interface can still be supplied:

```bash
python Source-Code.py --interface wlan1
```

The package form is also supported:

```bash
python -m wifi_analyzer --interface wlan1
```

## Install

```bash
python -m pip install -e .
wifi-analyzer
```

## Test

```bash
python -m pytest
```

