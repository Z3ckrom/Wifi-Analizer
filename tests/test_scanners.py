from wifi_analyzer.scanners import LinuxScanner, WindowsScanner


WINDOWS_OUTPUT = r"""
SSID 1 : Office
    Authentication : WPA2-Personal
    BSSID 1 : aa:bb:cc:dd:ee:ff
         Signal : 82%
         Channel : 6
         Channel width : 20
"""


def test_windows_parser():
    networks = WindowsScanner._parse(WINDOWS_OUTPUT, "2.4")
    assert len(networks) == 1
    network = networks[0]
    assert network.ssid == "Office"
    assert network.bssid == "AA:BB:CC:DD:EE:FF"
    assert network.channel == 6
    assert network.rssi == -59.0
    assert network.signal_percent == 82.0
    assert network.security == "WPA2-Personal"


def test_windows_target_parser_filters_other_bssids():
    assert WindowsScanner._parse(WINDOWS_OUTPUT, "2.4", "11:22:33:44:55:66") == []


def test_nmcli_escape_splitter():
    assert LinuxScanner._split_nmcli(r"Cafe\:Guest:AA\:BB\:CC\:DD\:EE\:FF:6:70:2437:WPA2") == [
        "Cafe:Guest",
        "AA:BB:CC:DD:EE:FF",
        "6",
        "70",
        "2437",
        "WPA2",
    ]
