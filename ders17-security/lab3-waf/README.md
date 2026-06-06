# Lab 3 — WAF (15 dk)

**Amaç:** ModSecurity + OWASP CRS ile SQLi/XSS saldırılarını yakalamak ve false
positive sorununu canlı görmek.

> Önkoşul: Lab 1 cleanup yapıldı (`kubectl delete ingress security-lab`),
> app pod'ları çalışıyor.

---

## 1) WAF YOK — saldırılar geçer (3 dk)

```bash
cd ders17-security/lab3-waf

kubectl apply -f ingress-no-waf.yaml

# Saldırı testi
./attack-tests.sh
```

**Beklenen:** SQLi, XSS, path traversal, RCE — **hepsi 200 OK**.
order-svc payload'u response'a yansıtıyor (`/search` query'yi, `/comment` text'i).
Gerçek bir uygulama olsa SQL sorgusunu çalıştırırdı, DOM'a inject ederdi vs.

---

## 2) DetectionOnly — logla ama bloklama (3 dk)

```bash
kubectl apply -f ingress-waf-detect.yaml

# Saldırıları tekrarla
./attack-tests.sh
```

**Beklenen:** Hâlâ 200 OK dönüyor (block YOK). Ama controller loglarında alert var:

```bash
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller --tail=200 \
  | grep -i modsecurity | head -20
```

Aramaya örnek loglar:
```
ModSecurity: Warning. ... [id "942100"] [msg "SQL Injection Attack Detected via libinjection"]
ModSecurity: Warning. ... [id "941100"] [msg "XSS Attack Detected via libinjection"]
ModSecurity: Warning. ... [id "930100"] [msg "Path Traversal Attack"]
```

**Pattern:** Production'a WAF açarken ÖNCE DetectionOnly. 1-2 hafta log topla, false
positive'leri rule exception ile çöz, sonra Block'a geç.

---

## 3) Block modu — saldırılar engellenir (3 dk)

```bash
kubectl apply -f ingress-waf-block.yaml

# Saldırıları tekrarla
./attack-tests.sh
```

**Beklenen:**
- Baseline istekleri (laptop, /health) → **200 OK** (normal trafik geçiyor)
- SQLi/XSS/path traversal/RCE → **403 Forbidden**
- Body: `<html><head><title>403 Forbidden</title>...` (NGINX default 403 sayfası)

---

## 4) False positive — meşru istek de bloklanır (3 dk)

`attack-tests.sh`'nin son iki testi false positive denemesi:

```bash
# Meşru ama "SELECT ... FROM" geçiyor → SQLi rule tetikleniyor
curl -X POST http://localhost/comment \
  -H "Content-Type: application/json" \
  -d '{"text":"Please SELECT the best option FROM our menu"}'
# → 403 Forbidden  (False positive!)

# "UNION" kelimesi de SQLi rule'unu tetikler
curl "http://localhost/search?q=union+of+workers"
# → 403 Forbidden  (False positive!)
```

**Tartışma:** WAF agresif tutulursa meşru kullanıcıyı bloklar (revenue kaybı).
Gevşek tutulursa saldırgan geçer. Denge işi — DetectionOnly'de canlı trafiği
gözle, exception'ları yaz:

```nginx
# Bir kuralı belirli bir path için kapat (ingress annotation snippet'i)
SecRule REQUEST_URI "@beginsWith /comment" \
  "id:1000,phase:1,nolog,pass,ctl:ruleRemoveById=942100"
```

---

## 5) Tartışma (3 dk)

| Soru | Cevap |
|------|-------|
| "WAF tek başına yeterli mi?" | **Hayır.** Defense in depth: parametrized query, input validation, output encoding, CSP, rate limit. WAF bunların yerine değil yanına. |
| "Hangi paranoia level'da kalmalı?" | PL1 default — çoğu üretim için doğru. PL2+ → çok daha fazla false positive, sadece kritik endpoint'ler için. |
| "DetectionOnly → Block geçişi ne kadar sürer?" | Tipik: 2 hafta gözlem + 1 hafta exception tuning. Trafik volümü düşükse uzar. |
| "WAF ne YAKALAMAZ?" | İş mantığı saldırıları (auth bypass, IDOR, race condition, çalınmış token). WAF örüntü tanır, niyet tanımaz. |

---

## Cleanup (Lab 2'ye geçmeden önce)

```bash
kubectl delete ingress security-lab
```
