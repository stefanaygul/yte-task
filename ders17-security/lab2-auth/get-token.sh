#!/usr/bin/env bash
# Lab 2 — /login endpoint'inden JWT al, stdout'a yaz.
#
# Kullanım:
#   ./get-token.sh                     # token'ı yazdırır
#   TOKEN=$(./get-token.sh)            # değişkene al
#   ./get-token.sh | tr -d '\n' | pbcopy   # macOS clipboard'a kopyala
set -euo pipefail

TARGET="${TARGET:-http://localhost}"

curl -s -X POST "${TARGET}/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | (command -v jq >/dev/null && jq -r .token || sed 's/.*"token":"\([^"]*\)".*/\1/')
