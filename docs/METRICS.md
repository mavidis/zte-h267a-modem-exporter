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

UniFi'nin çevre AP tablosu bir cihazı son görülmesinden **~23 saat** sonra düşürür. Veri 2026-09-20 22:21'de başladı ve ilk düşüşler 2026-09-21 21:26'da görüldü. Controller açıldıktan sonraki ilk ~23 saatte liste sürekli büyür: Pazartesi günü 353'ten 2807'ye çıktı ve o gün hiç cihaz düşmedi. Bu ısınma dönemi grafiğe kümülatifmiş gibi bir görüntü verir. Sonrasında anlık liste boyutu (`count(unpoller_rogueap_signal)`) ~2.7-2.9k bandında oturur, gün içinde yalnızca birkaç yüz oynar ve sokak trafiğini göstermez. Saatlik **net fark** da işe yaramaz: listeye giren ve düşen cihaz sayıları birbirine yakın olduğu için trafik yoğun saatlerde bile net değer eksiye düşebilir. Ayrıca listedeki kayıtların çoğu donmuş durumdadır: UniFi bir kaydın `signal`/`age` değerlerini cihaz tekrar duyulana kadar güncellemez. Herhangi bir anda ~2.8k kaydın sadece birkaç düzinesi güncelleniyor. **Ana trafik göstergesi, son 1 saatte gerçekten duyulan cihaz sayısıdır** (`age` değişmiş ya da listeye yeni girmiş):

```promql
count(count by (mac)(
  (changes(unpoller_rogueap_age[1h]) > 0)
  or (unpoller_rogueap_age unless unpoller_rogueap_age offset 1h)
))
```

Referans (21-23 Eylül, sabit cihazlar hariç saatlik ortalama): gece 03:00 ~11, sabah 08:00 ~310, öğle ~150, akşam 18:00 ~315. Cihaz bazında patern analizi (günlük rutin, otobüs hattı, yeni/tekrar gelen) mavidis/unifi-network deposundaki `analysis/rogue_ap_report.py` scriptinde. Aşağıdaki listeye **yeni giren** sorgusu ikincil bir göstergedir: ~23 saatlik silme süresi yüzünden, düzenli geçen cihazları her gün yeniden "yeni" sayar.

```promql
# Son 1 saatte görülen ama bir önceki saatte görülmeyen benzersiz MAC sayısı
count(
  count by (mac)(count_over_time(unpoller_rogueap_signal[1h]))
  unless
  count by (mac)(count_over_time(unpoller_rogueap_signal[1h] offset 1h))
)
```

Referans değerler (2026-09-21 → 2026-09-24, ~74 saat, saatlik "yeni giren" MAC sayısı):

| Saat dilimi | Pzt 09-21 | Sal 09-22 | Çar 09-23 |
|---|---|---|---|
| Gece 03-06 | 11-20 | 6-8 | 4-7 |
| Sabah 08-10 | 246-280 | 132-169 | 104-123 |
| Öğle 11-16 | 99-146 | 99-128 | 91-132 |
| Akşam 17-20 | 167-218 | 133-169 | 167-203 |
| Günlük toplam giren / düşen | 2648 / 95 (ısınma) | 2047 / 1975 | 2067 / 2097 |

- Desen üç günde de tutarlı: gece dip, sabah trafik tepesi, gün içi plato ve günün en yüksek değerini veren akşam tepesi.
- Kararlı günlerde (Sal/Çar) günlük giren ≈ düşen (~2.05k). Liste dengede olduğu için net fark (giren − düşen) sıfır civarında gürültüden ibarettir.
- Pazartesi sabahı diğer günlerden belirgin şekilde yüksek. Bunun bir kısmı ısınma etkisi olabilir: Pazar gecesinden kalan liste neredeyse boştu. Bir kısmı da haftanın ilk günü etkisi olabilir. İkisini ayırmak için en az bir tam hafta (hafta sonu dahil) veri gerekir.
- Liste TTL'i (~23s) 24 saatten biraz kısa. Bu yüzden her gün aynı saatte geçen bir cihaz (ör. işe gidip gelen biri) ertesi gün listeden düşmüş olur ve yeniden "yeni" sayılır. Birden fazla UniFi AP varsa aynı MAC birden çok seri üretir (`ap_mac` label'ı), bu yüzden her zaman `count by (mac)` ile tekilleştirin.

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
