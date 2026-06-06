#!/usr/bin/env bash
# Lab 3 — Saldırı simülasyon scripti.
#
# Hangi ingress aktifse ona göre 200/403 görürsün:
#   - ingress-no-waf.yaml       → hepsi 200 (saldırılar geçer)
#   - ingress-waf-detect.yaml   → hepsi 200 (block YOK, ama log var)
#   - ingress-waf-block.yaml    → SQLi/XSS/path traversal 403
#
# Kullanım:
#   ./attack-tests.sh                       # http://localhost
#   TARGET=http://localhost ./attack-tests.sh
set -uo pipefail   # -e KOY-MA: 4xx response curl exit'i etkilemez ama
                    #            bazı pipe'lar non-zero dönerse devam etsin

TARGET="${TARGET:-http://localhost}"

hr() { echo "─────────────────────────────────────────────────────────"; }

run() {
  local desc="$1"
  shift
  hr
  echo "▶ $desc"
  echo "  → $*"
  # status code + ilk 200 char body
  STATUS=$(curl -s -o /tmp/attack_body -w "%{http_code}" "$@")
  BODY=$(head -c 200 /tmp/attack_body)
  echo "  ← HTTP $STATUS | body: $BODY"
  echo
}

echo "🎯 Hedef: ${TARGET}"
echo

# ---- BASELINE: normal istekler her zaman geçmeli ----
run "Baseline — normal arama (her modda 200 olmalı)" \
  "${TARGET}/search?q=laptop"

run "Baseline — sağlık kontrolü" \
  "${TARGET}/health"

# ---- SQL INJECTION ----
# ' OR 1=1 --   (URL-encoded: %27%20OR%201%3D1%20--)
run "SQLi — klasik ' OR 1=1 --" \
  "${TARGET}/search?q=%27%20OR%201%3D1%20--"

# UNION SELECT
run "SQLi — UNION SELECT" \
  "${TARGET}/search?q=1%27%20UNION%20SELECT%20username,password%20FROM%20users--"

# ---- XSS ----
# <script>alert(document.cookie)</script>
run "XSS — script tag (body içinde)" \
  -X POST "${TARGET}/comment" \
  -H "Content-Type: application/json" \
  -d '{"text":"<script>alert(document.cookie)</script>"}'

# <img src=x onerror=alert(1)>
run "XSS — img onerror (query'de)" \
  "${TARGET}/search?q=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E"

# ---- PATH TRAVERSAL ----
run "Path traversal — ../../etc/passwd" \
  "${TARGET}/search?q=../../etc/passwd"

# ---- REMOTE COMMAND EXECUTION (shell metachar) ----
run "RCE — ; cat /etc/passwd" \
  "${TARGET}/search?q=foo%3B%20cat%20%2Fetc%2Fpasswd"

# ---- FALSE POSITIVE DENEMELERİ (Block modunda 403 dönebilir) ----
hr
echo "⚠️  Aşağıdaki istekler MEŞRU ama Block modunda 403 olabilir (false positive):"
echo

run "False positive #1 — yorum: 'SELECT the best option FROM our menu'" \
  -X POST "${TARGET}/comment" \
  -H "Content-Type: application/json" \
  -d '{"text":"Please SELECT the best option FROM our menu"}'

run "False positive #2 — arama: 'union of workers'" \
  "${TARGET}/search?q=union+of+workers"

hr
echo "✅ Saldırı testleri tamam."
echo
echo "Logları gör:"
echo "  kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=200 | grep -i modsecurity"
