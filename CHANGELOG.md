# Changelog

Bu projedeki önemli değişiklikler bu dosyada tutulur.

Format [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) standardına, sürümleme [Semantic Versioning](https://semver.org/spec/v2.0.0.html) kurallarına uyar.

## [Unreleased]

### Added
- Rogue AP dashboard'una "Saatlik Yeni Görülen / Düşen Cihaz" paneli eklendi. Panel, çevre AP listesine saatlik giren ve listeden düşen benzersiz MAC sayılarını gösterir; giren sayısı sokak trafiği yoğunluğunu yansıtır.
- `docs/METRICS.md`: çevre AP trafik yoğunluğu PromQL örneği ve yorumlama notları. İçinde ~74 saatlik veriden çıkarılan referans değerler, ~23 saatlik liste TTL'i ve controller açılışındaki ısınma dönemi açıklaması var.

### Changed
- Rogue AP saatlik paneli artık "Saatlik Duyulan Cihaz" (unifi-network deposundan senkronize). Serileri gerçek görülmeler (`age` değişimi) ve listeye yeni girenler. Kaynak ve analiz için mavidis/unifi-network deposuna bakın.

### Fixed
- "Benzersiz Çevre AP Sayısı" paneli artık `count by (mac)` ile tekilleştiriyor; birden fazla UniFi AP olduğunda aynı cihaz birden çok kez sayılmıyor. Panel açıklamasındaki listenin kümülatif büyüdüğü yönündeki yanlış bilgi düzeltildi.
