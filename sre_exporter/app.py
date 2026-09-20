#!/usr/bin/env python3
import json
import os
import shutil
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

METRICS_DATA_DIR = os.getenv("METRICS_DATA_DIR", "/metrics_data")
LATEST_FILE = os.path.join(METRICS_DATA_DIR, "latest.json")
DATA_FILE = os.path.join(METRICS_DATA_DIR, "data.json")
RESTORE_LATEST_FILE = os.path.join(METRICS_DATA_DIR, "restore_latest.json")
DISK_PATH = os.getenv("DISK_PATH", "/mnt/IronWolf")
PORT = int(os.getenv("PORT", "9878"))


def _read_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except Exception:
        return {}

def generate_prometheus_metrics():
    lines = []
    lines.append("# HELP sre_backup_status Son SRE yedekleme genel durumu (1=SUCCESS, 0=FAILURE)")
    lines.append("# TYPE sre_backup_status gauge")
    lines.append("# HELP sre_backup_total_bytes Son yedeklemede aktarilan toplam bayt")
    lines.append("# TYPE sre_backup_total_bytes gauge")
    lines.append("# HELP sre_backup_total_files Son yedeklemede aktarilan toplam dosya adedi")
    lines.append("# TYPE sre_backup_total_files gauge")
    lines.append("# HELP sre_backup_last_timestamp_seconds Son yedeklemenin tamamlanma zamani (epoch)")
    lines.append("# TYPE sre_backup_last_timestamp_seconds gauge")
    lines.append("# HELP sre_backup_server_status Sunucu bazli yedekleme ve checksum durumu (1=OK, 0=FAIL)")
    lines.append("# TYPE sre_backup_server_status gauge")
    lines.append("# HELP sre_backup_server_bytes Sunucu bazli aktarilan bayt")
    lines.append("# TYPE sre_backup_server_bytes gauge")
    lines.append("# HELP sre_backup_server_files Sunucu bazli aktarilan dosya adedi")
    lines.append("# TYPE sre_backup_server_files gauge")
    lines.append("# HELP sre_backup_disk_total_bytes Yedekleme diski toplam kapasitesi")
    lines.append("# TYPE sre_backup_disk_total_bytes gauge")
    lines.append("# HELP sre_backup_disk_free_bytes Yedekleme diski bos alan")
    lines.append("# TYPE sre_backup_disk_free_bytes gauge")
    lines.append("# HELP sre_backup_disk_used_percent Yedekleme diski doluluk orani (%)")
    lines.append("# TYPE sre_backup_disk_used_percent gauge")

    # Disk Bilgisi
    try:
        total, used, free = shutil.disk_usage(DISK_PATH)
        used_percent = (used / total) * 100 if total > 0 else 0
        lines.append(f"sre_backup_disk_total_bytes {total}")
        lines.append(f"sre_backup_disk_free_bytes {free}")
        lines.append(f"sre_backup_disk_used_percent {used_percent:.2f}")
    except Exception:
        lines.append("sre_backup_disk_total_bytes 0")
        lines.append("sre_backup_disk_free_bytes 0")
        lines.append("sre_backup_disk_used_percent 0")

    # Latest Backup Metrics
    latest_data = _read_json(LATEST_FILE)

    status_code = latest_data.get("status_code", 1)
    total_bytes = latest_data.get("total_bytes", 0)
    total_files = latest_data.get("total_files", 0)
    ts = latest_data.get("timestamp", int(time.time()))

    lines.append(f"sre_backup_status {status_code}")
    lines.append(f"sre_backup_total_bytes {total_bytes}")
    lines.append(f"sre_backup_total_files {total_files}")
    lines.append(f"sre_backup_last_timestamp_seconds {ts}")

    servers = latest_data.get("servers", [])
    for srv in servers:
        s_ip = srv.get("server", "unknown")
        s_name = srv.get("name", s_ip)
        s_bytes = srv.get("bytes", 0)
        s_files = srv.get("files", 0)
        s_ok = srv.get("status_ok", 1)
        lines.append(f'sre_backup_server_status{{server="{s_ip}",name="{s_name}"}} {s_ok}')
        lines.append(f'sre_backup_server_bytes{{server="{s_ip}",name="{s_name}"}} {s_bytes}')
        lines.append(f'sre_backup_server_files{{server="{s_ip}",name="{s_name}"}} {s_files}')

    # Latest Restore Drill Metrics (restore-validate projesi)
    lines.append("# HELP sre_restore_status Son restore-drill genel durumu (1=SUCCESS, 0=FAILURE)")
    lines.append("# TYPE sre_restore_status gauge")
    lines.append("# HELP sre_restore_total_tests Son restore-drill'de test edilen DB sayısı")
    lines.append("# TYPE sre_restore_total_tests gauge")
    lines.append("# HELP sre_restore_successful_tests Son restore-drill'de başarıyla restore edilen DB sayısı")
    lines.append("# TYPE sre_restore_successful_tests gauge")
    lines.append("# HELP sre_restore_last_timestamp_seconds Son restore-drill'in tamamlanma zamani (epoch)")
    lines.append("# TYPE sre_restore_last_timestamp_seconds gauge")
    lines.append("# HELP sre_restore_db_status DB bazli restore-test durumu (1=OK, 0=FAIL)")
    lines.append("# TYPE sre_restore_db_status gauge")

    restore_data = _read_json(RESTORE_LATEST_FILE)
    r_status_code = restore_data.get("status_code", 1)
    r_total = restore_data.get("total_tests", 0)
    r_success = restore_data.get("successful_tests", 0)
    r_ts = restore_data.get("timestamp", int(time.time()))

    lines.append(f"sre_restore_status {r_status_code}")
    lines.append(f"sre_restore_total_tests {r_total}")
    lines.append(f"sre_restore_successful_tests {r_success}")
    lines.append(f"sre_restore_last_timestamp_seconds {r_ts}")

    for db in restore_data.get("databases", []):
        d_server = db.get("server", "unknown")
        d_name = db.get("name", d_server)
        d_db = db.get("db", "unknown")
        d_engine = db.get("engine", "unknown")
        d_ok = db.get("status_ok", 1)
        lines.append(
            f'sre_restore_db_status{{server="{d_server}",name="{d_name}",db="{d_db}",engine="{d_engine}"}} {d_ok}'
        )

    return "\n".join(lines) + "\n"

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics" or self.path == "/":
            output = generate_prometheus_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(output.encode("utf-8"))
        elif self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, MetricsHandler)
    print(f"[SRE Exporter] Running on port {PORT}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
