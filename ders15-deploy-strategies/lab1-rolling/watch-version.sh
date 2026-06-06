#!/usr/bin/env bash
# watch-version.sh
# order-svc /version endpoint'ini her 0.5s'de bir çağırır.
# Rolling update sırasında v1 ve v2 response'larının karışımını gösterir.
#
# Kullanım:
#   ./watch-version.sh                  # default: localhost:8001 (port-forward gerekli)
#   ./watch-version.sh http://10.0.0.1  # custom URL
#
# Ayrı bir terminalde port-forward açık olmalı:
#   kubectl port-forward svc/order-svc 8001:8001

set -euo pipefail

URL="${1:-http://localhost:8001}"

echo "📡 İzleniyor: ${URL}/version"
echo "   (Ctrl+C ile durdur)"
echo ""

while true; do
  TS=$(date +%H:%M:%S)
  # --max-time 2: yavaş pod'larda asılı kalmasın
  # -s: silent, -w: HTTP status code göster
  RESPONSE=$(curl -s --max-time 2 "${URL}/version" || echo '{"error":"timeout"}')
  echo "[${TS}] ${RESPONSE}"
  sleep 0.5
done
