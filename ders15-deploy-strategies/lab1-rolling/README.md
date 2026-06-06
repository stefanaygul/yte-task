# Lab 1 — Rolling Update + Rollback

**Süre:** 15 dakika
**Zorluk:** ⭐
**Amaç:** Kubernetes'in default rolling update mekanizmasını gözlemlemek, sorunlu bir deploy'u rollback etmek.

---

## Senaryo

`order-svc v1` production'da çalışıyor. Yeni `v2` versiyonunu deploy ediyoruz, ama v2'de bir performans sorunu var: cold start 10 saniye sürüyor (gerçek hayatta: yavaş cache warm-up, lazy DB connection pool, vb).

Ne göreceğiz:
1. Rolling update sırasında v1 ve v2 **aynı anda** trafik alıyor.
2. Sorunlu v2 yüzünden deploy yavaşlıyor → tespit ediyoruz.
3. `kubectl rollout undo` ile saniyeler içinde v1'e geri dönüyoruz.

---

## Adım 1 — Başlangıç durumunu kur (2 dk)

```bash
# Lab 1 başlangıç deployment'ı (v1) + service'ler
kubectl apply -f deploy-v1.yaml
kubectl apply -f service.yaml

# Pod'lar Running + Ready olana kadar bekle
kubectl get pods -l app=order-svc -w
# (Ctrl+C ile çık, hepsi 1/1 Ready olmalı)
```

İki ayrı terminal aç:

**Terminal A — pod'ları izle:**
```bash
kubectl get pods -l app=order-svc -w
```

**Terminal B — port-forward + curl loop:**
```bash
# Port-forward (background)
kubectl port-forward svc/order-svc 8001:8001 &

# Versiyon izleyici
./watch-version.sh
```

Şu anda her response `"version": "v1"` dönmeli.

---

## Adım 2 — v2 deploy et (3 dk)

**Terminal C** — yeni terminal aç ve deploy et:

```bash
kubectl apply -f deploy-v2.yaml
```

> ⚠️ **Neden `apply`, neden `kubectl set image` değil?**
> Bu lab'da v1/v2 farkı — cold start, `/orders`'taki `discount` alanı ve `version=v2`
> pod label'ı — image tag'ine değil **env var + label'a** bağlı (`APP_VERSION`,
> `STARTUP_DELAY_SECONDS`). `kubectl set image ... :v2` sadece image tag'ini değiştirir;
> env'ler v1'de kalır → yeni pod hâlâ v1 gibi davranır (10sn cold start yok, `/version`
> hâlâ `v1`) **ve** `version=v2` label'ı hiç oluşmaz, dolayısıyla Adım 3'teki
> `-l version=v2` sorguları boş döner. `apply -f deploy-v2.yaml` image + env + label'ı
> birlikte günceller — bu yüzden doğru yöntem bu.

Hemen Terminal A ve B'ye bak:

- **Terminal A**: yeni pod (v2) `ContainerCreating` → `Running` → `0/1 Not Ready` (10s bekle) → `1/1 Ready`. Sonra eski v1 pod'lardan biri Terminating.
- **Terminal B**: response'ların bir kısmı `v1`, bir kısmı `v2`. **Aynı anda iki versiyon trafik alıyor.**

```bash
# Rollout durumunu izle (bloklayıcı — bittiğinde döner)
kubectl rollout status deployment/order-svc
```

Beklenen: deployment ~30-40 saniyede tamamlanır (her v2 pod'u 10s readiness bekliyor).

---

## Adım 3 — "Sorun var!" anı (3 dk)

Diyelim ki v2'nin bu yavaşlığı production'da kabul edilemez. Tanı koyalım:

```bash
# Pod detayını oku — readiness fail olaylarını gör
kubectl describe pod -l app=order-svc,version=v2 | grep -A 5 "Readiness"

# Logları oku
kubectl logs -l app=order-svc,version=v2 --tail=20
# Beklenen: "⏳ Startup delay: 10s (cold start simülasyonu)"
```

**Tartışma:** prod'da bu 10 saniyelik gecikmeyi ne tetikleyebilir?
- Yeni eklenen Redis cache warm-up
- Lazy initialize edilen connection pool
- Büyük bir config dosyasının disk'ten okunması
- ML modeli yüklemesi

---

## Adım 4 — Rollback yap (3 dk)

Production'da panic yapmadan v1'e geri dön:

```bash
# Son deploy'u geri al — bir önceki revision'a döner
kubectl rollout undo deployment/order-svc

# Geri dönüşü izle
kubectl rollout status deployment/order-svc
```

Terminal B'de `v2 → v1` geçişini gör. **Saniyeler içinde** v1'e döndük.

```bash
# Revision history'yi gör
kubectl rollout history deployment/order-svc

# Belirli bir revision'a dön (örn: revision 1)
# kubectl rollout undo deployment/order-svc --to-revision=1

# Bir revision'ın detayı
kubectl rollout history deployment/order-svc --revision=2
```

> 💡 **Not:** `revisionHistoryLimit: 5` ayarı sayesinde son 5 revision saklanıyor. Default 10'dur. Çok yüksek tutmak etcd'yi şişirir.

---

## Adım 5 — Tartışma (4 dk)

**S1: Rolling update sırasında v1 ve v2 aynı anda çalıştı. Bu neden tehlikeli olabilir?**

İpuçları:
- v2 API breaking change içeriyorsa (yeni alan, kaldırılmış alan), client'lar inconsistent response alır.
- Database migration gerektiren değişiklikler tehlikeli — v1 ve v2 aynı schema'ya bakar.
- Session affinity yoksa kullanıcı bir istekte v1'e, sonrakinde v2'ye düşebilir.

**S2: v2'de `/orders` response'una `discount` alanı eklendi. v1 client bunu görür mü?**

Test edelim:
```bash
# v2 pod'a düş
kubectl exec -it $(kubectl get pod -l version=v2 -o name | head -1) -- \
  curl -s localhost:8001/orders
```
Cevap: v1 client bilinmeyen alanı yok sayar (genelde) → ileri uyumlu (forward-compatible) değişiklikler güvenli.

**S3: `maxUnavailable: 0` vs `maxUnavailable: 1` farkı?**

| Ayar | Davranış | Ne zaman kullanılır |
|------|----------|---------------------|
| `maxUnavailable: 0` | Sıfır downtime, eski pod yenisi hazır olana kadar düşmez | Production, kritik servisler |
| `maxUnavailable: 1` | Daha hızlı deploy, ama 1 pod kapasite kaybı olur | Resource kısıtlı ortam, batch job'lar |

**S4: `kubectl rollout undo` neyi geri alıyor? ConfigMap değişikliği de geri alınır mı?**

Cevap: **Hayır.** Sadece Deployment spec'i geri alınır. ConfigMap, Secret, vb. ayrıca yönetilmeli (GitOps'la — Lab 3'te göreceğiz).

---

## Temizlik

Lab 2'ye geçmeden önce:

```bash
kubectl delete -f deploy-v1.yaml
kubectl delete -f service.yaml
# Background port-forward'ı kapat
kill %1 2>/dev/null || true
```

---

## Kısa komut özeti

```bash
kubectl apply -f deploy-v2.yaml                  # bu lab: image + env + label birlikte
# kubectl set image deploy/order-svc order-svc=order-svc:v2   # genel; sadece image tag'i değiştirir
kubectl rollout status deployment/order-svc
kubectl rollout history deployment/order-svc
kubectl rollout undo deployment/order-svc
kubectl rollout undo deployment/order-svc --to-revision=N
kubectl rollout pause deployment/order-svc       # geçici durdur
kubectl rollout resume deployment/order-svc      # devam et
```
