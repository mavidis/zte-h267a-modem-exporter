import hashlib
import logging
import os
import signal
import time

import requests
from bs4 import BeautifulSoup
from prometheus_client import Counter, Gauge, start_http_server
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("modem_exporter")

# --- Prometheus Metrics Definitions ---
SCRAPE_SUCCESS = Gauge("modem_scrape_success", "1 if modem scrape was successful, 0 otherwise")
SCRAPE_DURATION = Gauge("modem_scrape_duration_seconds", "Total duration of the modem scrape cycle in seconds")
SCRAPE_ERRORS = Counter("modem_scrape_errors_total", "Total count of scrape errors by category", ["type"])

MODEM_INFO = Gauge(
    "modem_info",
    "Static modem identity, 1 for the active serial/firmware pair",
    ["serial_number", "firmware_version", "mac_address"],
)

WAN_CONNECTED = Gauge("modem_wan_connected", "1 if WAN connection is UP, 0 if DOWN")
WAN_UPTIME = Gauge("modem_wan_uptime_seconds", "WAN Connection Uptime in seconds")
SYSTEM_UPTIME = Gauge("modem_system_uptime_seconds", "Modem System Uptime in seconds")

DOWNSTREAM_SPEED = Gauge("modem_downstream_sync_speed_mbps", "Downstream Sync Rate in Mbps")
UPSTREAM_SPEED = Gauge("modem_upstream_sync_speed_mbps", "Upstream Sync Rate in Mbps")
WAN_LINK_UP = Gauge("modem_wan_link_up", "1 if the physical WAN Ethernet link is up, 0 otherwise")
WAN_LINK_FULL_DUPLEX = Gauge("modem_wan_link_full_duplex", "1 if the WAN Ethernet link is full duplex, 0 if half")
WAN_BYTES_RECEIVED = Gauge("modem_wan_bytes_received_total", "Total bytes received on the WAN interface")
WAN_BYTES_SENT = Gauge("modem_wan_bytes_sent_total", "Total bytes sent on the WAN interface")
WAN_PACKETS_RECEIVED = Gauge("modem_wan_packets_received_total", "Total packets received on the WAN interface")
WAN_PACKETS_SENT = Gauge("modem_wan_packets_sent_total", "Total packets sent on the WAN interface")

CONNECTED_DEVICES = Gauge("modem_connected_devices_count", "Number of active connected LAN/WLAN devices")
DEVICE_ACTIVE = Gauge(
    "modem_device_active",
    "1 if a known LAN/WLAN device is currently active, 0 otherwise",
    ["mac_address", "hostname", "ip_address", "connection_type"],
)

WIFI_RADIO_ENABLED = Gauge(
    "modem_wifi_radio_enabled", "1 if the WiFi radio is broadcasting, 0 otherwise", ["band", "ssid"]
)
WIFI_CHANNEL = Gauge("modem_wifi_channel", "Configured WiFi channel", ["band"])

VOIP_LINE_REGISTERED = Gauge(
    "modem_voip_line_registered", "1 if the VoIP line is registered with the provider", ["line"]
)


class LabeledGaugeTracker:
    """Keeps a labeled Gauge in sync with the rows of the latest scrape.

    prometheus_client never forgets a label combination on its own, so a
    device that disappears (or a firmware version that changes) would leave
    a stale time series behind forever. This removes whatever labels were
    present in the previous scrape but not the current one.
    """

    def __init__(self, gauge, label_names):
        self.gauge = gauge
        self.label_names = label_names
        self.previous_keys = set()

    def update(self, rows):
        current_keys = set()
        for row in rows:
            key = tuple(row[name] for name in self.label_names)
            current_keys.add(key)
            self.gauge.labels(*key).set(row["value"])
        for key in self.previous_keys - current_keys:
            self.gauge.remove(*key)
        self.previous_keys = current_keys


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_objects(html_text):
    """Parse the modem's flat <paraname>/<paravalue> XML into a list of dicts.

    Every object the modem reports starts with a `_InstID` field, so a new
    dict is opened each time one is seen and subsequent fields are attached
    to it until the next `_InstID`.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    objects = []
    current = None
    for paraname_tag in soup.find_all("paraname"):
        name = paraname_tag.text.strip()
        paravalue_tag = paraname_tag.find_next_sibling("paravalue")
        value = paravalue_tag.text.strip() if paravalue_tag else ""
        if name == "_InstID":
            current = {"_InstID": value}
            objects.append(current)
        elif current is not None:
            current[name] = value
    return objects


def extract_wan_status(objects):
    for obj in objects:
        if "ConnStatus" in obj:
            return {
                "connected": obj.get("ConnStatus", "").lower() == "connected",
                "uptime_seconds": _to_float(obj.get("UpTime")),
                "mac_address": obj.get("WorkIFMac", "").lower(),
            }
    return {}


def extract_system_status(objects):
    for obj in objects:
        if "SerialNumber" in obj:
            return {
                "serial_number": obj.get("SerialNumber", ""),
                "firmware_version": obj.get("Softwarever", ""),
                "uptime_seconds": _to_float(obj.get("Systemuptime")),
            }
    return {}


def extract_wifi_ssids(objects):
    radios = []
    for obj in objects:
        if "RadioStatus" in obj and "Band" in obj:
            radios.append(
                {
                    "band": obj.get("Band", ""),
                    "ssid": obj.get("ESSID", ""),
                    "enabled": obj.get("RadioStatus") == "1",
                }
            )
    return radios


def extract_wifi_channels(objects):
    channels = []
    for obj in objects:
        if "Channel" in obj and "Band" in obj:
            channel = _to_float(obj.get("Channel"))
            if channel is not None:
                channels.append({"band": obj.get("Band", ""), "channel": channel})
    return channels


def extract_voip_lines(objects):
    lines = []
    for obj in objects:
        if "IsOnline" in obj:
            lines.append(
                {
                    "line": str(len(lines) + 1),
                    "registered": obj.get("IsOnline") == "1",
                }
            )
    return lines


def extract_devices(objects, connection_type):
    devices = []
    for obj in objects:
        if "MACAddress" in obj:
            devices.append(
                {
                    "mac_address": obj.get("MACAddress", "").lower(),
                    "hostname": obj.get("HostName", "").strip() or "unknown",
                    "ip_address": obj.get("IPAddress", ""),
                    "connection_type": connection_type,
                    "active": obj.get("Active") == "1",
                }
            )
    return devices


def extract_eth_interface(objects):
    for obj in objects:
        if "LinkSpeed" in obj:
            return {
                "link_speed_mbps": _to_float(obj.get("LinkSpeed")),
                "up": obj.get("Status", "").lower() == "up",
                "full_duplex": obj.get("LinkDuplex", "").lower() == "full",
                "bytes_received": _to_float(obj.get("BytesReceived")),
                "bytes_sent": _to_float(obj.get("BytesSent")),
                "packets_received": _to_float(obj.get("PacketsReceived")),
                "packets_sent": _to_float(obj.get("PacketsSent")),
            }
    return {}


class ModemClient:
    def __init__(self, host, username, password, timeout=10):
        self.host = host if host.startswith("http") else f"http://{host}"
        self.username = username
        self.password = password
        self.timeout = timeout

        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{self.host}/",
            }
        )
        self.is_logged_in = False

        self.info_tracker = LabeledGaugeTracker(MODEM_INFO, ["serial_number", "firmware_version", "mac_address"])
        self.device_tracker = LabeledGaugeTracker(
            DEVICE_ACTIVE, ["mac_address", "hostname", "ip_address", "connection_type"]
        )
        self.wifi_ssid_tracker = LabeledGaugeTracker(WIFI_RADIO_ENABLED, ["band", "ssid"])
        self.wifi_channel_tracker = LabeledGaugeTracker(WIFI_CHANNEL, ["band"])
        self.voip_tracker = LabeledGaugeTracker(VOIP_LINE_REGISTERED, ["line"])

    def login(self):
        logger.info(f"Connecting to modem at {self.host}...")
        self.session.cookies.clear()
        try:
            # 1. Fetch index page to establish initial session cookie (_TESTCOOKIESUPPORT)
            self.session.get(f"{self.host}/", timeout=self.timeout)

            # 2. Get login token from logintoken_lua.lua
            token_url = f"{self.host}/function_module/login_module/login_page/logintoken_lua.lua"
            res_token = self.session.get(token_url, timeout=self.timeout)

            token_val = ""
            if res_token.status_code == 200:
                soup = BeautifulSoup(res_token.text, "html.parser")
                token_val = soup.get_text().strip()

            # 3. Calculate SHA256 password hash if token exists, else raw password
            if token_val:
                sha256_pass = hashlib.sha256((self.password + token_val).encode("utf-8")).hexdigest()
            else:
                sha256_pass = self.password

            # 4. POST login payload
            payload = {"Username": self.username, "Password": sha256_pass, "action": "login"}
            res_login = self.session.post(f"{self.host}/", data=payload, timeout=self.timeout)

            # Check if login succeeded via SID cookie or page content
            page_text = res_login.text.lower()
            login_ok = "logout" in page_text or "main" in page_text or bool(self.session.cookies.get("SID"))
            if res_login.status_code == 200 and login_ok:
                self.is_logged_in = True
                logger.info("Successfully logged into ZTE ZXHN H267A modem.")
                return True

            logger.error(
                f"Login attempt failed. Status: {res_login.status_code}, Cookies: {self.session.cookies.get_dict()}"
            )
            SCRAPE_ERRORS.labels(type="auth").inc()
            self.is_logged_in = False
            return False

        except requests.exceptions.Timeout:
            logger.error("Timeout occurred during modem login.")
            SCRAPE_ERRORS.labels(type="timeout").inc()
            self.is_logged_in = False
            return False
        except Exception as e:
            logger.error(f"Error during login: {e}")
            SCRAPE_ERRORS.labels(type="login").inc()
            self.is_logged_in = False
            return False

    def fetch_xml(self, path):
        url = f"{self.host}/{path.lstrip('/')}"
        try:
            res = self.session.get(url, timeout=self.timeout)
            if res.status_code == 200:
                looks_like_login_page = (
                    "Username" in res.text and "Password" in res.text and "login" in res.text.lower()
                )
                if "SessionTimeout" in res.text or looks_like_login_page:
                    logger.warning("Session expired while fetching data. Triggering re-login.")
                    self.is_logged_in = False
                    if self.login():
                        return self.session.get(url, timeout=self.timeout)
                    return None
                return res
            logger.warning(f"Unexpected status {res.status_code} fetching path {path}")
            return None
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching path {path}")
            SCRAPE_ERRORS.labels(type="timeout").inc()
            return None
        except Exception as e:
            logger.error(f"Failed to fetch path {path}: {e}")
            SCRAPE_ERRORS.labels(type="network").inc()
            return None

    def scrape(self):
        start_time = time.time()

        if not self.is_logged_in:
            if not self.login():
                SCRAPE_SUCCESS.set(0)
                SCRAPE_DURATION.set(time.time() - start_time)
                return

        try:
            # --- 1. WAN & System Status ---
            info_res = self.fetch_xml("getpage.lua?pid=1005&nextpage=home_information_lua.lua")
            if not info_res or info_res.status_code != 200:
                logger.error("Failed to retrieve system/WAN info page.")
                SCRAPE_ERRORS.labels(type="info").inc()
                SCRAPE_SUCCESS.set(0)
                return

            info_objects = parse_objects(info_res.text)

            wan_status = extract_wan_status(info_objects)
            if "connected" in wan_status:
                WAN_CONNECTED.set(1 if wan_status["connected"] else 0)
            if wan_status.get("uptime_seconds") is not None:
                WAN_UPTIME.set(wan_status["uptime_seconds"])

            system_status = extract_system_status(info_objects)
            if system_status.get("uptime_seconds") is not None:
                SYSTEM_UPTIME.set(system_status["uptime_seconds"])
            if system_status.get("serial_number"):
                self.info_tracker.update(
                    [
                        {
                            "serial_number": system_status["serial_number"],
                            "firmware_version": system_status.get("firmware_version", ""),
                            "mac_address": wan_status.get("mac_address", ""),
                            "value": 1,
                        }
                    ]
                )

            self.wifi_ssid_tracker.update(
                [
                    {"band": r["band"], "ssid": r["ssid"], "value": 1 if r["enabled"] else 0}
                    for r in extract_wifi_ssids(info_objects)
                ]
            )
            self.voip_tracker.update(
                [
                    {"line": v["line"], "value": 1 if v["registered"] else 0}
                    for v in extract_voip_lines(info_objects)
                ]
            )

            # --- 2. Connected Devices (LAN + WLAN) ---
            devices = []
            lan_res = self.fetch_xml("getpage.lua?pid=1005&nextpage=home_lanDevice_lua.lua")
            if lan_res and lan_res.status_code == 200:
                devices += extract_devices(parse_objects(lan_res.text), "lan")
            else:
                SCRAPE_ERRORS.labels(type="lan").inc()

            wlan_res = self.fetch_xml("getpage.lua?pid=1005&nextpage=home_wlanDevice_lua.lua")
            wlan_objects = []
            if wlan_res and wlan_res.status_code == 200:
                wlan_objects = parse_objects(wlan_res.text)
                devices += extract_devices(wlan_objects, "wlan")
            else:
                SCRAPE_ERRORS.labels(type="wlan").inc()

            self.device_tracker.update(
                [
                    {
                        **{k: d[k] for k in ("mac_address", "hostname", "ip_address", "connection_type")},
                        "value": 1 if d["active"] else 0,
                    }
                    for d in devices
                ]
            )
            CONNECTED_DEVICES.set(sum(1 for d in devices if d["active"]))

            self.wifi_channel_tracker.update(
                [{"band": c["band"], "value": c["channel"]} for c in extract_wifi_channels(wlan_objects)]
            )

            # --- 3. Ethernet WAN Interface (link speed, status, traffic counters) ---
            eth_res = self.fetch_xml("common_page/internet_eth_interface_lua.lua")
            if eth_res and eth_res.status_code == 200:
                eth = extract_eth_interface(parse_objects(eth_res.text))
                if eth.get("link_speed_mbps") is not None:
                    DOWNSTREAM_SPEED.set(eth["link_speed_mbps"])
                    UPSTREAM_SPEED.set(eth["link_speed_mbps"])
                if "up" in eth:
                    WAN_LINK_UP.set(1 if eth["up"] else 0)
                if "full_duplex" in eth:
                    WAN_LINK_FULL_DUPLEX.set(1 if eth["full_duplex"] else 0)
                if eth.get("bytes_received") is not None:
                    WAN_BYTES_RECEIVED.set(eth["bytes_received"])
                if eth.get("bytes_sent") is not None:
                    WAN_BYTES_SENT.set(eth["bytes_sent"])
                if eth.get("packets_received") is not None:
                    WAN_PACKETS_RECEIVED.set(eth["packets_received"])
                if eth.get("packets_sent") is not None:
                    WAN_PACKETS_SENT.set(eth["packets_sent"])
            else:
                SCRAPE_ERRORS.labels(type="eth").inc()

            SCRAPE_SUCCESS.set(1)

        except Exception as e:
            logger.error(f"Error while scraping metrics: {e}")
            SCRAPE_ERRORS.labels(type="scrape").inc()
            SCRAPE_SUCCESS.set(0)
        finally:
            SCRAPE_DURATION.set(time.time() - start_time)


def main():
    host = os.getenv("MODEM_HOST", "192.168.123.1")
    user = os.getenv("MODEM_USER", "admin")
    password = os.getenv("MODEM_PASSWORD")
    interval = int(os.getenv("SCRAPE_INTERVAL", "30"))
    port = int(os.getenv("EXPORTER_PORT", "9877"))
    timeout = float(os.getenv("MODEM_TIMEOUT", "10"))

    if not password:
        logger.error("MODEM_PASSWORD environment variable is required and must not be empty.")
        raise SystemExit(1)

    running = True

    def shutdown_handler(signum, frame):
        nonlocal running
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        running = False

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    logger.info(f"Starting ZXHN H267A Modem Exporter on port {port} (interval: {interval}s, timeout: {timeout}s)")
    start_http_server(port)

    client = ModemClient(host, user, password, timeout=timeout)

    while running:
        client.scrape()
        # Interruptible sleep in 1-second chunks for clean signal handling
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("Modem Exporter exited.")


if __name__ == "__main__":
    main()
