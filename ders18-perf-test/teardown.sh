#!/usr/bin/env bash
# Ders 18 Performans Testi Lab — teardown.
# Cluster'ı tamamen siler. Diğer kind cluster'larına (ders15-deploy,
# ders17-security) DOKUNMAZ.
set -euo pipefail

CLUSTER_NAME="ders18-perf"

if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "🗑️  kind cluster siliniyor: ${CLUSTER_NAME}"
  kind delete cluster --name "${CLUSTER_NAME}"
  echo "✅ Silindi"
else
  echo "ℹ️  Cluster '${CLUSTER_NAME}' yok — yapacak bir şey yok"
fi
