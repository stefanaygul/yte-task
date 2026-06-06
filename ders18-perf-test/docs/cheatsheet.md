# Ders 18 — Cheatsheet

Workshop boyunca en sık ihtiyaç duyulan komutlar.

## Context & durum

```bash
kubectl config use-context kind-ders18-perf

kubectl get pods,svc,hpa
kubectl get pods -l app=order-svc
kubectl top pods                      # metrics-server gerekir
kubectl top pods -l app=order-svc
```

## App davranışını değiştir (env var — image rebuild YOK)

```bash
# DB latency (bottleneck simülasyonu)
kubectl set env deploy/order-svc SIMULATED_DB_LATENCY_MS=100

# Cache aç/kapat (GET /orders DB'yi bypass eder)
kubectl set env deploy/order-svc CACHE_ENABLED=true

# Memory leak (soak test)
kubectl set env deploy/order-svc MEMORY_LEAK=true

# payment-svc latency
kubectl set env deploy/payment-svc SIMULATED_LATENCY_MS=100

# Baseline'a topluca geri dön
kubectl set env deploy/order-svc \
  SIMULATED_DB_LATENCY_MS=10 CACHE_ENABLED=false MEMORY_LEAK=false
kubectl rollout status deploy/order-svc

# Aktif env'leri gör
kubectl set env deploy/order-svc --list
curl -s localhost:8001/version
```

## k6 çalıştırma

```bash
# Temel
k6 run k6-scripts/load-test.js

# Hedef URL / istek karışımı override
k6 run -e BASE_URL=http://localhost:8001 k6-scripts/load-test.js
k6 run -e POST_RATIO=0   k6-scripts/load-test.js   # sadece GET
k6 run -e POST_RATIO=1   k6-scripts/load-test.js   # sadece POST (pahalı yol)
k6 run -e THINK=1        k6-scripts/soak-test.js    # her VU sn'de ~1 istek

# Hedef RPS (capacity)
k6 run -e RATE=600 k6-scripts/capacity-test.js

# Soak süresini değiştir
k6 run -e THINK=1 -e DURATION=2m k6-scripts/soak-test.js

# Threshold sonucu (CI/CD kapısı): 0=pass, 99=fail
k6 run k6-scripts/thresholds.js; echo "exit=$?"

# JSON özet dosyaya
k6 run --summary-export=summary.json k6-scripts/load-test.js

# k6 yoksa Docker ile (host network gerekir)
docker run --rm -i --network host -e BASE_URL=http://localhost:8001 \
  grafana/k6 run - < k6-scripts/load-test.js
```

## k6 çıktısı nasıl okunur

```
http_req_duration..: avg=42ms med=38ms p(95)=95ms p(99)=180ms   ← latency dağılımı
http_reqs..........: 240000   2000.1/s                          ← toplam + RPS
http_req_failed....: 0.42%    1008 out of 240000                ← error rate
vus................: 100      max=100                           ← eşzamanlı kullanıcı
iterations.........: 240000                                     ← tamamlanan akış
```
- **p99** = "en kötü %1 müşterinin" gördüğü süre. SLO'lar genelde p95/p99 üzerinden.
- **avg yalan söyler:** birkaç yavaş istek p99'u fırlatır ama avg'yi az etkiler.

## Kaynak izleme (yük altında)

```bash
watch -n2 kubectl top pods
watch -n2 'kubectl get pods -l app=order-svc; kubectl top pods -l app=order-svc'
kubectl get pods -w                          # restart/OOM canlı
kubectl get hpa -w                           # replica değişimi canlı

# OOM doğrulama
kubectl describe pod -l app=order-svc | grep -A3 "Last State"
# Reason: OOMKilled / Exit Code: 137
```

## HPA

```bash
kubectl apply -f infra/hpa.yaml
kubectl get hpa
kubectl get hpa order-svc -o yaml | grep -A8 currentMetrics
kubectl describe hpa order-svc               # scale event'leri (Events bölümü)

# Manuel scale (HPA'sız karşılaştırma)
kubectl scale deploy/order-svc --replicas=5

# HPA kaldır
kubectl delete -f infra/hpa.yaml
```

## Grafana / Prometheus

```bash
# Grafana:    http://localhost:30300   (admin / workshop)
# Prometheus: http://localhost:30900

# Faydalı PromQL (Prometheus UI veya Grafana Explore):
#   RPS:        sum(rate(http_requests_total{job="order-svc"}[1m]))
#   p99 latency:histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="order-svc"}[1m])) by (le))
#   error rate: sum(rate(http_requests_total{job="order-svc",status=~"5.."}[1m])) / sum(rate(http_requests_total{job="order-svc"}[1m]))
#   CPU:        rate(container_cpu_usage_seconds_total{pod=~"order-svc.*"}[1m])

# k6 metriklerini Grafana'ya canlı bas (remote-write)
K6_PROMETHEUS_RW_SERVER_URL=http://localhost:30900/api/v1/write \
  k6 run -o experimental-prometheus-rw k6-scripts/load-test.js
# Grafana'da hazır k6 dashboard: import ID 19665 (k6 Prometheus)
```

## Hızlı reset (lab'lar arası)

```bash
# App'i baseline env'e döndür
kubectl set env deploy/order-svc \
  SIMULATED_DB_LATENCY_MS=10 CACHE_ENABLED=false MEMORY_LEAK=false

# HPA + scale temizle
kubectl delete -f infra/hpa.yaml --ignore-not-found
kubectl scale deploy/order-svc --replicas=2
```

## Tam teardown

```bash
./teardown.sh    # kind cluster 'ders18-perf' silinir
```
