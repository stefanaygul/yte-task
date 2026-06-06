# Lab 2 — Stress Test + Bottleneck (15 dk)

**Amaç:** Yükü kademeli artırarak **saturation point**'i (kırılma noktası) bul,
bottleneck'in CPU mu yoksa "DB" (simüle latency) mi olduğunu **kanıtla**.

> Ön koşul: order-svc baseline durumda (`SIMULATED_DB_LATENCY_MS=10`).

---

## 1) Stress test'i başlat + izle (5 dk)

İki terminal aç.

**Terminal 1 — yük:**
```bash
k6 run k6-scripts/stress-test.js
# Profil: 100 → 300 → 500 → 1000 VU, her seviye 1 dk
```

**Terminal 2 — kaynak izleme:**
```bash
watch -n2 kubectl top pods          # order-svc CPU/memory tırmanışı
# ayrı bir pencerede:
kubectl get pods -w                 # restart / OOM oluyor mu
```

k6 çıktısında her stage'de p95/p99 ve `http_req_failed`'i izle. VU arttıkça
latency tırmanır, bir noktada **dikey** fırlar — işte orası saturation.

---

## 2) Saturation point'i belirle (3 dk)

k6 canlı çıktısında (veya özetinde) şu soruyu cevapla:

> **Hangi VU/RPS seviyesinde p99 ilk kez 500ms'i geçti?**

`kubectl top pods` ile aynı anda:
> **O noktada order-svc CPU'su limit'e (500m) dayandı mı?**

[docs/capacity-template.md](../docs/capacity-template.md) → "Saturation" bölümünü doldur:

| Ölçüm | Değer |
|-------|-------|
| Saturation VU | _____ |
| Saturation RPS (≈ o seviyedeki http_reqs/s) | _____ |
| O anda CPU (millicore) | _____ |
| Bottleneck tahmini | CPU / DB / ağ |

---

## 3) Bottleneck CPU mu? (2 dk)

Baseline'da DB latency düşük (10ms). Yük altında order-svc CPU'su 500m limit'e
**dayanıyorsa** → bottleneck **CPU** (tek worker, Python event loop doygun).

`kubectl top pods` çıktısında order-svc ~`490m` gösteriyorsa CPU throttle ediliyor.

---

## 4) DB'nin bottleneck olduğunu KANITLA (5 dk)

DB latency'sini 10× artır, tekrar çalıştır. Eğer saturation point **düşerse**
(daha az RPS'te kırılırsa), bottleneck **CPU değil DB**'dir:

```bash
kubectl set env deploy/order-svc SIMULATED_DB_LATENCY_MS=100
kubectl rollout status deploy/order-svc

k6 run k6-scripts/stress-test.js
```

**Gözlem:** Aynı VU seviyesinde CPU daha DÜŞÜK kalır ama latency çok daha YÜKSEK.
Çünkü darboğaz hesaplama değil, "DB bekleme" (her istek `asyncio.sleep` ile I/O'da
asılı duruyor). Saturation RPS belirgin biçimde düşer.

| | DB=10ms | DB=100ms |
|---|---|---|
| Saturation RPS | _____ (daha yüksek) | _____ (daha düşük) |
| CPU @ saturation | _____ (yüksek) | _____ (düşük) |
| Çıkarım | CPU-bound | **DB/IO-bound** |

> 🎯 Ders: Bottleneck'i ölçmeden tahmin etme. "CPU ekleyelim" çözümü DB-bound
> sistemde para yakar; çözüm cache / DB index / connection pool olurdu.

**Bonus — cache etkisi:** GET trafiği için cache açınca DB latency bypass edilir:
```bash
kubectl set env deploy/order-svc CACHE_ENABLED=true
k6 run -e POST_RATIO=0 k6-scripts/stress-test.js   # sadece GET → cache hit
# GET p99 dramatik düşer, çünkü DB'ye gitmiyor
```

**Geri al:**
```bash
kubectl set env deploy/order-svc SIMULATED_DB_LATENCY_MS=10 CACHE_ENABLED=false
kubectl rollout status deploy/order-svc
```

---

## Lab 2 çıktısı

- [ ] Saturation point (VU + RPS) bulundu ve tabloya yazıldı
- [ ] `kubectl top pods` ile CPU davranışı gözlemlendi
- [ ] DB latency artırınca saturation point'in DÜŞTÜĞÜ gösterildi → DB bottleneck kanıtı
- [ ] env'ler baseline'a geri alındı

➡️ Sıradaki: [Lab 3 — Spike + Soak](../lab3-spike-soak/README.md)
