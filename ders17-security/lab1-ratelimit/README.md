# Lab 1 — Rate Limiting (15 dk)

**Amaç:** NGINX Ingress'e rate limit ekle, 429 cevabını gör, NGINX metric'lerinden izle.

> Önkoşul: [README'deki Kurulum](../README.md#kurulum) tamam olmalı.
> Yani `order-svc` ve `payment-svc` çalışıyor, Ingress Controller ModSecurity destekli kuruldu.

---

## 1) Rate limit YOK — tüm trafik geçer (3 dk)

```bash
cd ders17-security/lab1-ratelimit

kubectl apply -f ingress-no-limit.yaml
# Ingress'in IP/host'unu al
kubectl get ingress security-lab

# Smoke test
curl -s http://localhost/orders | jq .

# Loadtest
./loadtest.sh
```

**Beklenen:** 100 request, hepsi 200. (hey çıktısında `[200] 100 responses`)

---

## 2) Rate limit EKLE (3 dk)

```bash
kubectl apply -f ingress-with-limit.yaml

# Annotation'lar ne diyor?
kubectl get ingress security-lab -o yaml | grep -A 3 annotations
```

Eklediğimiz annotation'lar:
- `limit-rps: "5"` → IP başına saniyede 5 request
- `limit-burst-multiplier: "2"` → burst toleransı = 5 × 2 = 10 request

> **Status code tuzağı:** NGINX rate limit aşılınca default **503** döner.
> Standart "429 Too Many Requests" dönmesi için `limit-req-status-code: "429"`
> ayarı **ingress annotation değil**, cluster-wide ConfigMap field'ıdır.
> Bu workshop'ta `create-cluster.sh` bunu ConfigMap'e yazıyor — eğer kendi
> cluster'ında 503 görüyorsan:
> ```bash
> kubectl -n ingress-nginx patch configmap ingress-nginx-controller \
>   --type merge --patch '{"data":{"limit-req-status-code":"429"}}'
> kubectl -n ingress-nginx rollout restart deploy/ingress-nginx-controller
> ```

---

## 3) Aynı loadtest — 429 gör (3 dk)

```bash
./loadtest.sh
```

**Beklenen:** ~10 başarı, ~90 fail (429). hey çıktısında status code dağılımı net görünür:
```
Status code distribution:
  [200]  10 responses
  [429]  90 responses
```

> **Neden tam 10/90 değil?** Burst bucket'ı baştan dolu, ilk 10 hızla geçer.
> Sonraki saniyelerde bucket saniyede 5 token doldurduğu için bazen birkaç ek istek
> geçer. Loadtest süresi ne kadar uzunsa o kadar başarılı geçer.

---

## 4) Response header'ları incele (3 dk)

```bash
# Tek tek curl — hem 200 hem 429 yakala
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "status=%{http_code} retry-after=%header{retry-after}\n" \
    http://localhost/orders
done
```

Sorular:
- 429 response'ta `Retry-After` header var mı?
- Response body ne diyor? (`curl -v http://localhost/orders` ile bak)
- `X-RateLimit-*` header'ı var mı? (NGINX Ingress default'ta YOK — bunu kendiniz
  eklemeniz gerekir, ileri konu.)

---

## 5) Monitoring — NGINX Ingress metric'leri (3 dk)

```bash
# Kind variant'ta ayrı metrics servisi YOK — doğrudan controller deployment'ına
# port-forward at (containerPort 10254 expose edilmiş).
kubectl port-forward -n ingress-nginx deploy/ingress-nginx-controller 10254:10254 &
PF_PID=$!
sleep 1

# 429'ları say
curl -s http://localhost:10254/metrics | grep 'nginx_ingress_controller_requests' | grep 'status="429"'

# Cleanup
kill $PF_PID
```

**Beklenen:** `nginx_ingress_controller_requests{...status="429"...} 90` benzeri bir satır.

---

## Tartışma

- **"IP bazlı limit NAT arkasında sorun yaratır."** Bir kurumdan tüm kullanıcılar tek IP
  ile geliyorsa hep birlikte limitlenirler. Çözüm: `X-Forwarded-For` üzerinden gerçek IP
  + kullanıcı/API key bazlı limit (`limit-req-zone $http_x_api_key zone=...`).

- **"Rate limit değerini nasıl belirlersiniz?"** Önce gözlemle: normal trafik p95/p99
  RPS'i nedir? Limit'i ortalamanın 2-3 katı koy. Çok düşük → meşru kullanıcı, çok yüksek
  → DoS koruması işe yaramaz.

- **"Rate limit nerede olmalı: Ingress mi, uygulama mı, ikisi de mi?"** Defense in depth:
  Ingress kaba (IP/path bazlı) + uygulama ince (kullanıcı/feature bazlı).

---

## Cleanup (Lab 3'e geçmeden önce)

```bash
# Ingress'i sil — Lab 3 kendi ingress'ini apply edecek
kubectl delete ingress security-lab
```
