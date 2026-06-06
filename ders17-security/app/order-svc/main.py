# order-svc — Ders 17 Güvenlik Lab demo servisi.
#
# Endpoint'ler güvenlik testleri için tasarlandı:
#   - /orders        → rate limit testi (Lab 1)
#   - /login + /admin → JWT auth (Lab 2)
#   - /search, /comment → WAF testi: SQLi/XSS payload yansıtır (Lab 3)
#
# AUTH_MODE env var'a göre /admin davranışı değişir:
#   - none        → herkes geçer (auth devre dışı)
#   - jwt-local   → her pod kendi JWT'sini validate eder (PyJWT + HMAC256)
#   - jwt-gateway → app validate etmez; sadece X-User-Id header'a güvenir
#                   (gateway/Ingress'in JWT doğruladığı varsayılır)
#
# Üretimde HMAC yerine RSA/ECDSA kullanın — HMAC secret paylaşımı risklidir.

import os
import time
import logging
from typing import Optional

import jwt
from fastapi import FastAPI, Header, HTTPException, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response, JSONResponse

# ---- Konfigürasyon ----
AUTH_MODE = os.getenv("AUTH_MODE", "none").lower()        # none | jwt-local | jwt-gateway
JWT_SECRET = os.getenv("JWT_SECRET", "workshop-secret-key")
JWT_ALG = "HS256"
SERVICE_VERSION = "1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("order-svc")
log.info(f"order-svc starting | AUTH_MODE={AUTH_MODE}")

# ---- Prometheus metrikleri ----
REQ_COUNT = Counter(
    "order_requests_total",
    "Toplam istek sayısı",
    ["method", "path", "status"],
)
REQ_LATENCY = Histogram(
    "order_request_duration_seconds",
    "İstek süresi (saniye)",
    ["path"],
)
AUTH_FAILURES = Counter(
    "order_auth_failures_total",
    "Auth doğrulama hatası sayısı (mode'a göre)",
    ["mode", "reason"],
)

app = FastAPI(title="order-svc", version=SERVICE_VERSION)


# ---- Basit metrik middleware ----
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        REQ_COUNT.labels(request.method, request.url.path, "500").inc()
        raise
    REQ_COUNT.labels(request.method, request.url.path, str(status)).inc()
    REQ_LATENCY.labels(request.url.path).observe(time.perf_counter() - start)
    return response


# ---- Endpoint'ler ----
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": SERVICE_VERSION, "service": "order-svc", "auth_mode": AUTH_MODE}


@app.get("/orders")
async def list_orders():
    """Dummy order listesi — auth gerekmez. Rate limit testinde GET hedefi."""
    return {
        "orders": [
            {"id": 1, "item": "laptop", "amount": 1200},
            {"id": 2, "item": "mouse", "amount": 25},
            {"id": 3, "item": "keyboard", "amount": 80},
        ]
    }


@app.post("/orders")
async def create_order():
    """Yeni order — auth gerekmez. Rate limit testinde POST hedefi."""
    return {"status": "created", "id": int(time.time() * 1000) % 100000}


@app.post("/login")
async def login(payload: dict):
    """Workshop için basit login: username==password==admin → JWT döner."""
    username = (payload or {}).get("username")
    password = (payload or {}).get("password")
    if username != "admin" or password != "admin":
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = jwt.encode(
        {
            "sub": username,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,  # 1 saat
            "role": "admin",
        },
        JWT_SECRET,
        algorithm=JWT_ALG,
    )
    return {"token": token}


def _require_jwt_local(authorization: Optional[str]) -> dict:
    """jwt-local mode: PyJWT ile imzayı + exp'i doğrula (CPU yükü burada)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        AUTH_FAILURES.labels("jwt-local", "missing_header").inc()
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        AUTH_FAILURES.labels("jwt-local", "expired").inc()
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        AUTH_FAILURES.labels("jwt-local", "invalid").inc()
        raise HTTPException(status_code=401, detail="invalid token")


def _require_gateway_header(x_user_id: Optional[str]) -> dict:
    """jwt-gateway mode: app validate etmez, sadece gateway'in eklediği
    X-User-Id header'ına güvenir. Kripto yok → CPU ucuz."""
    if not x_user_id:
        AUTH_FAILURES.labels("jwt-gateway", "missing_header").inc()
        raise HTTPException(status_code=401, detail="missing X-User-Id header")
    return {"sub": x_user_id, "via": "gateway"}


@app.get("/admin")
async def admin(
    authorization: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    """AUTH_MODE'a göre farklı doğrulama yolu — Lab 2 burayı yükler."""
    if AUTH_MODE == "none":
        principal = {"sub": "anonymous", "mode": "none"}
    elif AUTH_MODE == "jwt-local":
        principal = _require_jwt_local(authorization)
    elif AUTH_MODE == "jwt-gateway":
        principal = _require_gateway_header(x_user_id)
    else:
        raise HTTPException(status_code=500, detail=f"unknown AUTH_MODE={AUTH_MODE}")
    return {"area": "admin", "principal": principal, "auth_mode": AUTH_MODE}


@app.get("/search")
async def search(q: str = ""):
    """Arama simülasyonu — query'yi loglar ve response'a yansıtır.
    WAF testi: q parametresine SQLi / path traversal payload'u gönder."""
    log.info(f"search query={q!r}")
    return {"query": q, "results": [f"result for: {q}"]}


@app.post("/comment")
async def comment(payload: dict):
    """Yorum simülasyonu — body'deki text'i response'a yansıtır.
    WAF testi: text alanına XSS payload'u gönder."""
    text = (payload or {}).get("text", "")
    log.info(f"comment text={text!r}")
    return {"saved": True, "text": text}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
