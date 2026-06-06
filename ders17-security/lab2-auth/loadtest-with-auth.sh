#!/usr/bin/env bash
# Lab 2 — Auth'lu loadtest: /admin endpoint'ine 500 request, 50 paralel.
#
# AUTH_MODE'a göre header farklı:
#   jwt-local   → Authorization: Bearer <jwt>   (app validate eder)
#   jwt-gateway → X-User-Id: admin              (app sadece okur)
#
# MODE env var ile seç (default: jwt-local):
#   ./loadtest-with-auth.sh
#   MODE=jwt-gateway ./loadtest-with-auth.sh
set -euo pipefail

TARGET="${TARGET:-http://localhost}"
MODE="${MODE:-jwt-local}"
N="${N:-500}"
C="${C:-50}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$MODE" in
  jwt-local)
    echo "🔐 Mode: jwt-local — JWT alıp Authorization header ile gönderiyoruz"
    TOKEN=$(TARGET="$TARGET" "${SCRIPT_DIR}/get-token.sh")
    if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
      echo "❌ Token alınamadı. /login çalışıyor mu? curl ${TARGET}/login -X POST ..."
      exit 1
    fi
    HEADER="Authorization: Bearer ${TOKEN}"
    ;;
  jwt-gateway)
    echo "🔐 Mode: jwt-gateway — X-User-Id header ile gönderiyoruz (kripto yok)"
    HEADER="X-User-Id: admin"
    ;;
  *)
    echo "❌ Bilinmeyen MODE='$MODE' (jwt-local | jwt-gateway)"
    exit 1
    ;;
esac

echo "🎯 Hedef: ${TARGET}/admin"
echo "📊 Toplam istek: ${N}, paralel: ${C}"
echo "📨 Header: ${HEADER:0:40}..."
echo

if command -v hey >/dev/null 2>&1; then
  echo "🛠️  hey ile çalıştırılıyor"
  echo "----------------------------------------"
  hey -n "${N}" -c "${C}" -H "${HEADER}" "${TARGET}/admin"
else
  echo "⚠️  hey yok — curl fallback (status code dağılımı)"
  TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
  start=$(date +%s)
  seq "${N}" | xargs -n 1 -P "${C}" -I{} sh -c \
    "curl -s -o /dev/null -w '%{http_code}\n' -H '${HEADER}' '${TARGET}/admin'" >> "$TMP"
  end=$(date +%s)
  echo
  echo "Status code dağılımı:"
  sort "$TMP" | uniq -c | sort -rn
  echo "Toplam süre: $((end - start)) sn"
fi

echo
echo "📈 Test biter bitmez CPU'yu ölç:"
echo "  kubectl top pods -l app=order-svc"
echo "  (metrics-server gerekli — yoksa: kubectl top kullanılamaz)"
