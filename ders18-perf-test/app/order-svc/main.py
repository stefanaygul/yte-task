# order-svc — Ders 18 Performans Testi Lab demo servisi.
#
# Bu servis "ayarlanabilir bottleneck" olacak şekilde tasarlandı. Env var'larla
# davranışı değiştirerek performans olgularını CANLI gözlemleyebilirsin:
#
#   SIMULATED_DB_LATENCY_MS  → her DB sorgusunda eklenen yapay gecikme (ms).
#                              Lab 2'de 10 → 100 yapınca saturation point düşer
#                              (DB'nin bottleneck olduğunu kanıtlar).
#   CACHE_ENABLED            → "true" ise GET /orders sonucu in-memory cache'lenir;
#                              DB latency'sini bypass eder (cache hit/miss farkı).
#   MEMORY_LEAK              → "true" ise her request 100KB'yi global listede tutar
#                              ve bırakmaz → soak test'te memory artışı + OOM (Lab 3).
#   PAYMENT_URL              → payment-svc adresi (POST /orders bunu çağırır).
#
# Metrikler prometheus_client ile /metrics'ten yayınlanır:
#   http_requests_total          (Counter:  method, status, endpoint)
#   http_request_duration_seconds(Histogram: endpoint)
#   orders_created_total         (Counter)
#
# DİKKAT: Gecikmeler asyncio.sleep ile simüle edilir (gerçek DB yok). Bu, event
# loop'u bloklamadan "I/O bekliyoruz" hissini verir — gerçekçi bir async servis.

import os
import time
import asyncio
import logging
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response, JSONResponse

# ---- Konfigürasyon (hepsi env var ile override edilir) ----
SIMULATED_DB_LATENCY_MS = int(os.getenv("SIMULATED_DB_LATENCY_MS", "10"))
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "false").lower() == "true"
MEMORY_LEAK = os.getenv("MEMORY_LEAK", "false").lower() == "true"
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment-svc:8002")
SERVICE_VERSION = "1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("order-svc")
log.info(
    "order-svc starting | DB_LATENCY_MS=%s CACHE_ENABLED=%s MEMORY_LEAK=%s",
    SIMULATED_DB_LATENCY_MS, CACHE_ENABLED, MEMORY_LEAK,
)

# ---- Prometheus metrikleri ----
# İsimler kasıtlı olarak "generic" tutuldu (http_*) ki Grafana'da hazır k6/HTTP
# panelleriyle de eşleşebilsin.
REQ_COUNT = Counter(
    "http_requests_total",
    "Toplam HTTP istek sayısı",
    ["method", "status", "endpoint"],
)
REQ_LATENCY = Histogram(
    "http_request_duration_seconds",
    "İstek süresi (saniye)",
    ["endpoint"],
    # Workshop'ta p95/p99'u anlamlı görmek için bucket'ları SLO civarına yoğunlaştır.
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
ORDERS_CREATED = Counter(
    "orders_created_total",
    "Başarıyla oluşturulan order sayısı",
)

app = FastAPI(title="order-svc", version=SERVICE_VERSION)

# ---- "Veritabanı" (in-memory) ----
_ORDERS = [
    {"id": 1, "item": "laptop", "amount": 1200},
    {"id": 2, "item": "mouse", "amount": 25},
    {"id": 3, "item": "keyboard", "amount": 80},
]

# Cache: GET /orders sonucunu tutar (CACHE_ENABLED=true ise).
_CACHE: dict = {}

# Memory leak deposu: MEMORY_LEAK=true ise her request 100KB ekler, asla bırakmaz.
# Liste global → GC toplayamaz → RSS sürekli artar (soak test'in göstereceği şey).
_LEAK_STORE: list = []
_LEAK_CHUNK = b"x" * (100 * 1024)  # 100 KB

# order-svc → payment-svc çağrıları için tek bir paylaşılan async client
# (her request'te yeni client açmak connection pool israfı olurdu).
_http: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def _startup():
    global _http
    _http = httpx.AsyncClient(timeout=httpx.Timeout(5.0))


@app.on_event("shutdown")
async def _shutdown():
    if _http:
        await _http.aclose()


def _maybe_leak():
    """MEMORY_LEAK açıksa global store'a 100KB ekle. Soak test'in kalbi."""
    if MEMORY_LEAK:
        _LEAK_STORE.append(_LEAK_CHUNK)


async def _db_query():
    """DB sorgusu simülasyonu: SIMULATED_DB_LATENCY_MS kadar bekle, order listesini dön.
    asyncio.sleep event loop'u bloklamaz → I/O-bound bir DB çağrısı gibi davranır."""
    await asyncio.sleep(SIMULATED_DB_LATENCY_MS / 1000.0)
    return _ORDERS


# ---- Metrik middleware: her isteği say + süresini ölç ----
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    endpoint = request.url.path
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        REQ_COUNT.labels(request.method, "500", endpoint).inc()
        REQ_LATENCY.labels(endpoint).observe(time.perf_counter() - start)
        raise
    REQ_COUNT.labels(request.method, str(status), endpoint).inc()
    REQ_LATENCY.labels(endpoint).observe(time.perf_counter() - start)
    return response


# ---- Endpoint'ler ----
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {
        "version": SERVICE_VERSION,
        "service": "order-svc",
        "db_latency_ms": SIMULATED_DB_LATENCY_MS,
        "cache_enabled": CACHE_ENABLED,
        "memory_leak": MEMORY_LEAK,
    }


@app.get("/orders")
async def list_orders():
    """Order listesi. CACHE_ENABLED=true ise ilk istekten sonra DB'ye gitmez
    (latency ~0) → cache hit/miss farkını yük testinde net gösterir."""
    _maybe_leak()

    if CACHE_ENABLED and "orders" in _CACHE:
        return {"orders": _CACHE["orders"], "cached": True}

    orders = await _db_query()
    if CACHE_ENABLED:
        _CACHE["orders"] = orders
    return {"orders": orders, "cached": False}


@app.post("/orders")
async def create_order():
    """Yeni order: önce payment-svc'ye /pay çağrısı, sonra DB'ye yazma simülasyonu.
    Bu yüzden POST /orders, GET'ten daha pahalı (downstream + DB) — gerçekçi."""
    _maybe_leak()

    # 1) Downstream: payment-svc (kendi yapay latency'si var)
    paid = False
    try:
        resp = await _http.post(f"{PAYMENT_URL}/pay")
        paid = resp.status_code == 200
    except Exception as exc:  # payment-svc down/timeout → order başarısız
        log.warning("payment call failed: %s", exc)
        return JSONResponse(status_code=502, content={"status": "payment_failed", "reason": str(exc)})

    if not paid:
        return JSONResponse(status_code=502, content={"status": "payment_declined"})

    # 2) DB write simülasyonu (DB latency burada da geçerli)
    await _db_query()
    ORDERS_CREATED.inc()
    return {"status": "created", "id": int(time.time() * 1000) % 100000, "paid": True}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
