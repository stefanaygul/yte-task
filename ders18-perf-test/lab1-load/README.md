# Lab 1 — Load Test + Baseline (15 dk)

**Amaç:** k6 ile temel load test çalıştır, baseline rakamlarını ölç, SLO threshold
tanımla ve testi pass/fail kapısına dönüştür.

> Ön koşul: [README'deki Kurulum](../README.md#kurulum) tamam (image build + deploy edildi, `curl localhost:8001/version` cevap veriyor).

---

## 1) Baseline load test (5 dk)

100 VU ile 2 dakikalık steady yük. Threshold YOK — sadece ölçüyoruz.

```bash
k6 run k6-scripts/load-test.js
```

Çıktıda şu satırları **not al** (baseline tablosu):

```
  http_req_duration..............: avg=42ms  med=38ms  p(95)=95ms  p(99)=180ms  max=...
  http_reqs......................: 240000  ~2000/s          ← RPS
  http_req_failed................: 0.42%   ...              ← error rate
  iterations.....................: ...
```

**Tartış:**
- avg ile p99 arasındaki fark neden önemli? (avg yalan söyler, p99 "en kötü %1 müşteri")
- `http_req_failed` neden %0 değil? → payment-svc kasıtlı %5 random 500 üretiyor;
  POST trafiği bu hataları taşır. (POST oranı `common.js`'te `POST_RATIO`.)

> 💡 Sadece GET ölçmek istersen: `k6 run -e POST_RATIO=0 k6-scripts/load-test.js`

---

## 2) Baseline'ı tabloya yaz

[docs/capacity-template.md](../docs/capacity-template.md) → "Baseline" bölümünü doldur.
Bu rakamlar Lab 2 ve Lab 4'te referans olacak.

| Metrik | Baseline değer |
|--------|----------------|
| RPS (steady) | _____ |
| p95 latency | _____ |
| p99 latency | _____ |
| error rate | _____ |

---

## 3) SLO threshold ekle → pass/fail (5 dk)

Aynı yük, ama bu kez SLO'lar k6 threshold'u olarak tanımlı:
- p99 < 500ms
- error rate < %1

```bash
k6 run k6-scripts/thresholds.js
echo "exit code: $?"      # 0 = tüm SLO'lar geçti, 99 = en az biri fail
```

Sağlıklı sistemde **pass** (✓ yeşil threshold'lar) bekleriz.

---

## 4) SLO'yu kasıtlı fail ettir (3 dk)

DB latency'sini fırlat → p99 SLO'su patlasın:

```bash
kubectl set env deploy/order-svc SIMULATED_DB_LATENCY_MS=200
kubectl rollout status deploy/order-svc

k6 run k6-scripts/thresholds.js
echo "exit code: $?"      # 99 → p99<500ms artık FAIL
```

Çıktıda kırmızı threshold:
```
  ✗ http_req_duration..............: p(99)=420ms ... threshold p(99)<500 ✗
```
(200ms DB + zincir → p99 500ms'i aşar.)

**Geri al** (sonraki lab'lar baseline'dan başlasın):
```bash
kubectl set env deploy/order-svc SIMULATED_DB_LATENCY_MS=10
kubectl rollout status deploy/order-svc
```

---

## 5) Aynı rakamlara Grafana'dan bak (opsiyonel, 3 dk)

> ⚠️ Baseline rakamlarının **asıl kaynağı k6'nın terminal özeti** (Adım 1-2). Grafana
> bunları canlı GÖRSELLEŞTİRMEK için. İki ayrı bakış açısı var — ikisi farklı şey ölçer:
>
> - **Sunucu tarafı (order-svc):** Prometheus, order-svc `/metrics`'ini scrape eder → "sunucu ne gördü?"
> - **İstemci tarafı (k6):** k6 remote-write ile kendi metriklerini basar → "müşteri ne yaşadı?" (ağ + kuyruk dahil; k6 p99 genelde sunucu p99'dan biraz YÜKSEK çıkar — güzel tartışma).

### 5a) Sunucu tarafı — order-svc metrikleri (her zaman var)

Grafana → http://localhost:30300 (admin / workshop) → sol menü **Explore** → datasource **Prometheus**.
Adım 1'de tartıştığımız her metriğin PromQL karşılığı (kopyala-yapıştır):

```promql
# RPS (saniyedeki istek)
sum(rate(http_requests_total{job="order-svc"}[1m]))

# Error rate (% — 5xx oranı). Adım 1'deki "neden %0 değil" sorusunun grafiği.
sum(rate(http_requests_total{job="order-svc",status=~"5.."}[1m]))
  / sum(rate(http_requests_total{job="order-svc"}[1m]))

# p99 latency (saniye). avg vs p99 farkını görmek için ikisini aynı panele koy:
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="order-svc"}[1m])) by (le))

# p95 latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="order-svc"}[1m])) by (le))

# avg latency (toplam süre / istek sayısı) — p99 ile yan yana koyunca "avg yalan söyler" netleşir
sum(rate(http_request_duration_seconds_sum{job="order-svc"}[1m]))
  / sum(rate(http_request_duration_seconds_count{job="order-svc"}[1m]))
```

> 💡 Test koşarken bu sorguları çalıştır; Explore otomatik 5sn'de bir yeniler (ServiceMonitor `interval: 5s`).

### 5b) İstemci tarafı — k6 dashboard (opsiyonel)

```bash
# k6'yı metriklerini Prometheus'a basacak şekilde çalıştır
K6_PROMETHEUS_RW_SERVER_URL=http://localhost:30900/api/v1/write \
  k6 run -o experimental-prometheus-rw k6-scripts/load-test.js
```

Grafana → **Dashboards → New → Import** → ID **19665** ("k6 Prometheus") → datasource Prometheus.
Burada k6'nın gördüğü `k6_http_req_duration` (p95/p99), `k6_http_reqs` (RPS), `k6_http_req_failed` panelleri hazır gelir.

> Grafana açılmıyorsa monitoring stack kurulu mu? `kubectl get pods -n monitoring`.
> Yoksa `./kind/create-cluster.sh` (idempotent — eksik parçaları tamamlar).

---

## Lab 1 çıktısı

- [ ] Baseline tablosu dolduruldu (RPS, p95, p99, error)
- [ ] Threshold'lu test sağlıklı sistemde **pass** etti
- [ ] DB latency artırınca SLO **fail** etti (exit 99) ve geri alındı
- [ ] avg vs p99 farkını açıklayabiliyorsun

➡️ Sıradaki: [Lab 2 — Stress Test](../lab2-stress/README.md)
