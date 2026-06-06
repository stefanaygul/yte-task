#!/usr/bin/env bash
# Ders 15 Deploy Strategies — kind cluster + ingress-nginx kurulumu.
#
# Bu script yalnızca ALTYAPI kurar (cluster + ingress controller).
# Workshop boyunca öğrenilen komutlar (kubectl apply, set image, vs.)
# bu scriptte YOK — onlar lab README'lerinde manuel olarak çalıştırılır.
set -euo pipefail

CLUSTER_NAME="ders15-deploy"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---- 1. Prerequisite check ----
for cmd in kind kubectl docker; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Eksik: $cmd kurulu değil"
    exit 1
  fi
done
echo "✅ Prerequisite check OK (kind, kubectl, docker)"

# ---- 2. Cluster oluştur ----
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "ℹ️  Cluster '${CLUSTER_NAME}' zaten var — yeniden oluşturma atlanıyor"
  echo "   Sıfırdan başlamak için önce: kind delete cluster --name ${CLUSTER_NAME}"
else
  echo "🚧 kind cluster oluşturuluyor: ${CLUSTER_NAME}"
  kind create cluster --config "${SCRIPT_DIR}/cluster.yaml"
fi

# Context'i bu cluster'a çevir (paralel cluster'lar varsa karışmasın)
kubectl config use-context "kind-${CLUSTER_NAME}"

# ---- 3. ingress-nginx kur (kind variant) ----
# https://kind.sigs.k8s.io/docs/user/ingress/#ingress-nginx
echo "🚧 ingress-nginx kuruluyor (kind variant)"
kubectl apply -f \
  https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo "⏳ ingress-nginx controller Ready bekleniyor..."
kubectl -n ingress-nginx wait \
  --for=condition=ready pod \
  -l app.kubernetes.io/component=controller \
  --timeout=180s

# ---- 4. Smoke test ----
echo "🧪 Smoke test: ingress-nginx host'tan erişilebilir mi?"
# Default 404 dönmeli — bu controller çalışıyor demektir
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ || echo "FAIL")
if [ "${HTTP_CODE}" = "404" ]; then
  echo "✅ ingress-nginx hazır (http://localhost → 404 default backend, beklendiği gibi)"
else
  echo "⚠️  ingress smoke test beklenmedik sonuç: ${HTTP_CODE}"
fi

# ---- 5. Özet ----
cat <<EOF

╔══════════════════════════════════════════════════════════════════╗
║  Cluster hazır: ${CLUSTER_NAME}
╠══════════════════════════════════════════════════════════════════╣
║  Context:    kind-${CLUSTER_NAME}
║  Ingress:    http://*.localtest.me  (örn: http://gitea.localtest.me)
║                                                                    ║
║  Sıradaki adım: README.md → "Kurulum"                              ║
║    image build + kind load + Argo Rollouts + ArgoCD               ║
╚══════════════════════════════════════════════════════════════════╝

EOF
