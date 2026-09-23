# ZTE ZXHN H267A Modem Exporter - Metrik ve PromQL Kılavuzu

Bu doküman, ZTE ZXHN H267A Exporter tarafından üretilen tüm metriklerin katalogunu, PromQL sorgu örneklerini ve Grafana yapılandırmalarını içerir.

---

## 1. Metrik Kataloğu

### Sistem ve Exporter Sağlık Metrikleri

| Metrik Adı | Tip | Etiketler | Birim | Açıklama |
|---|---|---|---|---|
| `modem_scrape_success` | Gauge | - | Boolean (0/1) | Son tarama döngüsünün başarı durumu |
| `modem_scrape_duration_seconds` | Gauge | - | Saniye | Exporter'ın modemi taraması için geçen toplam süre |
| `modem_scrape_errors_total` | Counter | `type` | Sayaç | Hata kategorisine göre oluşan toplam hata sayısı (`auth`, `info`, `lan`, `wlan`, `eth`, `timeout`, `network`, `scrape`) |
| `modem_info` | Gauge | `serial_number`, `firmware_version`, `mac_address` | Sabit 1 | Modemin kimlik bilgileri |
| `modem_system_uptime_seconds` | Gauge | - | Saniye | Modemin yeniden başlatılmasından bu yana geçen süre |

### WAN (Geniş Alan Ağı) ve İnternet Metrikleri

| Metrik Adı | Tip | Etiketler | Birim | Açıklama |
|---|---|---|---|---|
| `modem_wan_connected` | Gauge | - | Boolean (0/1) | PPPoE WAN bağlantısının aktiflik durumu |
| `modem_wan_uptime_seconds` | Gauge | - | Saniye | Kesintisiz aktif PPPoE bağlantı süresi |
| `modem_wan_link_up` | Gauge | - | Boolean (0/1) | Fiziksel WAN Ethernet kablo bağlantısı |
| `modem_wan_link_full_duplex` | Gauge | - | Boolean (0/1) | Ethernet portunun Full Duplex modu |
| `modem_downstream_sync_speed_mbps` | Gauge | - | Mbps | WAN portu downstream hız kapasitesi |
| `modem_upstream_sync_speed_mbps` | Gauge | - | Mbps | WAN portu upstream hız kapasitesi |
| `modem_wan_bytes_received_total` | Gauge | - | Byte | WAN arayüzünden indirilen (download) toplam veri |
| `modem_wan_bytes_sent_total` | Gauge | - | Byte | WAN arayüzünden yüklenen (upload) toplam veri |
| `modem_wan_packets_received_total` | Gauge | - | Paket | Alınan toplam Ethernet paketi |
| `modem_wan_packets_sent_total` | Gauge | - | Paket | Gönderilen toplam Ethernet paketi |

### Ağ Cihazları ve Kablosuz Ağ Metrikleri

| Metrik Adı | Tip | Etiketler | Birim | Açıklama |
|---|---|---|---|---|
| `modem_connected_devices_count` | Gauge | - | Sayı | Anlık aktif bağlı cihaz sayısı |
| `modem_device_active` | Gauge | `mac_address`, `hostname`, `ip_address`, `connection_type` | Boolean (0/1) | Ağa kayıtlı her cihazın aktiflik durumu |
| `modem_wifi_radio_enabled` | Gauge | `band`, `ssid` | Boolean (0/1) | 2.4GHz / 5GHz WiFi yayını açık mı |
| `modem_wifi_channel` | Gauge | `band` | Sayı | 2.4GHz / 5GHz frekansında seçili kanal |
| `modem_voip_line_registered` | Gauge | `line` | Boolean (0/1) | Sabit telefon (VoIP) hattının operatöre kayıt durumu |

---

## 2. Yararlı PromQL Sorgu Örnekleri

### Download Anlık Bant Genişliği (Bps / Mbps)
```promql
# Bit per second (bps)
rate(modem_wan_bytes_received_total[5m]) * 8

# Megabit per second (Mbps)
(rate(modem_wan_bytes_received_total[5m]) * 8) / 1000000
```

### Upload Anlık Bant Genişliği (Bps / Mbps)
```promql
# Bit per second (bps)
rate(modem_wan_bytes_sent_total[5m]) * 8

# Megabit per second (Mbps)
(rate(modem_wan_bytes_sent_total[5m]) * 8) / 1000000
```

### Son 1 Saatteki Scrape Hata Oranı
```promql
sum(increase(modem_scrape_errors_total[1h])) by (type)
```

### Sadece Aktif LAN Cihazları Tablosu
```promql
modem_device_active{connection_type="lan"} == 1
```

### Sadece Aktif WiFi Cihazları Tablosu
```promql
modem_device_active{connection_type="wlan"} == 1
```

### WAN Uptime İnsan Okunabilir Gösterim (Grafana)
* **Sorgu:** `modem_wan_uptime_seconds`
* **Grafana Field Unit:** `Time -> Duration (hh:mm:ss)` veya `dtdurations`

### Çevre AP (Rogue AP) Trafik Yoğunluğu (unpoller)

UniFi'nin çevre AP tablosu görülen cihazları ortalama ~1 gün tutup sonra düşürür. Bu yüzden anlık liste boyutu (`count(unpoller_rogueap_signal)`, ~2.8k) gün içinde yalnızca birkaç yüz oynar ve sokak trafiğini göstermez. Saatlik **net fark** da işe yaramaz: listeye giren ve düşen cihaz sayıları birbirine yakın olduğu için trafik yoğun saatlerde bile net değer eksiye düşebilir. Trafik göstergesi olarak listeye **yeni giren** MAC sayısını kullanın:

```promql
# Son 1 saatte görülen ama bir önceki saatte görülmeyen benzersiz MAC sayısı
count(
  count by (mac)(count_over_time(unpoller_rogueap_signal[1h]))
  unless
  count by (mac)(count_over_time(unpoller_rogueap_signal[1h] offset 1h))
)
```

Referans (2026-09-23): gece saatte ~5-7 yeni cihaz, sabah 07:00'den itibaren ~120, akşam 17-19 arası tepe 160-209. Birden fazla UniFi AP varsa aynı MAC birden çok seri üretir (`ap_mac` label'ı), bu yüzden her zaman `count by (mac)` ile tekilleştirin.

---

## 3. Alarm İfadeleri (Alert Expressions)

```yaml
# WAN kesintisi alarmı (1 dakikadan uzun süre kopuksa)
- alert: ModemWanDisconnected
  expr: modem_wan_connected == 0
  for: 1m

# Exporter tarama hatası (2 dakikadan uzun sürerse)
- alert: ModemScrapeFailed
  expr: modem_scrape_success == 0
  for: 2m
```
