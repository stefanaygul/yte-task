# DevOps / Infra Görevleri — Chaos E-Commerce

## Senaryo
Black Friday gecesi 03:00. Monitoring yok, servisler crash olunca geri gelmiyor,
container'lar sınırsız kaynak tüketiyor, queue mesajları kayboluyor.
Senin görevin altyapıyı production-ready hale getirmek.

---

## D1 — Docker Compose Hardening (Kolay)
**Dosya:** `docker-compose.yml`
**Problem:** Hiçbir servisin healthcheck'i, resource limit'i, restart policy'si veya volume'u yok.
**Görev:**
- Tüm servislere uygun `healthcheck` ekle
- `restart: unless-stopped` veya `on-failure` ekle
- PostgreSQL ve RabbitMQ'ya `volumes` ekle (data persistence)
- `deploy.resources.limits` ile CPU/memory sınırla
- `depends_on` condition'larını `service_healthy` yap

**Çıktı:** `docker-compose kill api && sleep 5 && docker-compose ps` — api tekrar ayakta olmalı.

---

## D2 — Container Startup Order (Kolay)
**Dosya:** `docker-compose.yml`
**Problem:** `depends_on` container'ın çalıştığını kontrol eder ama servisin hazır olduğunu kontrol etmez.
**Görev:**
- PostgreSQL, Redis, RabbitMQ için healthcheck tanımla
- API ve worker'ın bu healthcheck'lere bağlı başlamasını sağla

**Çıktı:** `docker-compose up` — tüm servisler sorunsuz başlamalı, log'da connection refused yok.

---

## D3 — Monitoring Stack (Orta)
**Görev:**
- docker-compose'a Prometheus + Grafana ekle
- API'den metric endpoint'i expose et (prometheus_fastapi_instrumentator veya benzeri)
- Şu metrikleri topla:
  - Request rate (RPS)
  - Error rate (5xx)
  - Latency (p50, p95, p99)
  - Active DB connections
- Grafana'da basit bir dashboard oluştur

**Çıktı:** Locust çalışırken Grafana'da metrikleri gör. Screenshot al.

---

## D4 — Reverse Proxy (Orta)
**Görev:**
- Nginx veya Traefik'i reverse proxy olarak ekle
- Rate limiting uygula (örn: IP başına 100 req/s)
- API'yi doğrudan dışarı açma, proxy üzerinden eriş
- Access log formatını yapılandır

**Çıktı:** `ab -n 1000 -c 50 http://localhost/products/` — rate limit devreye girmeli.

---

## D5 — Log Aggregation (Orta)
**Görev:**
- Tüm servislerin loglarını merkezi bir yere topla
- Seçenek 1: ELK (Elasticsearch + Logstash + Kibana) — heavy ama tam
- Seçenek 2: Loki + Grafana — lightweight
- Structured logging (JSON format) ayarla
- Log level'ları yapılandır

**Çıktı:** Sipariş oluştur, Kibana/Grafana'da logunu bul. Screenshot al.

---

## D6 — Queue Management & DLQ (Orta)
**Dosya:** `docker-compose.yml`, RabbitMQ config
**Problem:** Dead letter queue yok. Hatalı mesajlar kaybolur.
**Görev:**
- RabbitMQ'da DLQ (dead letter exchange + queue) yapılandır
- Hatalı mesajların DLQ'ya gittiğini doğrula
- RabbitMQ management UI'dan queue'ları monitör et
- Alarm kur: DLQ'da mesaj birikirse bildirim

**Çıktı:** Kasıtlı hatalı mesaj gönder, DLQ'da göründüğünü doğrula.

---

## D7 — Horizontal Scaling (Orta)
**Görev:**
- API servisini `docker-compose up --scale api=3` ile çoğalt
- Load balancer (nginx) ekleyerek trafiği dağıt
- Worker'ı da scale et (`--scale worker=2`)
- Scaling sonrası DB connection pool toplam limitini hesapla

**Çıktı:** Locust ile 200 user test et. 3 API instance'ın log'unda trafiğin dağıldığını göster.

---

## D8 — Backup & Recovery (Orta)
**Görev:**
- PostgreSQL için otomatik backup script'i yaz (pg_dump, cron)
- Point-in-time recovery (WAL archiving) yapılandır
- Backup'tan restore testi yap
- Redis RDB/AOF persistence'ı yapılandır

**Çıktı:** Veri ekle → backup al → veriyi sil → restore et → veri geri geldi mi?

---

## D9 — Security Hardening (Zor)
**Görev:**
- Docker image'ları non-root user ile çalıştır
- Environment variable'ları secret yönetimi ile değiştir (docker secrets veya .env + gitignore)
- Network segmentation: frontend ve backend network ayır
- Gereksiz portları dışarıya kapatma (DB, Redis, RabbitMQ sadece internal)

**Çıktı:** Dışarıdan `telnet localhost 5432` çalışmamalı. API sadece proxy üzerinden erişilebilir olmalı.

---

## D10 — Chaos Testing (Zor)
**Görev:**
- Chaos test senaryoları yaz:
  1. `docker kill chaos-ecommerce-db-1` → API nasıl davranıyor?
  2. `docker kill chaos-ecommerce-redis-1` → Cache bypass çalışıyor mu?
  3. `tc qdisc add dev eth0 root netem delay 500ms` → Latency artınca ne oluyor?
  4. `docker-compose exec db psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='chaosdb'"` → Tüm DB bağlantılarını kes
- Her senaryo için beklenen davranışı ve gerçek davranışı dokümante et

**Çıktı:** Chaos test raporu: senaryo, beklenen, gerçek, aksiyon.

---

## Değerlendirme Rubriği

| Puan | Açıklama |
|------|----------|
| 0 | Yapılmadı |
| 1 | Denendi ama çalışmıyor veya yeni sorun ekledi |
| 2 | Çalışıyor ama neden bu yaklaşımı seçtiği açıklanmamış |
| 3 | Çalışıyor + trade-off analizi yapılmış + test edilmiş |
