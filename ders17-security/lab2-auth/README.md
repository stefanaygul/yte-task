# Lab 2 — Auth Load Karşılaştırma (15 dk)

**Amaç:** JWT validation'ın per-service maliyetini görmek; auth'u gateway'e taşıdığında
CPU yükünün nasıl düştüğünü ölçmek.

> Önkoşul: Lab 3 cleanup yapıldı, app deploy hâlâ duruyor.
>
> **metrics-server gerekli** — `kubectl top pods` çalışmıyorsa:
> ```bash
> kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
> # kind için TLS bypass gerekir:
> kubectl -n kube-system patch deploy metrics-server --type=json \
>   -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
> kubectl -n kube-system rollout status deploy/metrics-server
> ```

---

## 0) Ingress'i hazırla, başlangıçta sade routing

```bash
cd ders17-security/lab2-auth
kubectl apply -f ingress.yaml
```

---

## 1) JWT token al (2 dk)

```bash
./get-token.sh
# eyJhbGciOiJIUzI1NiIs.eyJzdWIiOiJhZG1pbiIsIm...

# Token'ı decode et — payload'a bak
TOKEN=$(./get-token.sh)
echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null
# {"sub":"admin","iat":...,"exp":...,"role":"admin"}
```

> **HMAC vs RSA**: Workshop'ta HMAC256 (HS256) kullanıyoruz çünkü tek secret yeter.
> Üretimde **RSA (RS256) veya ECDSA (ES256)** kullanın: doğrulayan tarafa sadece public
> key dağıtırsınız, secret tek noktada kalır (özel anahtar). HMAC'te secret kim varsa
> token da imzalayabilir → kompromise edilirse her şey biter.

---

## 2) Per-service mode: her pod kendi JWT'sini validate eder (4 dk)

```bash
kubectl apply -f deploy-jwt-local.yaml
kubectl rollout status deploy/order-svc

# Sanity: /admin token ile 200, token'sız 401
TOKEN=$(./get-token.sh)
curl -s -o /dev/null -w "with token:    %{http_code}\n" -H "Authorization: Bearer $TOKEN" http://localhost/admin
curl -s -o /dev/null -w "without token: %{http_code}\n" http://localhost/admin

# Loadtest — TEK terminalde
MODE=jwt-local ./loadtest-with-auth.sh

# Test BİTER BİTMEZ (CPU verisi taze olsun):
kubectl top pods -l app=order-svc
```

**Beklenen:** order-svc pod'larının CPU'su yüksek. Her istek için PyJWT verify
çalışıyor (HMAC hesabı + JSON parse). hey çıktısında requests/sec değerini not al.

---

## 3) Gateway mode: app crypto yapmıyor (4 dk)

```bash
kubectl apply -f deploy-jwt-gateway.yaml
kubectl rollout status deploy/order-svc

# Sanity: X-User-Id ile 200, header'sız 401
curl -s -o /dev/null -w "with header:    %{http_code}\n" -H "X-User-Id: admin" http://localhost/admin
curl -s -o /dev/null -w "without header: %{http_code}\n" http://localhost/admin

# Loadtest
MODE=jwt-gateway ./loadtest-with-auth.sh

# Hemen CPU
kubectl top pods -l app=order-svc
```

**Beklenen:** order-svc CPU belirgin düştü. Aynı request sayısı, ama app sadece
header okuyor → kripto yok. requests/sec değeri de yükselmiş olmalı (daha hızlı).

---

## 4) Karşılaştırma (5 dk)

İki test sonucunu yan yana koy:

| Metrik | jwt-local | jwt-gateway |
|---|---|---|
| order-svc CPU (toplam, 2 pod) | ~150-200m | ~50-80m |
| hey RPS | düşük | yüksek |
| hey p99 latency | yüksek | düşük |

**Ölçek senaryosu** — 50 mikroservis olsa:
- **Per-service:** 50 × 150m = **7.5 CPU core** sadece JWT validation için
- **Gateway:** 1 gateway × 300m = **0.3 CPU core** + backend'ler hemen hemen sıfır

**Trade-off:** Gateway tek başarısızlık noktası olur — high-availability gerekir,
gateway'in kendisi de horizontal scale edilmeli. "Zero trust" mimarilerde her servis
yine kendi token'ını doğrular; performans dengesi ihtiyaca göre kurulur.

---

## 5) Tartışma

- **"Service mesh (Istio/Linkerd) bu işi nasıl yapıyor?"** Sidecar proxy (Envoy) JWT
  validate eder, uygulamaya temiz request geçer — "gateway mode" pattern'inin pod-level
  versiyonu. Maliyet sidecar'da, ama cluster içinde dağıtılmış.
- **"JWT cache'lemek hile mi?"** Hayır — exp kontrolü ile çoğu validate cache hit
  olabilir. Production JWT lib'leri (auth0, jose) bunu yapıyor.
- **"Token revocation nasıl?"** JWT stateless → anında iptal yok. Short TTL (5-15dk) +
  refresh token + denylist (Redis) pattern'i.

---

## Cleanup

```bash
kubectl delete ingress security-lab
kubectl delete deploy order-svc
kubectl apply -f ../manifests/order-svc.yaml   # AUTH_MODE=none geri yükle
```
