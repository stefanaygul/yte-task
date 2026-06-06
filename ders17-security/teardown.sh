#!/usr/bin/env bash
# Ders 17 Güvenlik Lab — teardown.
# Cluster'ı tamamen siler. Diğer kind cluster'larına (ör. ders15-deploy) DOKUNMAZ.
set -euo pipefail

CLUSTER_NAME="ders17-security"

if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "🗑️  kind cluster siliniyor: ${CLUSTER_NAME}"
  kind delete cluster --name "${CLUSTER_NAME}"
  echo "✅ Silindi"
else
  echo "ℹ️  Cluster '${CLUSTER_NAME}' yok — yapacak bir şey yok"
fi
