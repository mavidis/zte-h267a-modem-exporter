# Changelog

Bu projedeki önemli değişiklikler bu dosyada tutulur.

Format [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) standardına, sürümleme [Semantic Versioning](https://semver.org/spec/v2.0.0.html) kurallarına uyar.

## [Unreleased]

### Added
- `unifi_alert_rules.yml` (mavidis/unifi-network deposundan `make sync` ile kopyalanır): UniFi poller/controller/AP erişimi, kanal doluluğu, zayıf sinyal, kapalı otomatik yedek ve rogue AP recording rule hattı alarmları. Bu depodaki `alert_rules.yml`'i ezmemek için `unifi_` önekli. `rule_files` listesine ve prometheus mount'larına eklendi.
- `rogueap_recording_rules.yml` (mavidis/unifi-network deposundaki `prometheus/rogueap_recording_rules.yml` ile senkron): çevre AP görülmelerini kaydeden `rogueap:*` recording rule'ları. `prometheus.yml` içindeki `rule_files` listesine eklendi ve `docker-compose.yml`'de mount edildi. Geçmiş veri (2026-09-20'den itibaren) `promtool tsdb create-blocks-from rules` ile dolduruldu.
- Rogue AP dashboard'u (unifi-network'ten senkronize): "Saatlik Yeni ve Tekrar Gelen Cihazlar" paneli ve "Düzenli Geçen Cihazlar" tablosu.
- Rogue AP dashboard'una "Saatlik Yeni Görülen / Düşen Cihaz" paneli eklendi. Panel, çevre AP listesine saatlik giren ve listeden düşen benzersiz MAC sayılarını gösterir; giren sayısı sokak trafiği yoğunluğunu yansıtır.
- `docs/METRICS.md`: çevre AP trafik yoğunluğu PromQL örneği ve yorumlama notları. İçinde ~74 saatlik veriden çıkarılan referans değerler, ~23 saatlik liste TTL'i ve controller açılışındaki ısınma dönemi açıklaması var.

### Changed
- Rogue AP stat panelleri ve saatlik paneli recording rule'lara geçti.
- Rogue AP saatlik paneli artık "Saatlik Duyulan Cihaz" (unifi-network deposundan senkronize). Serileri gerçek görülmeler (`age` değişimi) ve listeye yeni girenler. Kaynak ve analiz için mavidis/unifi-network deposuna bakın.

### Fixed
- "Benzersiz Çevre AP Sayısı" paneli artık `count by (mac)` ile tekilleştiriyor; birden fazla UniFi AP olduğunda aynı cihaz birden çok kez sayılmıyor. Panel açıklamasındaki listenin kümülatif büyüdüğü yönündeki yanlış bilgi düzeltildi.
