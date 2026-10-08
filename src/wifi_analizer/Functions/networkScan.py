import subprocess, re, random, pywifi
# -------------------------
# Wi-Fi Scanning (Windows)
# -------------------------
def scan_wifi_win(band_var: str):
    # A string that tells what band we are looking for.
    selected_band = band_var
    # An array of networks from the Selected wifi band the user put
    networks = []
    wifi = pywifi.PyWiFi()
    interface = wifi.interfaces()[0]
    # Force your wifi card to scan every time for latest
    interface.scan()
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            text=True, encoding="utf-8", errors="ignore")
    except Exception:
        return []
    
    # split into per-SSID blocks
    for block in re.split(r"\n(?=SSID \d+ :)", out):
        ssid_m = re.match(r"SSID \d+ : (.*)", block)
        if not ssid_m:
            continue
        ssid = ssid_m.group(1).strip() or "<hidden>"
        # each BSSID inside the SSID block
        for bss in re.split(r"\n\s*(?=BSSID \d+)", block)[1:]:
            sig = re.search(r"Signal\s*:\s*(\d+)%", bss)
            ch = re.search(r"Channel\s*:\s*(\d+)", bss)
            if not (sig and ch):
                continue
            ch = int(ch.group(1))
            dbm = int(sig.group(1)) / 2 - 100
            if selected_band == "2.4" and not (1 <= ch <= 14):
                continue
            if selected_band == "5" and ch < 30:
                continue
            color = "#" + "".join(random.choices("0123456789ABCDEF", k=6))
            networks.append((ssid, ch, dbm, color, 20))
    return networks