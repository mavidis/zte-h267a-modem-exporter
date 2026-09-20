# ZTE ZXHN H267A Modem Exporter

ZTE ZXHN H267A fiber modeminin web arayüzünü scrape ederek Prometheus metriklerine dönüştüren bir exporter, hazır bir Grafana dashboard'u ve bunları çalıştıran bir `docker-compose` yığını.

Modemin resmi bir API'si yok; bu exporter modemin admin paneline aynı web arayüzünün (SHA256 token tabanlı login akışı, XML tabanlı iç sayfalar) kullandığı şekilde giriş yapar ve verileri parse eder.

## 📚 Detaylı Dokümantasyon

- [Mimari ve Tasarım Dokümantasyonu](docs/ARCHITECTURE.md): Kimlik doğrulama akışı, XML ayrıştırma algoritması ve oturum kurtarma mekanizması.
- [Metrik ve PromQL Kılavuzu](docs/METRICS.md): Tüm metriklerin listesi, örnek PromQL sorguları ve alarm formülleri.
- [Kurulum, Dağıtım ve İşletim Kılavuzu](docs/DEPLOYMENT.md): Docker Compose, Systemd servisi, sorun giderme ve güvenlik.

## Mimari

```
┌────────────────┐   scrape (login + XML)   ┌──────────────┐
│  ZTE ZXHN H267A │ <───────────────────────  │ modem-exporter│
│  (web arayüzü)  │                           │  :9877/metrics│
└────────────────┘                           └──────┬───────┘
                                                      │ scrape (30s)
                                                      ▼
                                              ┌──────────────┐
                                              │  Prometheus   │
                                              │    :9090      │
                                              └──────┬───────┘
                                                      │ query
                                                      ▼
                                              ┌──────────────┐
                                              │   Grafana     │
                                              │    :3000      │
                                              └──────────────┘
```

## Kurulum

```bash
cp .env.example .env
# .env içine MODEM_PASSWORD değerini (modem admin şifresi) yazın

docker compose up -d
```

- Grafana: http://localhost:3000 (ilk girişte `admin` / `admin`, girişte değiştirmeniz istenecektir)
- Prometheus: http://localhost:9090
- Ham metrikler: http://localhost:9877/metrics

### İsteğe bağlı: Disk SMART ve SRE yedekleme izleme

`docker-compose.sre.yml`, ZTE modem exporter'dan bağımsız iki ek servis içerir: `smartctl-exporter` (disk SMART sağlığı) ve `sre-backup-exporter` (`sre_exporter/`, yedekleme/restore-drill JSON dosyalarını Prometheus metriğine çevirir). Bu servisler belirli bir sunucudaki disk aygıtı ve dizin yollarına bağımlıdır; kendi ortamınıza göre `.env` içindeki `SMARTCTL_DEVICE_*`, `SRE_METRICS_DIR`, `SRE_BACKUP_DISK_PATH` değerlerini ayarlayıp şu şekilde etkinleştirin:

```bash
docker compose -f docker-compose.yml -f docker-compose.sre.yml up -d
```

Bu katman çalıştırılmazsa `smartctl-exporter`/`sre-backup` Prometheus hedefleri "down" görünür; bu zararsızdır ve modem exporter'ını etkilemez.

Grafana'da "ZXHN H267A Modem İzleme Panel" dashboard'u otomatik olarak provision edilir.

### Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `MODEM_HOST` | `192.168.123.1` | Modemin LAN IP'si |
| `MODEM_USER` | `admin` | Modem admin kullanıcı adı |
| `MODEM_PASSWORD` | *(zorunlu)* | Modem admin şifresi |
| `SCRAPE_INTERVAL` | `30` | Modemin kaç saniyede bir scrape edileceği (saniye) |
| `MODEM_TIMEOUT` | `10` | Modeme atılan HTTP istekleri için zaman aşımı süresi (saniye) |
| `EXPORTER_PORT` | `9877` | Exporter'ın dinlediği port |

## Metrikler

| Metrik | Tip | Etiketler | Açıklama |
|---|---|---|---|
| `modem_scrape_success` | gauge | - | Son scrape başarılı mıydı (1/0) |
| `modem_scrape_duration_seconds` | gauge | - | Her scrape döngüsünün toplam süresi (saniye) |
| `modem_scrape_errors_total` | counter | `type` | Hata türlerine göre toplam scrape hata sayısı (`auth`, `info`, `lan`, `wlan`, `eth`, `timeout`, `network`, `scrape`) |
| `modem_info` | gauge | `serial_number`, `firmware_version`, `mac_address` | Modem kimliği, her zaman 1 |
| `modem_wan_connected` | gauge | - | PPPoE WAN bağlantısı UP mı |
| `modem_wan_uptime_seconds` | gauge | - | WAN bağlantı süresi |
| `modem_system_uptime_seconds` | gauge | - | Modemin toplam çalışma süresi |
| `modem_downstream_sync_speed_mbps` | gauge | - | Downstream link hızı (Ethernet WAN olduğu için upstream ile aynı) |
| `modem_upstream_sync_speed_mbps` | gauge | - | Upstream link hızı |
| `modem_wan_link_up` | gauge | - | Fiziksel WAN Ethernet linki UP mı |
| `modem_wan_link_full_duplex` | gauge | - | WAN linki full-duplex mi |
| `modem_wan_bytes_received_total` | gauge | - | WAN arayüzünde alınan toplam byte |
| `modem_wan_bytes_sent_total` | gauge | - | WAN arayüzünde gönderilen toplam byte |
| `modem_wan_packets_received_total` | gauge | - | WAN arayüzünde alınan toplam paket |
| `modem_wan_packets_sent_total` | gauge | - | WAN arayüzünde gönderilen toplam paket |
| `modem_connected_devices_count` | gauge | - | Aktif LAN + WLAN cihaz sayısı |
| `modem_device_active` | gauge | `mac_address`, `hostname`, `ip_address`, `connection_type` | Bilinen her cihazın aktiflik durumu (1/0) |
| `modem_wifi_radio_enabled` | gauge | `band`, `ssid` | WiFi radyosu yayında mı |
| `modem_wifi_channel` | gauge | `band` | Yapılandırılmış WiFi kanalı |
| `modem_voip_line_registered` | gauge | `line` | VoIP hattının operatöre kayıtlı olup olmadığı |

`modem_device_active` gibi label'lı metrikler, önceki scrape'te var olup artık bulunmayan seriler için otomatik olarak temizlenir (bkz. `LabeledGaugeTracker` in `exporter/app.py`), böylece kaybolan cihazlar Prometheus'ta sonsuza dek asılı kalmaz.

## Alarm Kuralları (Prometheus Alerting)

`alert_rules.yml` dosyası ile önceden tanımlanmış alarmlar otomatik olarak Prometheus'a yüklenir:
- **`ModemScrapeFailed`**: Exporter modeme 2 dakikadan uzun süre ulaşamazsa tetiklenir.
- **`ModemWanDisconnected`**: WAN PPPoE bağlantısı 1 dakikadan uzun süre kapalı kalırsa tetiklenir.
- **`ModemPhysicalLinkDown`**: Modem ile ONT arasındaki fiziksel Ethernet linki düştüğünde tetiklenir.
- **`ModemVoipUnregistered`**: VoIP sabit telefon hattı operatörden kayıtsız duruma düşerse tetiklenir.

## Geliştirme

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

ruff check .        # lint
ruff format .        # format
pytest -v            # testler
```

Testler modeme bağlanmaz; modemin gerçek XML formatını taklit eden anonimleştirilmiş fixture dosyaları kullanır (`tests/fixtures/`). Parsing mantığı (`parse_objects`, `extract_*`) modemin HTML/network katmanından tamamen ayrıştırılmıştır, bu yüzden saf fonksiyonlar olarak test edilebilir.

## Güvenlik notları

- `.env` dosyası `.gitignore` içinde, asla commit etmeyin.
- Docker container'ı non-root `appuser` kullanıcısı ile çalışır.
- Modem şifresi ortam değişkeninde düz metin olarak tutulur; mümkünse modeminizde bu exporter için kısıtlı/salt-okunur bir kullanıcı tanımlayın.
- Grafana'nın varsayılan `admin/admin` şifresini ilk girişte değiştirin (`docker-compose.yml` içindeki `GF_SECURITY_ADMIN_PASSWORD` ile de değiştirilebilir).
- `modem_device_active` metriği ev ağınızdaki cihazların hostname/MAC/IP bilgilerini Prometheus'a yazar; Grafana/Prometheus'a erişimi olan herkes bu bilgiyi görebilir.

## Bilinen sınırlamalar

- Bu modem fiber ONT'ye Ethernet üzerinden bağlandığından (DSL değil), optik seviye (RX/TX power) verisi modemin web arayüzünde bulunmuyor — ONT'nin kendisi ayrı bir exporter gerektirir.
- Modemin web arayüzünde CPU/RAM/sıcaklık gibi sistem kaynak metrikleri yayınlanmıyor.
- `modem_device_active` etiket kardinalitesi ev ağınızdaki cihaz sayısıyla orantılı büyür; çok büyük ağlarda (yüzlerce cihaz) dikkat edin.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
