# Lab 3 — Spike + Soak Test (10 dk)

**Amaç:** İki farklı dayanıklılık olgusu:
- **Spike:** ani yük patlamasına tepki + **recovery time**
- **Soak:** uzun süreli yükte **memory leak** → OOMKill

> Ön koşul: order-svc baseline durumda (`MEMORY_LEAK=false`, `SIMULATED_DB_LATENCY_MS=10`).

---

## Bölüm A — Spike Test (5 dk)

Trafik bir anda 10×'a çıkar (flash sale / viral an), 30sn tepede kalır, düşer.
Soru: sistem çöküyor mu, yoksa toparlıyor mu? **Ne kadar sürede** normale dönüyor?

**Terminal 1:**
```bash
k6 run k6-scripts/spike-test.js
# 100 → (10sn) 1000 → 30sn tut → 100 → recovery izle
```

**Terminal 2:**
```bash
watch -n1 kubectl top pods
kubectl get pods -w     # ayrı pencere: pod restart/OOM var mı
```

**İzlenecekler:**
1. Spike anında p99 ne kadar fırladı? (k6 canlı çıktı)
2. Spike bittikten sonra latency **kaç saniyede** baseline'a döndü? → recovery time
3. Pod crash/restart oldu mu? (ideal: hayır, sadece yavaşladı)

> 🎯 Ders: HPA olmadan spike'ı mevcut podlar yутmak zorunda. Recovery hızlıysa
> sistem "elastik". Lab 4'te HPA ekleyince spike'a otomatik pod doğacak.

---

## Bölüm B — Soak Test + Memory Leak (5 dk)

Sabit 100 VU ile 5 dk (workshop ölçeği — prod'da saatler/günler). `MEMORY_LEAK=true`
iken order-svc her isteği 100KB tutar ve bırakmaz → RSS tırmanır → 256Mi limit'te OOMKill.

### Leak'i aç ve çalıştır

```bash
kubectl set env deploy/order-svc MEMORY_LEAK=true
kubectl rollout status deploy/order-svc
```

**Terminal 1:**
```bash
k6 run -e THINK=1 k6-scripts/soak-test.js     # 100 VU, ~saniyede 1 istek/VU, 5 dk
```

**Terminal 2 — leak'i CANLI izle:**
```bash
watch -n5 kubectl top pods       # order-svc MEMORY sütunu düzenli tırmanır
kubectl get pods -w              # RESTARTS 0 → 1 olunca: OOMKilled
```

OOM gerçekleşince:
```bash
kubectl describe pod -l app=order-svc | grep -A3 "Last State"
# Last State: Terminated  Reason: OOMKilled  Exit Code: 137
```

> ⚠️ Workshop ölçeği: 100KB/istek × ~100 istek/sn → 256Mi limit'e ~1 dakikada çarpar.
> Prod'daki gerçek leak'ler günde birkaç MB sızar; biz saatleri dakikaya sıkıştırdık.
> Olgu aynı: monoton artan memory grafiği = leak parmak izi.

### Karşılaştır: leak kapalı (memory düz)

```bash
kubectl set env deploy/order-svc MEMORY_LEAK=false
kubectl rollout status deploy/order-svc

k6 run -e THINK=1 k6-scripts/soak-test.js
watch -n5 kubectl top pods       # MEMORY artık sabit platoda kalır, OOM YOK
```

| | MEMORY_LEAK=true | MEMORY_LEAK=false |
|---|---|---|
| Memory eğrisi | monoton artan ↗ | sabit plato → |
| OOMKill | evet (RESTARTS artar) | hayır |
| Çıkarım | **leak** — soak yakalar | sağlıklı |

> 🎯 Ders: Load/stress test bunu KAÇIRIR (çok kısa). Soak test memory eğrisinin
> eğimine bakar — düz olmalı. Sürekli artıyorsa, ne kadar yavaş olursa olsun, leak vardır.

---

## Lab 3 çıktısı

- [ ] Spike sonrası recovery time gözlemlendi
- [ ] `MEMORY_LEAK=true` ile memory tırmanışı + OOMKill (`RESTARTS`, Exit 137) görüldü
- [ ] `MEMORY_LEAK=false` ile memory'nin düz kaldığı karşılaştırıldı
- [ ] env'ler baseline'a geri alındı

➡️ Sıradaki: [Lab 4 — Kapasite + HPA](../lab4-capacity-hpa/README.md)
