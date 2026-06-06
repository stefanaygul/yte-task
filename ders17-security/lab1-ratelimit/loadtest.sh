#!/usr/bin/env bash
# Lab 1 — Loadtest: 100 request, 20 paralel.
#
# Tercihen `hey` kullanır. Yoksa basit curl döngüsüyle fallback yapar
# (status code dağılımını yine raporlar).
#
# Kullanım:
#   ./loadtest.sh                     # default http://localhost/orders
#   TARGET=http://localhost/orders ./loadtest.sh
set -euo pipefail

TARGET="${TARGET:-http://localhost/orders}"
N="${N:-100}"
C="${C:-20}"

echo "🎯 Hedef: ${TARGET}"
echo "📊 Toplam istek: ${N}, paralel: ${C}"
echo

if command -v hey >/dev/null 2>&1; then
  echo "🛠️  hey ile çalıştırılıyor"
  echo "----------------------------------------"
  hey -n "${N}" -c "${C}" "${TARGET}"
else
  echo "⚠️  hey bulunamadı — curl fallback'i kullanılıyor"
  echo "    (önerilen: brew install hey  veya  go install github.com/rakyll/hey@latest)"
  echo "----------------------------------------"

  TMP=$(mktemp)
  trap 'rm -f "$TMP"' EXIT

  start=$(date +%s)
  # xargs -P ile C kadar paralel curl koştur, her birinin HTTP status'unu yaz
  seq "${N}" | xargs -n 1 -P "${C}" -I{} sh -c \
    "curl -s -o /dev/null -w '%{http_code}\n' '${TARGET}'" >> "$TMP"
  end=$(date +%s)

  echo
  echo "Status code dağılımı:"
  sort "$TMP" | uniq -c | sort -rn
  echo
  echo "Toplam süre: $((end - start)) sn"
fi
