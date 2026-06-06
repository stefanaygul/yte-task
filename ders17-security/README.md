# Ders 17 — Güvenlik Lab

Kubernetes üzerinde **Rate Limiting**, **Auth Load** ve **WAF** (ModSecurity + OWASP CRS)
konularını hands-on çalışan örnek lab.

> Bu klasör derste işlenen konunun **örnek uygulamasıdır**. Aşağıdaki **Kurulum**
> bölümünü bir kez yapıp lab'lara önerilen sırayla geç. Her lab kendi README'sinde
> komut komut anlatılır.

## Lab'lar bir bakışta

Önerilen sıra **Lab 1 → Lab 3 → Lab 2** (her lab bir öncekinin ingress'ini temizler;
app pod'ları açık kalır):

| Sıra | Lab | Süre | Konu | Öğrenilen |
|------|-----|------|------|-----------|
| 1 | [Lab 1](lab1-ratelimit/README.md) | 15 dk | Rate Limiting | NGINX `limit-rps`, 429, controller metrikleri |
| 2 | [Lab 3](lab3-waf/README.md) | 15 dk | WAF | ModSecurity off/DetectionOnly/Block, false positive |
| 3 | [Lab 2](lab2-auth/README.md) | 15 dk | Auth Load | JWT per-service vs gateway, CPU karşılaştırması |

---

## Kurulum

`kind/create-cluster.sh` yalnızca **altyapıyı** (kind cluster + ingress-nginx,
ModSecurity destekli) kurar. Image build ve app deploy gibi adımlar bilerek manuel —
her komutu görerek ilerliyoruz.

### 1) Altyapı: kind cluster + ingress-nginx (ModSecurity)

```bash
cd ders17-security
./kind/create-cluster.sh

# Doğru cluster'da mıyız?
kubectl config current-context
# kind-ders17-security   ← böyle olmalı

# Smoke: ingress controller ayakta mı?
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/
# 404 (default backend) → controller çalışıyor
```

### 2) Image build + cluster'a load

```bash
# order-svc: tüm endpoint'ler burada (/orders, /login, /admin, /search, /comment)
docker build -t order-svc:latest ./app/order-svc
# payment-svc: minimal yardımcı servis (topoloji için)
docker build -t payment-svc:latest ./app/payment-svc

kind load docker-image order-svc:latest payment-svc:latest --name ders17-security
```

### 3) App deploy

```bash
kubectl apply -f manifests/order-svc.yaml      # AUTH_MODE=none
kubectl apply -f manifests/payment-svc.yaml

kubectl rollout status deploy/order-svc
kubectl rollout status deploy/payment-svc
kubectl get pods       # order-svc + payment-svc 2/2 Ready
```

### 4) Sanity check (Lab'lar Ingress üzerinden — port-forward gerekmez)

```bash
kubectl exec deploy/order-svc -- python3 -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8001/health').read())"
# b'{"status":"ok"}'
```

> Ingress üzerinden test Lab 1'in ilk adımı (önce `ingress-no-limit.yaml` apply'lanır).

Kurulum tamam → [Lab 1](lab1-ratelimit/README.md) ile başla.

---

## Yapı

```
ders17-security/
├── README.md             ← Bu dosya (kurulum + lab indeksi)
├── teardown.sh           ← kind cluster'ı sil
│
├── kind/
│   ├── cluster.yaml         ← kind config (port 80/443 mapping)
│   └── create-cluster.sh    ← TEK altyapı scripti (cluster + ingress + ModSecurity)
│
├── app/
│   ├── order-svc/        ← FastAPI: /orders, /login, /admin, /search, /comment
│   └── payment-svc/      ← FastAPI: /health, /pay (yardımcı servis)
│
├── manifests/            ← Base deployment + service YAML'ları
│   ├── order-svc.yaml       (AUTH_MODE=none)
│   └── payment-svc.yaml
│
├── lab1-ratelimit/       ← NGINX limit-rps annotation'ları
├── lab2-auth/            ← AUTH_MODE=jwt-local vs jwt-gateway
├── lab3-waf/             ← ModSecurity off / DetectionOnly / On
│
└── docs/
    └── cheatsheet.md     ← kubectl, curl, hey, JWT decode reçeteleri
```

## Tasarım kararı

- **Script sadece altyapı:** `kind/create-cluster.sh` yalnızca cluster + ingress
  controller kurar. Image build, app deploy, ingress apply gibi öğretilen komutlar
  **lab README'lerinde manuel** çalıştırılır — her adımı görerek öğrenmen için.
- **Ayrı kind cluster:** Bu lab kendi cluster'ını (`ders17-security`) oluşturur;
  başka cluster'larla (`ders15-deploy`, `ders18-perf`) çakışmaz.
- **Aynı app, env var override:** AUTH_MODE deploy YAML'ları aynı image'ı tekrar deploy
  eder, sadece env değişir. Image rebuild gerekmez.

---

## Kapanış — Defense in depth

Üç lab boyunca gördüğümüz katmanlar tek bir resmin parçaları:

```
┌─ Network ──────────────────────────────────────┐
│  Rate limit (Lab 1)       NetworkPolicy        │
│  WAF (Lab 3)              mTLS / service mesh  │
├─ Auth ─────────────────────────────────────────┤
│  Gateway JWT (Lab 2)      Per-service token    │
│  Short TTL + refresh      Revocation list      │
├─ App ──────────────────────────────────────────┤
│  Parametrized query       Input validation     │
│  Output encoding          CSP / SameSite       │
├─ Data ─────────────────────────────────────────┤
│  Encryption at rest       Secret manager       │
│  Least privilege IAM      Audit log            │
└────────────────────────────────────────────────┘
```

Tartışma soruları:
1. Şu an çalıştığınız projede bu katmanlardan hangisi var, hangisi yok?
2. Rate limit'i Ingress'te mi, app'te mi yaparsınız? Neden?
3. WAF'ı production'a açmadan önce hangi tuzaklara dikkat edersiniz?
4. JWT secret'ı nerede saklıyorsunuz? Rotation süreciniz var mı?

## Teardown

```bash
./teardown.sh   # kind cluster 'ders17-security' silinir
```

---

## Bilinen gotcha'lar

| Sorun | Çözüm |
|-------|-------|
| `modsecurity-snippet` annotation görmezden geliniyor | `create-cluster.sh` `allow-snippet-annotations=true` ve `annotations-risk-level=Critical` set ediyor — controller restart şart. Manuel yaparsan unutma. |
| `kubectl top pods` "metrics not available" | metrics-server kurulu değil. Lab 2 README'sindeki komutu çalıştır (kind için `--kubelet-insecure-tls` patch'i şart). |
| `hey` yok | Loadtest scriptleri otomatik curl fallback'e geçer. Daha temiz çıktı için: `brew install hey` |
| Port 80 zaten kullanılıyor (host) | Başka kind cluster'larında 80/443 mapping var mı? `docker ps` ile kontrol et, gerekirse o cluster'ı durdur. |
| ModSecurity Block mode'da meşru istek de bloklanıyor (false positive) | Bu **özellik**, bug değil — Lab 3 Adım 4 bunu kasten gösteriyor. |
