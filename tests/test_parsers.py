from pathlib import Path

from prometheus_client import CollectorRegistry, Gauge

from exporter.app import (
    LabeledGaugeTracker,
    ModemClient,
    extract_devices,
    extract_eth_interface,
    extract_system_status,
    extract_voip_lines,
    extract_wan_status,
    extract_wifi_channels,
    extract_wifi_ssids,
    parse_objects,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return parse_objects((FIXTURES / name).read_text())


def test_extract_wan_status():
    status = extract_wan_status(load("info.xml"))
    assert status == {
        "connected": True,
        "uptime_seconds": 12345.0,
        "mac_address": "aa:bb:cc:00:11:22",
    }


def test_extract_system_status():
    status = extract_system_status(load("info.xml"))
    assert status == {
        "serial_number": "ZTETESTSERIAL0001",
        "firmware_version": "V1.0.0_TEST",
        "uptime_seconds": 99999.0,
    }


def test_extract_wifi_ssids():
    radios = extract_wifi_ssids(load("info.xml"))
    assert radios == [
        {"band": "2.4GHz", "ssid": "TestWiFi_2G", "enabled": True},
        {"band": "5GHz", "ssid": "TestWiFi_5G", "enabled": False},
    ]


def test_extract_voip_lines():
    lines = extract_voip_lines(load("info.xml"))
    assert lines == [
        {"line": "1", "registered": True},
        {"line": "2", "registered": False},
    ]


def test_extract_devices_lan():
    devices = extract_devices(load("lan.xml"), "lan")
    assert devices == [
        {
            "mac_address": "de:ad:be:ef:00:01",
            "hostname": "desktop-pc",
            "ip_address": "192.168.1.50",
            "connection_type": "lan",
            "active": True,
        },
        {
            "mac_address": "de:ad:be:ef:00:02",
            "hostname": "unknown",
            "ip_address": "192.168.1.51",
            "connection_type": "lan",
            "active": False,
        },
    ]


def test_extract_devices_wlan_ignores_radio_objects():
    devices = extract_devices(load("wlan.xml"), "wlan")
    assert len(devices) == 1
    assert devices[0]["mac_address"] == "de:ad:be:ef:00:03"
    assert devices[0]["connection_type"] == "wlan"


def test_extract_wifi_channels():
    channels = extract_wifi_channels(load("wlan.xml"))
    assert channels == [
        {"band": "2.4GHz", "channel": 6.0},
        {"band": "5GHz", "channel": 36.0},
    ]


def test_extract_eth_interface():
    eth = extract_eth_interface(load("eth.xml"))
    assert eth == {
        "link_speed_mbps": 1000.0,
        "up": True,
        "full_duplex": True,
        "bytes_received": 1000000.0,
        "bytes_sent": 500000.0,
        "packets_received": 5000.0,
        "packets_sent": 3000.0,
    }


def test_labeled_gauge_tracker_removes_stale_series():
    registry = CollectorRegistry()
    gauge = Gauge("test_device_active", "test", ["mac_address"], registry=registry)
    tracker = LabeledGaugeTracker(gauge, ["mac_address"])

    tracker.update([{"mac_address": "aa:aa:aa:aa:aa:aa", "value": 1}])
    assert registry.get_sample_value("test_device_active", {"mac_address": "aa:aa:aa:aa:aa:aa"}) == 1

    tracker.update([{"mac_address": "bb:bb:bb:bb:bb:bb", "value": 1}])
    assert registry.get_sample_value("test_device_active", {"mac_address": "bb:bb:bb:bb:bb:bb"}) == 1
    assert registry.get_sample_value("test_device_active", {"mac_address": "aa:aa:aa:aa:aa:aa"}) is None


def test_modem_client_init():
    client = ModemClient("192.168.1.1", "admin", "secret", timeout=15)
    assert client.host == "http://192.168.1.1"
    assert client.username == "admin"
    assert client.password == "secret"
    assert client.timeout == 15
    assert not client.is_logged_in
