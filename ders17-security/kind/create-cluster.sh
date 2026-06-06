#!/usr/bin/env bash
# Ders 17 Güvenlik Lab — kind cluster + ingress-nginx (ModSecurity destekli).
#
# Bu script YALNIZCA ALTYAPI kurar:
#   1) kind cluster (ders17-security)
#   2) ingress-nginx controller (kind variant)
#   3) ModSecurity + OWASP CRS'i controller config'inde aç
#   4) Snippet annotation'larına izin ver (modsecurity-snippet için şart)
#
# Öğretilen komutlar (kubectl apply, docker build, hey, vs.) bu scriptte YOK —
# onlar README.md "Kurulum" bölümünde ve lab README'lerinde manuel çalıştırılır.
set -euo pipefail

CLUSTER_NAME="ders17-security"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ingress-nginx controller v1.11.3 — ModSecurity v3 + OWASP CRS dahili
INGRESS_NGINX_VERSION="controller-v1.11.3"
INGRESS_NGINX_MANIFEST="https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_NGINX_VERSION}/deploy/static/provider/kind/deploy.yaml"

# ---- 1. Prerequisite check ----
for cmd in kind kubectl docker curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Eksik: $cmd kurulu değil"
    exit 1
  fi
done
echo "✅ Prerequisite OK (kind, kubectl, docker, curl)"

# ---- 2. Cluster oluştur ----
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "ℹ️  Cluster '${CLUSTER_NAME}' zaten var — yeniden oluşturma atlanıyor"
  echo "   Sıfırdan: kind delete cluster --name ${CLUSTER_NAME}"
else
  echo "🚧 kind cluster oluşturuluyor: ${CLUSTER_NAME}"
  kind create cluster --config "${SCRIPT_DIR}/cluster.yaml"
fi

kubectl config use-context "kind-${CLUSTER_NAME}"

# ---- 3. ingress-nginx (kind variant) ----
echo "🚧 ingress-nginx kuruluyor (${INGRESS_NGINX_VERSION})"
kubectl apply -f "${INGRESS_NGINX_MANIFEST}"

echo "⏳ ingress-nginx admission Job'unun bitmesi bekleniyor..."
# Job tamamlanmadan controller pod admission webhook'unu kullanamaz; wait.
kubectl -n ingress-nginx wait \
  --for=condition=complete job \
  -l app.kubernetes.io/component=admission-webhook \
  --timeout=180s 2>/dev/null || true

echo "⏳ ingress-nginx controller Ready bekleniyor..."
kubectl -n ingress-nginx wait \
  --for=condition=ready pod \
  -l app.kubernetes.io/component=controller \
  --timeout=180s

# ---- 4. ModSecurity + snippet annotation'larını aç ----
#
# enable-modsecurity         → /etc/nginx/modsecurity/modsecurity.conf yüklenir
# enable-owasp-modsecurity-crs → OWASP Core Rule Set yüklenir
# allow-snippet-annotations  → ingress'lerde modsecurity-snippet kullanılabilsin
#                              (default false; security gerekçesiyle kapalı)
# annotations-risk-level     → v1.10+ snippet "Critical" risk seviyesinde sayılıyor;
#                              workshop için aç
# limit-req-status-code      → rate limit aşıldığında NGINX default 503 yerine
#                              standart 429 dönsün (ingress annotation DEĞİL,
#                              cluster-wide ConfigMap field'ı)
echo "🛡️  ModSecurity + OWASP CRS + snippet annotation'ları aktif ediliyor"
kubectl -n ingress-nginx patch configmap ingress-nginx-controller \
  --type merge \
  --patch '{"data":{
    "enable-modsecurity":"true",
    "enable-owasp-modsecurity-crs":"true",
    "allow-snippet-annotations":"true",
    "annotations-risk-level":"Critical",
    "limit-req-status-code":"429"
  }}'

echo "♻️  Controller restart (configmap değişti)"
kubectl -n ingress-nginx rollout restart deploy/ingress-nginx-controller
kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=180s

# ---- 5. Smoke test ----
echo "🧪 Smoke test: http://localhost → controller'a ulaşıyor mu?"
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ || echo "FAIL")
if [ "${HTTP_CODE}" = "404" ]; then
  echo "✅ ingress-nginx hazır (http://localhost → 404 default backend, beklendiği gibi)"
else
  echo "⚠️  Beklenmedik smoke test sonucu: ${HTTP_CODE}"
  echo "    Controller pod loglarını kontrol et:"
  echo "    kubectl logs -n ingress-nginx deploy/ingress-nginx-controller"
fi

cat <<EOF

╔══════════════════════════════════════════════════════════════════╗
║  ✅ Altyapı hazır: ${CLUSTER_NAME}
╠══════════════════════════════════════════════════════════════════╣
║  Cluster context: kind-${CLUSTER_NAME}
║  Ingress entry:   http://localhost   (host port 80 → cluster 80)
║  ModSecurity:     açık (DetectionOnly default; ingress annotation
║                   ile per-ingress override yapılır)
║
║  SIRADAKİ ADIM: README.md → "Kurulum"
║    1) Docker image'ları manuel build et
║    2) kind load ile cluster'a yükle
║    3) Manifest'leri manuel apply et
╚══════════════════════════════════════════════════════════════════╝

EOF
