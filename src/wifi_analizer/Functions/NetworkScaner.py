import subprocess, re, random, pywifi,time
# -------------------------
# Wi-Fi Scanning (Windows)
# -------------------------
def freq_to_channel(freq):
    freq = int(freq)
    if 2412 <= freq <= 2472:
        return (freq - 2407)//5
    if freq == 2484:
        return 14
    if 5000 <= freq <= 6000:
        return (freq - 5000)//5
    return None


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
    # time.sleep(3)
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

# -------------------------
# Wi-Fi Scanning (Linux)
# -------------------------
# def scan_wifi_linux():
#     if not wifi_iface:
#         return []
#     try:
#         result = subprocess.check_output(['sudo','iw','dev',wifi_iface,'scan'], text=True)
#     except Exception:
#         return []

#     networks=[]
#     band=band_var.get()

#     for cell in result.split('BSS '):
#         s=re.search(r'SSID: (.*)',cell)
#         f=re.search(r'freq: (\d+)',cell)
#         p=re.search(r'signal: (-?\d+\.?\d*) dBm',cell)
#         if not (s and f and p):
#             continue

#         ssid=s.group(1).strip() or '<hidden>'
#         ch=freq_to_channel(int(f.group(1)))
#         rssi=float(p.group(1))

#         if band == '2.4' and not (1 <= (ch or 0) <= 14):
#             continue
#         if band == '5' and (ch is None or ch < 30):
#             continue

#         networks.append((ssid,ch,rssi,get_color(ssid),20))

#     return networks