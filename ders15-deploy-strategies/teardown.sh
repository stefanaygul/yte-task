#!/usr/bin/env bash
# Ders 15 Deploy Strategies — teardown
#
# Default: kind cluster sil + lab çalışma alanını sil
# --all  : yukarıdakilere ek olarak workshop Docker image'larını da sil
#
# Idempotent: hiçbir şey yoksa hata vermez, sessizce geçer.
set -uo pipefail

CLUSTER_NAME="ders15-deploy"
WORK_DIR="${HOME}/lab3-work"
DELETE_IMAGES="false"

# ---- Argümanlar ----
if [ "${1:-}" = "--all" ]; then
  DELETE_IMAGES="true"
fi

echo "🧹 Ders 15 Deploy Strategies — teardown"
echo ""

# ---- 1. kind cluster ----
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "🗑  kind cluster siliniyor: ${CLUSTER_NAME}"
  kind delete cluster --name "${CLUSTER_NAME}"
  echo "✅ Cluster silindi"
else
  echo "ℹ️  Cluster '${CLUSTER_NAME}' zaten yok — atlandı"
fi

# ---- 2. Lab çalışma alanı ----
if [ -d "${WORK_DIR}" ]; then
  echo "🗑  Çalışma alanı siliniyor: ${WORK_DIR}"
  rm -rf "${WORK_DIR}"
  echo "✅ Çalışma alanı silindi"
else
  echo "ℹ️  Çalışma alanı ${WORK_DIR} yok — atlandı"
fi

# ---- 3. Docker image'lar (opsiyonel) ----
if [ "${DELETE_IMAGES}" = "true" ]; then
  echo "🗑  Workshop image'ları siliniyor (--all geçildi)"
  for img in order-svc:v1 order-svc:v2 payment-svc:v1 payment-svc:v2; do
    if docker image inspect "${img}" >/dev/null 2>&1; then
      docker rmi "${img}" >/dev/null
      echo "   ✅ ${img}"
    else
      echo "   ℹ️  ${img} zaten yok"
    fi
  done
else
  echo ""
  echo "ℹ️  Docker image'lar kalıyor (order-svc, payment-svc :v1/:v2)"
  echo "   Onları da silmek için: $0 --all"
fi

# ---- 4. Context kontrolü ----
# Cluster silindi ama kubectl context hâlâ kind-ders15-deploy'a bakıyor olabilir
CURRENT_CTX="$(kubectl config current-context 2>/dev/null || echo "")"
if [ "${CURRENT_CTX}" = "kind-${CLUSTER_NAME}" ]; then
  echo ""
  echo "⚠️  kubectl context hâlâ 'kind-${CLUSTER_NAME}' (silinmiş cluster) — kullanılamaz"
  echo "   Başka context'e geç:"
  kubectl config get-contexts -o name | grep -v "kind-${CLUSTER_NAME}" | head -3 | sed 's/^/      kubectl config use-context /'
fi

echo ""
echo "✨ Teardown tamamlandı"
