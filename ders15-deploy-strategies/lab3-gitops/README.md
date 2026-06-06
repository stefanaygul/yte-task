# Lab 3 — GitOps (ArgoCD + Gitea + Kustomize)

**Süre:** 20 dakika
**Zorluk:** ⭐⭐
**Amaç:** Git'i "source of truth" yap, deploy = git commit, rollback = git revert. Cluster'da elle yapılan değişikliği otomatik geri al.

---

## Neden GitOps?

| Konvansiyonel CI/CD | GitOps |
|---|---|
| Pipeline cluster'a push'lar | Cluster repo'yu pull'lar |
| Cluster state'i izlemek zor | State = git history |
| Manuel kubectl değişiklikleri silent | Drift detection |
| Rollback = pipeline re-run | Rollback = `git revert` (PR review'la bile) |

**Source of Truth = git.** Cluster onu yansıtan, yenilenebilir bir cache'tir.

---

## Mimari

```
   ┌──────────────┐    git push    ┌────────────┐
   │  Sen (host)  ├───────────────▶│   Gitea    │
   └──────────────┘                │  (in-K8s)  │
                                   └──────┬─────┘
                                          │ pull (HEAD)
                                          ▼
                                   ┌────────────┐  kustomize build  ┌──────────────┐
                                   │  ArgoCD    │──────────────────▶│  Cluster     │
                                   │  (in-K8s)  │   apply           │  Resources   │
                                   └────────────┘                   └──────────────┘
```

- **Gitea** in-cluster git server (`gitea-http.gitea.svc.cluster.local:3000`)
- **ArgoCD** in-cluster GitOps controller
- **Kustomize** manifest yapısı: `base/` + `overlays/workshop/`

---

## Ön gereksinim

[README'deki Kurulum](../README.md#kurulum) yapıldıysa hazır:
- `argocd` namespace + ArgoCD pod'ları Running

> Gitea bu lab'a özgü — Adım 0'da kuruyoruz.

Kontrol:
```bash
kubectl -n argocd get pods
```

---

## Adım 0 — Gitea'yı kur (2 dk)

In-cluster git server. Bu lab dizininden çalıştır (sonraki adımlarda da buraya döneceğiz):

```bash
cd ders15-deploy-strategies/lab3-gitops
LAB3=$(pwd)          # bu dizini hatırla — aşağıda kullanacağız

kubectl apply -f gitea/gitea.yaml
kubectl apply -f gitea/ingress.yaml

# Gitea pod Running olana kadar bekle
kubectl -n gitea wait --for=condition=ready pod -l app=gitea --timeout=180s
kubectl -n gitea get pods
```

---

## Adım 1 — Gitea admin user oluştur (2 dk)

Gitea ayakta ama içi boş — kullanıcı ve repo yok.

```bash
# Pod adını al
GITEA_POD=$(kubectl -n gitea get pod -l app=gitea -o jsonpath='{.items[0].metadata.name}')
echo "Gitea pod: $GITEA_POD"

# Admin user oluştur
# NOT: gitea binary root'a izin vermez → `su git -c "..."` ile geçici user switch.
kubectl -n gitea exec -it "$GITEA_POD" -c gitea -- \
  su git -c "gitea admin user create \
    --admin \
    --username workshop \
    --password workshop123 \
    --email workshop@example.local \
    --must-change-password=false"
```

Beklenen: `New user 'workshop' has been successfully created!`

---

## Adım 2 — Repo oluştur (Gitea API) (2 dk)

```bash
# API çağrısını cluster içinden yap (extra port-forward gerekmez)
kubectl -n gitea exec "$GITEA_POD" -c gitea -- \
  curl -s -w "\nHTTP %{http_code}\n" \
    -u workshop:workshop123 \
    -H "Content-Type: application/json" \
    -X POST http://gitea-http.gitea.svc.cluster.local:3000/api/v1/user/repos \
    -d '{"name":"manifests","default_branch":"main","auto_init":true,"private":false}'
```

Beklenen: repo JSON + `HTTP 201`.

---

## Adım 3 — Port-forward aç (1 dk, terminal A açık tutulur)

Hem tarayıcıyla UI'a hem `git clone` için aynı port-forward'u kullanacağız.

**Terminal A:**
```bash
kubectl port-forward -n gitea svc/gitea-http 3000:3000
```

Tarayıcıda aç → `http://localhost:3000` → login: `workshop` / `workshop123`. `workshop/manifests` boş repo görünmeli.

---

## Adım 4 — Initial Kustomize manifest'lerini push et (3 dk)

**Terminal B:**
```bash
# Geçici çalışma alanı
mkdir -p ~/lab3-work && cd ~/lab3-work

# Repo'yu clone
git clone http://workshop:workshop123@localhost:3000/workshop/manifests.git
cd manifests

# Lab dizinindeki Kustomize tree'sini kopyala ($LAB3 = Adım 0'da kaydettiğin lab dizini)
cp -r "$LAB3"/manifests/* .

# Yapıyı incele
find . -type f
# .
# ./base/deployment.yaml
# ./base/service.yaml
# ./base/kustomization.yaml
# ./overlays/workshop/kustomization.yaml

# Local'de "ArgoCD ne uygulayacak" diye render et (DEBUGGING için kritik)
kubectl kustomize overlays/workshop/ | head -40

# Push
git config user.email "workshop@example.local"
git config user.name "workshop"
git add .
git commit -m "initial: order-svc v1 + payment-svc v1 (kustomize)"
git push origin main
```

Gitea UI'da repo'yu yenile → `base/`, `overlays/workshop/` görünür.

---

## Adım 5 — ArgoCD Application'ı kur (3 dk)

```bash
cd "$LAB3"          # Adım 0'da kaydettiğin lab3-gitops dizini

# Application CRD'sini cluster'a ver
kubectl apply -f application.yaml

# ArgoCD'nin repo'yu sync etmesini bekle
kubectl -n argocd get application order-svc
# (NAME=order-svc, SYNC STATUS ilk başta OutOfSync, sonra Synced; HEALTH=Healthy)

# Cluster'a uygulanan kaynakları gör
kubectl get deploy,svc,pod -l app.kubernetes.io/part-of=ders15-deploy-strategies
```

**ArgoCD UI** (opsiyonel ama çok faydalı):

**Terminal C:**
```bash
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

Initial admin password:
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

Tarayıcı → `https://localhost:8080` (cert uyarısını kabul et) → login `admin` / yukarıdaki password. `order-svc` application'ını gör — Synced & Healthy olmalı, kaynak graph'ı görünür.

---

## Adım 6 — Git commit ile deploy (v1 → v2) (3 dk)

İşte GitOps'un kalbi: değişikliği **Kustomize overlay'inde tek satırla** yap, commit + push, ArgoCD geri kalanı halletsin.

```bash
cd ~/lab3-work/manifests

# Image tag'ini v2 yap
sed -i '' 's/newTag: v1/newTag: v2/' overlays/workshop/kustomization.yaml

# Diff'i kontrol et
git diff overlays/workshop/kustomization.yaml

# Local'de değişikliği önceden render et
kubectl kustomize overlays/workshop/ | grep "image: order-svc"
# image: order-svc:v2  (×3 pod template)
# image: payment-svc:v2

# Commit + push
git add .
git commit -m "upgrade: order-svc v1 → v2, payment-svc v1 → v2"
git push origin main
```

ArgoCD UI'da gözlemle:
1. ~30 saniye içinde `OutOfSync` görünür (default poll interval 3 dakika, manuel sync ile hemen tetiklenir)
2. `kubectl -n argocd get app order-svc -w` ile izle
3. Sync → Healthy

Manuel sync tetikle (UI'da Sync butonu, ya da CLI):
```bash
# argocd CLI varsa
# argocd app sync order-svc

# Plain kubectl ile
kubectl -n argocd patch application order-svc --type merge \
  -p '{"operation":{"sync":{"revision":"HEAD"}}}'
```

Doğrula:
```bash
kubectl get deploy order-svc -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
# order-svc:v2
```

---

## Adım 7 — Drift detection (3 dk)

`syncPolicy.selfHeal: true` → cluster'da elle yapılan değişiklik otomatik geri alınır.

```bash
# Elle scale → 3 replica'dan 1'e indir
kubectl scale deployment/order-svc --replicas=1

# Hemen izle
kubectl get deploy order-svc -w
```

10-30 saniye içinde ArgoCD drift'i fark eder, replica sayısını **git'teki gibi 3'e döndürür**.

ArgoCD UI'da:
- Status: `OutOfSync` (kısa süre) → `Synced`
- Event'lerde: "Resource was modified, syncing back to desired state"

> 💡 **Çıkarım:** Git'te 3 yazıyorsa cluster'da 3 olur. "Geçici" elle değişiklik **yoktur**. Tüm değişiklikler git'ten geçer → audit trail, code review, rollback hep kazançtır.

---

## Adım 8 — Rollback = `git revert` (3 dk)

```bash
cd ~/lab3-work/manifests

# Son commit'i (v2 yükseltmesi) tersine çevir → yeni bir commit oluşur
git revert HEAD --no-edit

# Diff'i gör (newTag: v2 → v1 geri döndü)
git show HEAD

# Push
git push origin main
```

ArgoCD birkaç saniye içinde sync → v1'e döner:
```bash
kubectl get deploy order-svc -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
# order-svc:v1
```

> 💡 **Çıkarım:** Rollback artık bir "deploy" değil. Bir **commit**, PR review'dan geçebilir, tarihçede görünür, başka bir geliştirici "bu rollback neden yapıldı" diye git log'a bakar. Production'da yanlış deploy'u geri almak için artık "deploy aracı"na değil, "git"e dokunuyorsun.

---

## Tartışma (2 dk)

**S1: Kustomize neden plain YAML'dan iyi?**
- Tek satır diff'le environment fark yönetimi (dev/staging/prod overlay'leri)
- Image tag merkezi (`images:` bloğu) — DRY
- `kubectl kustomize` ile preview → ArgoCD'siz debug

**S2: `automated.prune: true` ne yapar?**
- Git'te bir resource silinirse cluster'dan da silinir. Default `false` — kazara silmemek için açmadan önce dikkat.

**S3: `selfHeal: false` olsa ne olur?**
- ArgoCD drift'i raporlar ama düzeltmez. UI'da `OutOfSync` görünür, manuel `argocd app sync` gerekir. Bazı ekipler "hotfix penceresi" için bunu tercih eder.

**S4: ArgoCD vs Flux?**
- ArgoCD: zengin UI, multi-cluster yönetimi UI'da, Application CRD-merkezli.
- Flux: UI yok (3rd party var), Helm/Kustomize-native, GitOps Toolkit (notification/image automation modüler).
- Tercih genelde ekip kültürüne bağlı.

---

## Temizlik

```bash
# Application'ı sil (finalizer sayesinde child resource'lar da silinir)
kubectl delete -f application.yaml

# Çalışma alanını sil
rm -rf ~/lab3-work
```

Gitea ve ArgoCD'yi de tamamen kaldırmak istersen `teardown.sh` çalıştır.

---

## Komut özeti

```bash
# ArgoCD
kubectl -n argocd get application
kubectl -n argocd get app NAME -w
kubectl -n argocd patch app NAME --type merge -p '{"operation":{"sync":{"revision":"HEAD"}}}'

# Kustomize (local preview)
kubectl kustomize manifests/overlays/workshop/

# Gitea
kubectl -n gitea exec POD -c gitea -- su git -c "gitea admin user list"
```
