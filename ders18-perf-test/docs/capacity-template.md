# Kapasite Planlama Şablonu

Bu şablonu lab'lar boyunca sen doldurursun. Her lab kendi bölümünü besler.
Sonunda elinde tek sayfalık bir **kapasite planı** olacak.

> Rakamlar donanıma göre değişir — kendi cluster'ından gelen değerleri yaz.

---

## 1. Baseline (Lab 1'den)

Komut: `k6 run k6-scripts/load-test.js` (100 VU, 2 dk)

| Metrik | Değer |
|--------|-------|
| Steady RPS | __________ /s |
| avg latency | __________ ms |
| p95 latency | __________ ms |
| p99 latency | __________ ms |
| error rate | __________ % |
| Pod sayısı (test sırasında) | __________ |

SLO tanımım:
- p99 < __________ ms
- error rate < __________ %

---

## 2. Saturation Point (Lab 2'den)

Komut: `k6 run k6-scripts/stress-test.js` (100→1000 VU)

| Ölçüm | DB=10ms | DB=100ms |
|-------|---------|----------|
| p99 ilk 500ms'i geçtiği VU | _______ | _______ |
| O andaki RPS | _______ | _______ |
| O andaki CPU (millicore) | _______ | _______ |
| O andaki memory | _______ | _______ |

**Bottleneck kararım** (birini işaretle):
- [ ] CPU-bound (CPU limit'e dayandı, latency CPU ile arttı)
- [ ] DB/IO-bound (DB latency artınca saturation düştü, CPU düşük kaldı)
- [ ] Başka: __________________________

**Tek pod kapasitesi:** 1 pod ≈ __________ RPS @ SLO
(2 pod ile test ettiysen: ölçülen saturation RPS ÷ pod sayısı)

---

## 3. Spike & Soak Bulguları (Lab 3'ten)

**Spike** (`spike-test.js`):
- Spike anında p99 tepe değeri: __________ ms
- Recovery time (normale dönüş): __________ sn
- Pod crash/restart oldu mu? ☐ Evet ☐ Hayır

**Soak** (`soak-test.js`, MEMORY_LEAK=true):
- Memory eğrisi: ☐ monoton artan (leak) ☐ sabit plato
- OOMKill gözlendi mi? ☐ Evet (RESTARTS: ___) ☐ Hayır
- MEMORY_LEAK=false ile fark: __________________________

---

## 4. Kapasite Hesabı (Lab 4'ten)

```
Tek pod kapasitesi (Lab 2)         : __________ RPS @ SLO
Hedef trafik (planlama)            : __________ RPS
Headroom çarpanı (spike + gecikme) : × 1.5   (gerekçe: scale-up geç kalır + ani yük)

Gerekli pod = (hedef / tek_pod) × 1.5
            = ( ______ / ______ ) × 1.5
            = __________ → yukarı yuvarla → __________ pod
```

**HPA ayarlarım:**
- minReplicas: __________
- maxReplicas: __________
- target CPU utilization: __________ %

---

## 5. HPA Gözlemi (Lab 4'ten)

Komut: `k6 run -e RATE=______ k6-scripts/capacity-test.js` + `kubectl get hpa -w`

| Ölçüm | Değer |
|-------|-------|
| Yük başlangıç → ilk scale event | __________ sn |
| Yeni pod Pending → Ready | __________ sn |
| Toplam scale-up süresi | __________ sn |
| Ulaşılan stabil replica | __________ |
| Scale sırasında p99 tepe | __________ ms |
| Yük bitti → scale-down başladı | __________ sn sonra |

---

## 6. Sonuç & Aksiyon

**Bu servis için kapasite planı (1 cümle):**
> Hedef ______ RPS için ______ pod (min ___ / max ___), target CPU %___.
> Bilinen bottleneck: ____________. İlk iyileştirme: ____________.

**Production'a taşırken yapılacaklar:**
- [ ] Soak test'i saatler boyunca koş (workshop'ta 5dk'ydı)
- [ ] Gerçek bağımlılıklarla (gerçek DB/cache) tekrar ölç
- [ ] CI/CD'ye threshold'lu smoke load test ekle (regression yakala)
- [ ] Proactive scaling: bilinen trafik pattern'i var mı? (scheduled/predictive)
- [ ] Alert: p99 SLO + saturation %80'e yaklaşınca uyarı
