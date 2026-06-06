# Ders 15 — Deploy Stratejileri Lab

Kubernetes üzerinde **Rolling Update + Rollback**, **Canary (Argo Rollouts)** ve
**GitOps (ArgoCD + Gitea + Kustomize)** konularını hands-on çalışan örnek lab.

> Bu klasör derste işlenen konunun **örnek uygulamasıdır**. Her lab kendi
> README'sinde komut komut anlatılır; aşağıdaki **Kurulum** bölümünü bir kez
> yapıp sırayla lab'lara geçebilirsin.

## Lab'lar bir bakışta

| Lab | Süre | Konu | Öğrenilen |
|-----|------|------|-----------|
| [Lab 1](lab1-rolling/README.md) | 15 dk | Rolling Update + Rollback | Kademeli deploy, v1+v2 mix riski, `rollout undo` |
| [Lab 2](lab2-canary/README.md) | 15 dk | Canary (Argo Rollouts) | Adımlı trafik (%10→%100), abort/promote, AnalysisTemplate |
| [Lab 3](lab3-gitops/README.md) | 20 dk | GitOps (ArgoCD) | Git = source of truth, drift detection, rollback = `git revert` |

---

## Kurulum

Lab'lara başlamadan önce **bir kez** yapılır. `kind/create-cluster.sh` yalnızca
**altyapıyı** (kind cluster + ingress-nginx) kurar. Image build, controller kurulumu
gibi adımlar bilerek manuel — her komutu görerek ilerliyoruz.

### 1) Altyapı: kind cluster + ingress-nginx

```bash
cd ders15-deploy-strategies
./kind/create-cluster.sh

# Doğru cluster'da mıyız?
kubectl config current-context
# kind-ders15-deploy   ← böyle olmalı
```

### 2) Image build + cluster'a load (4 image: order/payment × v1/v2)

> ⚠️ `APP_VERSION` build-arg ile gömülür. `v1` ve `v2` image'ları AYNI app'in farklı
> davranışlarıdır (v2 cold-start 10sn) — Lab 1'de bunu gözlemliyoruz.

```bash
docker build -t order-svc:v1   --build-arg APP_VERSION=v1 ./app/order-svc
docker build -t order-svc:v2   --build-arg APP_VERSION=v2 ./app/order-svc
docker build -t payment-svc:v1 --build-arg APP_VERSION=v1 ./app/payment-svc
docker build -t payment-svc:v2 --build-arg APP_VERSION=v2 ./app/payment-svc

kind load docker-image order-svc:v1 order-svc:v2 payment-svc:v1 payment-svc:v2 \
  --name ders15-deploy
```

### 3) Argo Rollouts (Lab 2 için)

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f \
  https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
kubectl -n argo-rollouts wait --for=condition=available deploy/argo-rollouts --timeout=120s

# CLI plugin (host'ta brew ile)
brew install argoproj/tap/kubectl-argo-rollouts
kubectl argo rollouts version --short
```

### 4) ArgoCD (Lab 3 için)

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd wait --for=condition=available deploy --all --timeout=180s

# ⚠️ Bilinen sorun: ApplicationSet controller bazen CRD'siz başlar → CrashLoopBackOff.
# Lab'larda kullanmıyoruz, kapat:
kubectl -n argocd scale deploy/argocd-applicationset-controller --replicas=0
```

### 5) Smoke check

```bash
kubectl get pods -n argo-rollouts     # argo-rollouts Running
kubectl get pods -n argocd            # hepsi Running, applicationset-controller 0/0
```

Kurulum tamam → [Lab 1](lab1-rolling/README.md) ile başla.

---

## Yapı

```
ders15-deploy-strategies/
├── README.md             ← Bu dosya (kurulum + lab indeksi)
├── teardown.sh           ← kind cluster'ı sil
│
├── kind/
│   ├── cluster.yaml         ← kind config (port 80/443 mapping)
│   └── create-cluster.sh    ← TEK altyapı scripti (cluster + ingress)
│
├── app/
│   ├── order-svc/        ← FastAPI: /orders, /version (APP_VERSION build-arg ile v1/v2)
│   └── payment-svc/      ← FastAPI: yardımcı servis (topoloji için)
│
├── lab1-rolling/         ← Rolling update + rollback
├── lab2-canary/          ← Argo Rollouts canary (%10→%100, abort)
└── lab3-gitops/          ← ArgoCD + Gitea + Kustomize
```

## Tasarım kararı

- **Script sadece altyapı:** `kind/create-cluster.sh` yalnızca cluster + ingress
  kurar. Image build, controller kurulumu ve tüm `kubectl` komutları lab
  README'lerinde **manuel** — her adımı görerek öğrenmen için.
- **Ayrı kind cluster:** Bu lab kendi cluster'ını (`ders15-deploy`) oluşturur;
  başka cluster'larla (`ders17-security`, `ders18-perf`) çakışmaz.
- **Aynı app, v1/v2 image:** `APP_VERSION` build-arg ile aynı kod farklı davranır
  (v2 cold-start) — deploy stratejilerini gerçekçi gözlemleyebilmek için.

## Teardown

```bash
./teardown.sh   # kind cluster 'ders15-deploy' silinir
```

---

## Acil durum cheatsheet

```bash
# Pod neden çalışmıyor?
kubectl describe pod POD_NAME
kubectl logs POD_NAME --previous

# Image cluster'da yok mu?
docker images | grep -E "order-svc|payment-svc"
kind load docker-image IMAGE_NAME:TAG --name ders15-deploy

# ArgoCD sync olmuyor mu?
kubectl -n argocd logs deploy/argocd-repo-server --tail=30
kubectl -n argocd describe app order-svc | tail -20

# Tam reset
kind delete cluster --name ders15-deploy
./kind/create-cluster.sh   # ... ve Kurulum adımlarını tekrar yap
```
