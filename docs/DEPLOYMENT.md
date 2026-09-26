# ZTE ZXHN H267A Modem Exporter - Kurulum, Dağıtım ve İşletim Kılavuzu

Bu kılavuz, ZTE ZXHN H267A Modem Exporter yığınının farklı ortamlarda dağıtımını, yapılandırma seçeneklerini, sorun giderme adımlarını ve güvenlik önlemlerini açıklar.

---

## 1. Docker Compose ile Dağıtım (Önerilen)

En kolay ve izole dağıtım yöntemi Docker Compose kullanmaktır.

### Adım 1: Depoyu Hazırlayın ve Yapılandırın
```bash
git clone https://github.com/mavidis/zte-h267a-modem-exporter.git
cd zte-h267a-modem-exporter

cp .env.example .env
```

`.env` dosyasını düzenleyin:
```ini
MODEM_HOST=192.168.123.1
MODEM_USER=admin
MODEM_PASSWORD=modem_admin_sifreniz
SCRAPE_INTERVAL=30
MODEM_TIMEOUT=10
```

### Adım 2: Servisleri Başlatın

> **Kalıcı veri:** Prometheus verisi `modem_prometheus_data` volume'unda, Grafana veritabanı `./data/grafana` altında. `data/` git'te değil, yedeklenmesi gerekir. Proje adı `docker-compose.yml`'de sabit (`name: modem`): değiştirilirse Docker yeni ve boş bir Prometheus volume'u açar.
>
> **Yeni kurulumda** Grafana (uid 472) dizine yazabilsin diye: `mkdir -p data/grafana && sudo chown 472:0 data/grafana`
```bash
docker compose up -d
```

### Adım 3: Servislerin Durumunu Kontrol Edin
```bash
docker compose ps
docker compose logs -f modem-exporter
```

---

## 2. Linux Systemd Servisi Olarak Doğrudan Çalıştırma

Docker kullanmak istemiyorsanız, exporter'ı yerel bir Python servisi olarak da çalıştırabilirsiniz.

### Adım 1: Python Sanal Ortamını Hazırlayın
```bash
python3 -m venv /opt/modem-exporter/venv
/opt/modem-exporter/venv/bin/pip install -r requirements.txt
```

### Adım 2: Systemd Servis Dosyası Oluşturun (`/etc/systemd/system/modem-exporter.service`)
```ini
[Unit]
Description=ZTE ZXHN H267A Modem Prometheus Exporter
After=network.target

[Service]
Type=simple
User=nobody
WorkingDirectory=/opt/modem-exporter
Environment=MODEM_HOST=192.168.123.1
Environment=MODEM_USER=admin
Environment=MODEM_PASSWORD=modem_admin_sifreniz
Environment=SCRAPE_INTERVAL=30
Environment=MODEM_TIMEOUT=10
Environment=EXPORTER_PORT=9877
ExecStart=/opt/modem-exporter/venv/bin/python /opt/modem-exporter/exporter/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Adım 3: Servisi Etkinleştirin ve Başlatın
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now modem-exporter
sudo systemctl status modem-exporter
```

---

## 3. Erişim Noktaları ve Portlar

| Servis | Varsayılan URL | Açıklama |
|---|---|---|
| **Exporter Metrikleri** | `http://localhost:9877/metrics` | Ham Prometheus metrik çıktısı |
| **Prometheus UI** | `http://localhost:9090` | Prometheus sorgu ve kural arayüzü |
| **Grafana Dashboard** | `http://localhost:3000` | Görselleştirme paneli (`admin` / `admin`) |

---

## 4. Sorun Giderme (Troubleshooting)

### 1. `modem_scrape_success` Sürekli 0 Dönüyor
* **Şifre / Kullanıcı Adı:** Modemin web arayüzüne elle tarayıcıdan giriş yapmayı test edin.
* **IP Adresi:** Modemin IP'sinin doğru olduğunu doğrulayın (`ping 192.168.123.1`).
* **Session Timeout:** Modemin web arayüzünde başka bir tarayıcı açık kalmışsa aynı anda tek oturuma izin veriyor olabilir. Diğer oturumları kapatın.
* **Log Kontrolü:**
  ```bash
  docker compose logs modem-exporter
  ```

### 2. Prometheus Verileri Sıfırlanıyor mu?
* `docker-compose.yml` içinde `prometheus_data:/prometheus` volume tanımı bulunmaktadır. `docker compose down -v` komutu verilmediği sürece veriler kalıcı olarak korunur.

### 3. Zaman Aşımı (Timeout) Hataları Alınıyor
* Modemin yoğun olduğu durumlarda `.env` dosyasındaki `MODEM_TIMEOUT` değerini artırın (örn. `MODEM_TIMEOUT=20`).

---

## 5. Güvenlik Tavsiyeleri

* `.env` dosyasını kesinlikle kaynak kontrolüne (git) göndermeyin.
* Grafana ilk açılışta `admin/admin` şifresini değiştirmenizi zorunlu kılar, güçlü bir parola belirleyin.
* Exporter container'ı sistem güvenliği için kısıtlı `appuser` kullanıcısı ile çalışacak şekilde yapılandırılmıştır.
