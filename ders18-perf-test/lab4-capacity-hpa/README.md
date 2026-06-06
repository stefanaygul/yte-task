# Lab 4 — Kapasite Planlama + HPA (15 dk)

**Amaç:** Lab 2'deki saturation rakamından **kaç pod gerektiğini hesapla**, HPA
uygula ve hedef RPS altında **otomatik scale**'i canlı izle.

> Ön koşul: order-svc baseline durumda; Lab 2'den saturation RPS rakamın var.

---

## 1) Kapasiteyi hesapla (3 dk)

Lab 2'de bulduğun "1 pod = SLO içinde kaç RPS" rakamını kullan. Örnek (kendi
rakamınla değiştir):

```
1 pod  ≈ 200 RPS @ SLO (p99 < 500ms)        ← Lab 2'den
Hedef trafik: 600 RPS

Gerekli pod = (600 / 200) × 1.5  = 4.5 → 5 pod
                          └── %50 headroom (spike + scale gecikmesi payı)
```

[docs/capacity-template.md](../docs/capacity-template.md) → "Kapasite hesabı" bölümünü doldur.

> 🎯 Neden 1.5×? %100 kullanımda çalışmazsın: scale-up gecikmesi, spike,
> pod restart anları için baş payı bırakırsın. %60-70 hedef kullanım yaygın pratik.

---

## 2) HPA'yı uygula (2 dk)

```bash
kubectl apply -f infra/hpa.yaml
kubectl get hpa
# NAME        REFERENCE              TARGETS         MINPODS  MAXPODS  REPLICAS
# order-svc   Deployment/order-svc   cpu: 5%/60%     2        8        2
```

`TARGETS` "unknown" gösteriyorsa metrics-server hazır değil — bekle/kontrol et:
```bash
kubectl top pods    # çalışıyorsa metrics-server OK
```

---

## 3) Hedef RPS gönder + scale'i izle (7 dk)

**Terminal 1 — yük (hedef RPS):**
```bash
k6 run -e RATE=600 k6-scripts/capacity-test.js
# 1dk ramp → 4dk steady 600 RPS → 30sn ramp-down
```

**Terminal 2 — HPA + pod izleme:**
```bash
kubectl get hpa -w
# REPLICAS sütunu 2 → 3 → 4 → 5 ... tırmanışını izle

# ayrı pencere:
watch -n2 'kubectl get pods -l app=order-svc; echo; kubectl top pods -l app=order-svc'
```

**Gözlemle ve not al:**
1. CPU %60'ı aşınca HPA kaç saniyede yeni pod istedi?
2. Yeni pod `Pending → ContainerCreating → Running → Ready` kaç saniyede oldu?
3. **Toplam scale-up süresi** (yük başladı → ekstra pod trafik alır oldu) = ?
4. O sürede p99 latency'ye ne oldu? (k6 çıktısı — geçici SLO ihlali olabilir)

| Ölçüm | Değer |
|-------|-------|
| Scale tetikleme gecikmesi | _____ sn |
| Pod Ready süresi | _____ sn |
| Toplam scale-up | _____ sn |
| Stabil replica sayısı | _____ |

---

## 4) Scale-down'ı izle (yük bitince)

k6 bitince yük düşer. HPA hemen küçültmez — `scaleDown.stabilizationWindowSeconds=60`
(flap önleme). ~1-2 dk sonra replica'lar teker teker düşer:

```bash
kubectl get hpa -w     # REPLICAS 5 → 4 → 3 → 2 (min'e kadar)
```

---

## 5) Tartışma (3 dk)

- **"Scale-up süresinde müşteri ne yaşar?"** → O ~30-60sn'de mevcut podlar
  doygun; p99 fırlar, belki 5xx. Reaktif scaling her zaman GEÇ kalır.
- **Proactive scaling neden önemli?** → Bilinen pattern'lerde (sabah trafiği,
  kampanya saati) önceden scale et (scheduled/predictive HPA, KEDA cron).
- **Neden CPU %60, %90 değil?** → %90 hedeflersen scale tetiklendiğinde zaten
  geç kalmışsındır; baş payı yok.
- **HPA limitleri:** image pull + uygulama warm-up yavaşsa HPA da yavaş.
  Çözüm: küçük image, hızlı readiness, pre-pulled image, daha yüksek min replica.

---

## Cleanup

```bash
kubectl delete -f infra/hpa.yaml          # HPA'yı kaldır (deployment 2 replica'da kalır)
kubectl scale deploy/order-svc --replicas=2
```

## Lab 4 çıktısı

- [ ] Saturation RPS'ten gerekli pod sayısı hesaplandı (headroom dahil)
- [ ] HPA uygulandı, `TARGETS` gerçek CPU gösterdi
- [ ] Hedef RPS altında REPLICAS otomatik arttı (canlı izlendi)
- [ ] Scale-up süresi ölçüldü; reaktif vs proactive scaling tartışıldı
- [ ] Scale-down gözlemlendi, cleanup yapıldı

➡️ Bitti! Kapanış ve test türleri özeti için [README → Kapanış](../README.md#kapanış--test-türleri-hangi-soruyu-cevaplar).
