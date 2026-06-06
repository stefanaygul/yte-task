# Ders 18 — Performans Testi & Kapasite Planlama Lab

Kubernetes üzerinde **k6** ile load / stress / spike / soak testleri, **bottleneck
analizi**, **kapasite planlama** ve **HPA** otomatik scaling'i hands-on çalışan
45-60 dakikalık workshop.

> Bu klasör derste işlenen konunun **örnek uygulamasıdır**. Aşağıdaki **Kurulum**
> bölümünü bir kez yapıp lab'lara sırayla geç. Her lab kendi README'sinde komut
> komut anlatılır.

## Kurulum

`kind/create-cluster.sh` yalnızca **altyapıyı** (cluster + metrics-server +
Prometheus/Grafana) kurar. Image build, app deploy ve tüm `k6`/`kubectl` komutları
bilerek manuel — her adımı görerek ilerliyoruz.

### 1) Altyapı: kind cluster + metrics-server + monitoring

```bash
cd ders18-perf-test
./kind/create-cluster.sh
# Grafana: http://localhost:30300 (admin/workshop), Prometheus: http://localhost:30900

kubectl config current-context   # kind-ders18-perf
kubectl top nodes                # metrics-server çalışıyor mu (HPA için şart)
```

> k6 host'ta kurulu olmalı: `brew install k6` (macOS). Script kontrol edip uyarır.

### 2) Image build + cluster'a load

```bash
docker build -t order-svc:latest ./app/order-svc
docker build -t payment-svc:latest ./app/payment-svc

kind load docker-image order-svc:latest payment-svc:latest --name ders18-perf
```

> Tüm workshop `order-svc`'nin 3 env "düğmesini" çevirerek ilerler (image rebuild YOK):
> `SIMULATED_DB_LATENCY_MS` (DB bottleneck), `CACHE_ENABLED` (cache hit), `MEMORY_LEAK`
> (soak/OOM). Hepsi `kubectl set env deploy/order-svc <VAR>=<deger>` ile canlı değişir.

### 3) App deploy + sanity

```bash
kubectl apply -f manifests/order-svc.yaml
kubectl apply -f manifests/payment-svc.yaml
kubectl rollout status deploy/order-svc
kubectl rollout status deploy/payment-svc

# Host'tan NodePort üzerinden (kind port mapping → 8001)
curl -s localhost:8001/version
# {"version":"1.0","db_latency_ms":10,"cache_enabled":false,"memory_leak":false}
```

Kurulum tamam → [Lab 1](lab1-load/README.md) ile başla.

## Yapı

```
ders18-perf-test/
├── README.md             ← Bu dosya (kurulum + lab indeksi)
├── teardown.sh           ← kind cluster'ı sil
│
├── kind/
│   ├── cluster.yaml         ← kind config (NodePort port mapping: 8001/30300/30900)
│   └── create-cluster.sh    ← TEK altyapı scripti (cluster + metrics-server + monitoring)
│
├── app/
│   ├── order-svc/        ← FastAPI: ayarlanabilir DB latency / cache / memory leak
│   └── payment-svc/      ← FastAPI: downstream ödeme (yapay latency + %5 hata)
│
├── manifests/            ← Deployment + Service (NodePort) + ServiceMonitor
│   ├── order-svc.yaml
│   └── payment-svc.yaml
│
├── k6-scripts/
│   ├── common.js            ← paylaşılan istek karışımı + hedef URL
│   ├── load-test.js         ← Lab 1: baseline
│   ├── thresholds.js        ← Lab 1: SLO threshold (p99<500ms, err<%1)
│   ├── stress-test.js       ← Lab 2: 100→1000 VU, saturation point
│   ├── spike-test.js        ← Lab 3: ani 10x spike + recovery
│   ├── soak-test.js         ← Lab 3: 5dk sabit yük, memory leak avı
│   └── capacity-test.js     ← Lab 4: hedef RPS + HPA gözlemleme
│
├── infra/
│   ├── kube-prometheus-values.yaml  ← Grafana/Prometheus (NodePort + k6 remote-write)
│   └── hpa.yaml                     ← order-svc HPA (target CPU %60, min2/max8)
│
├── lab1-load/        ← Load test + baseline + SLO threshold
├── lab2-stress/      ← Stress test + bottleneck + DB kanıtı
├── lab3-spike-soak/  ← Spike recovery + memory leak / OOM
├── lab4-capacity-hpa/← Kapasite hesabı + HPA otomatik scale
│
└── docs/
    ├── cheatsheet.md          ← k6 + kubectl komut reçeteleri
    └── capacity-template.md   ← Senin dolduracağın kapasite planlama şablonu
```

## Lab'lar bir bakışta

| Lab | Süre | Test türü | Öğrenilen |
|-----|------|-----------|-----------|
| [Lab 1](lab1-load/README.md) | 15 dk | Load | Baseline ölçümü, p95/p99/RPS okuma, SLO threshold |
| [Lab 2](lab2-stress/README.md) | 15 dk | Stress | Saturation point, bottleneck tespiti (DB kanıtı) |
| [Lab 3](lab3-spike-soak/README.md) | 10 dk | Spike + Soak | Recovery time, memory leak → OOMKill |
| [Lab 4](lab4-capacity-hpa/README.md) | 15 dk | Capacity | RPS'ten pod hesabı, HPA ile otomatik scale |

## Tasarım kararı

- **Script sadece altyapı:** `kind/create-cluster.sh` yalnızca cluster + monitoring +
  metrics-server kurar. Image build, app deploy, `kubectl set env`, `k6 run`, HPA apply
  gibi **öğretilen** komutlar Kurulum ve lab README'lerinde **manuel** —
  her adımı görerek öğrenmen için.
- **Ayrı kind cluster:** Bu lab kendi cluster'ını (`ders18-perf`) oluşturur;
  başka cluster'larla (`ders15-deploy`, `ders17-security`) çakışmaz.
- **Tek app, env var ile ayarlanabilir bottleneck:** `order-svc` aynı image'la kalır;
  `SIMULATED_DB_LATENCY_MS`, `CACHE_ENABLED`, `MEMORY_LEAK` değerlerini `kubectl set env`
  ile değiştirerek farklı performans olgularını canlı görebilirsin. Image rebuild gerekmez.
- **k6 host'tan, NodePort üzerinden:** k6 host binary'si `localhost:8001`'e basar
  (kind port mapping → order-svc NodePort 30801). port-forward'ın yük altında tıkanma
  riskinden kaçınılır.

## Kapanış — test türleri hangi soruyu cevaplar?

```
┌─ Load test  ── "Normal yükte SLO tutuyor mu?"      → baseline, kapasite girdisi
├─ Stress     ── "Nerede kırılıyor? Bottleneck ne?"  → saturation point
├─ Spike      ── "Ani patlamaya dayanır mı?"         → recovery time
├─ Soak       ── "Uzun vadede bozulan ne?"           → memory/fd/connection leak
└─ Capacity   ── "Hedef trafik için kaç pod?"        → HPA + headroom planı
```

Tartışma soruları:
1. Projende bu testlerden hangisi CI/CD'de koşuyor? Hangisi hiç koşmuyor?
2. Saturation point'ini biliyor musun? Bilmiyorsan, bir sonraki kampanyada ne olur?
3. Bottleneck'i ölçmeden "CPU ekleyelim" demek neden tehlikeli? (DB-bound örneği)
4. HPA reaktif. Bilinen trafik pattern'lerinde proactive ne yapardın?
5. p99'u mu yoksa avg'yi mi SLO yaparsın? Neden?

## Teardown

```bash
./teardown.sh   # kind cluster 'ders18-perf' silinir
```
