# Lab 2 — Canary Deployment (Argo Rollouts)

**Süre:** 15 dakika
**Zorluk:** ⭐⭐⭐
**Amaç:** Yeni versiyonu kademeli olarak (önce %10, sonra %30, %60, %100) deploy etmek; sorun çıkarsa abort etmek.

---

## Neden Canary?

| Strateji | Risk | Hız | Maliyet |
|----------|------|-----|---------|
| Rolling | Orta (v1+v2 mix sürer) | Hızlı | Düşük |
| Blue-Green | Düşük (atomik geçiş) | Çok hızlı | 2x kapasite |
| **Canary** | **En düşük** (kademeli, gözlemli) | Yavaş (dakikalar/saatler) | +1 replica |

Canary'de kritik nokta: **gözlem süresi**. v2 trafiğin %10'unu alırken metrikleri (error rate, latency) izlersin → kötüyse abort, iyiyse promote.

---

## Ön gereksinim

[README'deki Kurulum](../README.md#kurulum) yapıldıysa hazır:
- Argo Rollouts controller (`argo-rollouts` namespace)
- `kubectl-argo-rollouts` plugin

Kontrol:
```bash
kubectl -n argo-rollouts get pods
kubectl argo rollouts version --short
```

---

## Adım 1 — Rollout'u kur (3 dk)

```bash
cd lab2-canary
kubectl apply -f service.yaml
kubectl apply -f rollout.yaml

# 5 v1 pod + 2 payment-svc pod hazır olana kadar bekle
kubectl argo rollouts get rollout order-svc
```

İstersen Argo Rollouts dashboard'u aç (canlı görsel, çok faydalı):
```bash
kubectl argo rollouts dashboard &
# http://localhost:3100
```

---

## Adım 2 — İzleme terminalleri (1 dk)

**Terminal A — Rollout durumu (canlı):**
```bash
kubectl argo rollouts get rollout order-svc --watch
```
Step'leri, replica'ları, weight'leri canlı gösterir.

**Terminal B — v1/v2 dağılım sayacı:**
```bash
kubectl port-forward svc/order-svc 8001:8001
```

**Terminal B' (yeni terminal):**
```bash
while true; do
  V1=0; V2=0
  for i in $(seq 1 50); do
    R=$(curl -s --max-time 1 localhost:8001/version | grep -oE '"v[12]"' || echo '"err"')
    [ "$R" = '"v1"' ] && V1=$((V1+1))
    [ "$R" = '"v2"' ] && V2=$((V2+1))
  done
  echo "[$(date +%H:%M:%S)] v1=${V1}/50  v2=${V2}/50"
  sleep 2
done
```

---

## Adım 3 — Canary'yi başlat (5 dk)

**Terminal C** (komut girişi):

```bash
# Image tag'ini v2'ye al
kubectl argo rollouts set image order-svc order-svc=order-svc:v2

# (Bug workaround) APP_VERSION env'i de v2 yap — rollout.yaml'da hardcoded "v1"
kubectl set env rollout/order-svc APP_VERSION=v2
```

Terminal A'da göreceğin akış:
```
Status:        ⏸ Paused
Step:          1/7
SetWeight:     10
ActualWeight:  20   # 5 replica'da %10 = ~1 pod (1/5 = %20)
Replicas: 6 (1 canary + 5 stable)
```

Terminal B'de göreceğin akış:
```
[14:32:01] v1=45/50  v2=5/50    # ~%10 v2
[14:32:35] v1=35/50  v2=15/50   # 30s pause sonra step 3 → %30
[14:33:10] v1=20/50  v2=30/50   # ~%60 v2
[14:33:45] v1=0/50   v2=50/50   # %100 v2
```

> 💡 **Hassasiyet notu:** Argo Rollouts "basic canary" modunda trafik kontrolü pod sayısı oranıyla yapılır (Service round-robin). 5 replica'da %10 tam değil ama yaklaşık. **Kesin trafik kontrolü** için Istio/Nginx integration gerekir.

---

## Adım 4 — Manuel kontrol komutları (kullanışlı)

```bash
# Manuel bir sonraki step'e geç (pause beklemeden)
kubectl argo rollouts promote order-svc

# Tüm step'leri atla, doğrudan %100
kubectl argo rollouts promote order-svc --full

# İptal et — tüm trafik v1'e döner
kubectl argo rollouts abort order-svc

# Abort sonrası tekrar başlat
kubectl argo rollouts retry order-svc
```

---

## Adım 5 — Canary'yi abort et (kaos senaryosu, 3 dk)

Canary'nin %30-60 arasındayken (Terminal A'da gör):

**v2'ye kaos enjekte et:**
```bash
kubectl set env rollout/order-svc CHAOS_ERROR_RATE=0.3
```

Terminal B'de v2 response'larının bir kısmı 500 → curl loop'ta "err" sayısı artar.

**Abort:**
```bash
kubectl argo rollouts abort order-svc
```

Terminal A:
```
Status: ✖ Degraded
Message: RolloutAborted
```

Terminal B:
```
[14:34:20] v1=50/50  v2=0/50   # tüm trafik v1'e döndü
```

Süre: abort → v1'e geçiş ~5-10 sn (replica resize).

---

## Adım 6 — Başarılı canary (2 dk)

```bash
# Kaosu temizle
kubectl set env rollout/order-svc CHAOS_ERROR_RATE-

# Yeniden başlat
kubectl argo rollouts retry order-svc
```

Bu sefer tüm step'ler geçer, %100 v2'ye ulaşır:
```
Status: ✔ Healthy
Step: 7/7
SetWeight: 100
```

---

## Tartışma (2 dk)

**S1: Canary süreleri nasıl belirlenir?**
- Yüksek trafikli servis (10K req/s): %10'da 5-10 dk yeter (anlamlı sample)
- Düşük trafikli servis (10 req/s): %10'da 1-2 saat gerekebilir
- Kural: her step'te N hata gözlemlenebilecek kadar trafik akmalı

**S2: Otomatik abort nasıl yapılır?**

[analysis-template.yaml](analysis-template.yaml)'a bak — Prometheus'tan error rate çekip otomatik fail eden bir AnalysisTemplate örneği. rollout.yaml'a şu blokla eklenir:
```yaml
steps:
  - setWeight: 10
  - pause: {duration: 5m}
  - analysis:
      templates:
        - templateName: error-rate-check
  - setWeight: 30
```

**S3: Argo Rollouts vs Flagger?**

| Tool | Trafik kontrolü | Metrik provider | Karmaşıklık |
|------|-----------------|------------------|-------------|
| Argo Rollouts | Native (basic) + Istio/Nginx | Prometheus, Datadog, NewRelic | Orta |
| Flagger | Sadece service mesh ile | Prometheus | Yüksek (mesh gerekli) |

**S4: Canary deploy vs feature flag?**

- **Canary**: aynı kodun farklı versiyonu — infrastructure level.
- **Feature flag**: aynı versiyonun farklı kod yolu — application level.
- İkisi BİRLİKTE kullanılır: canary ile deploy et, flag ile feature'ı aç/kapat.

---

## Temizlik

```bash
kubectl delete -f rollout.yaml
kubectl delete -f service.yaml
# port-forward terminal'ini Ctrl+C ile kapat
```

---

## Komut özeti (cheatsheet)

```bash
kubectl argo rollouts get      NAME [--watch]
kubectl argo rollouts set image NAME container=image:tag
kubectl argo rollouts promote  NAME [--full]
kubectl argo rollouts abort    NAME
kubectl argo rollouts retry    NAME
kubectl argo rollouts undo     NAME [--to-revision=N]
kubectl argo rollouts dashboard    # web UI :3100
```
