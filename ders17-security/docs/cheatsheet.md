# Ders 17 — Cheatsheet

Workshop boyunca en sık ihtiyaç duyulan komutlar.

## kubectl temelleri

```bash
# Context'i bu cluster'a sabitle
kubectl config use-context kind-ders17-security

# Genel durum
kubectl get pods,svc,ingress
kubectl get pods -l app=order-svc
kubectl top pods                     # metrics-server gerekir

# Logları izle
kubectl logs -f deploy/order-svc
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=200

# Tek pod'a shell
kubectl exec -it deploy/order-svc -- sh
```

## Ingress / WAF

```bash
# Aktif ingress nedir?
kubectl get ingress
kubectl describe ingress security-lab

# Controller config'i (ModSecurity flag'leri burada)
kubectl -n ingress-nginx get cm ingress-nginx-controller -o yaml

# WAF alert'lerini gör
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller | grep -i modsecurity

# Belirli kural ID'sini ara (örn. SQLi rule)
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller | grep '942100'
```

## curl tarifleri

```bash
# Status code + Retry-After tek satırda
curl -s -o /dev/null -w "status=%{http_code} retry-after=%header{retry-after}\n" \
  http://localhost/orders

# Body + header birlikte gör
curl -i http://localhost/search?q=test

# JWT ile
TOKEN=$(./lab2-auth/get-token.sh)
curl -H "Authorization: Bearer $TOKEN" http://localhost/admin
```

## hey loadtest

```bash
# 100 istek, 20 paralel
hey -n 100 -c 20 http://localhost/orders

# Header'la
hey -n 500 -c 50 -H "Authorization: Bearer $TOKEN" http://localhost/admin

# POST JSON ile
hey -n 200 -c 10 -m POST -T application/json \
  -d '{"text":"test"}' http://localhost/comment

# Yoksa kur: brew install hey  (macOS)  |  go install github.com/rakyll/hey@latest
```

## JWT decode (lib yok, base64 ile)

```bash
TOKEN=$(./lab2-auth/get-token.sh)

# Header
echo "$TOKEN" | cut -d. -f1 | base64 -d 2>/dev/null
# {"alg":"HS256","typ":"JWT"}

# Payload
echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null
# {"sub":"admin","iat":...,"exp":...,"role":"admin"}

# jwt-cli varsa:
echo "$TOKEN" | jwt decode -
```

## URL-encoding cheats (saldırı testleri)

| Karakter | URL-encoded |
|---|---|
| `'` (single quote) | `%27` |
| `"` (double quote) | `%22` |
| (space) | `%20` veya `+` |
| `<` | `%3C` |
| `>` | `%3E` |
| `;` | `%3B` |
| `/` | `%2F` |
| `\n` | `%0A` |
| `=` | `%3D` |

Komut satırından encode:
```bash
python3 -c "import urllib.parse; print(urllib.parse.quote(\"' OR 1=1 --\"))"
# %27%20OR%201%3D1%20--
```

## Hızlı reset (lab'lar arası)

```bash
# Sadece ingress'i temizle (app çalışıyor kalsın)
kubectl delete ingress security-lab

# order-svc'yi default AUTH_MODE=none'a döndür (Lab 2 sonrası)
kubectl apply -f manifests/order-svc.yaml
```

## Tam teardown

```bash
./teardown.sh
# kind cluster 'ders17-security' silinir
```
