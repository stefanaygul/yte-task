# payment-svc — Ders 18 Performans Testi Lab
#
# order-svc'nin POST /orders sırasında çağırdığı downstream servis.
# Yapay latency + %5 hata ile gerçekçi bir ödeme sağlayıcısını taklit eder.
#
#   SIMULATED_LATENCY_MS → /pay'in eklediği yapay gecikme (ms, default 20).
#                          POST /orders zincirine bu da eklenir.
#
# Metrikler order-svc ile aynı isimlerde (http_requests_total,
# http_request_duration_seconds) → Prometheus'ta servis label'ı ile ayrışır.

import os
import time
import random
import asyncio
import logging

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response, JSONResponse

SIMULATED_LATENCY_MS = int(os.getenv("SIMULATED_LATENCY_MS", "20"))
SERVICE_VERSION = "1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("payment-svc")
log.info("payment-svc starting | SIMULATED_LATENCY_MS=%s", SIMULATED_LATENCY_MS)

REQ_COUNT = Counter(
    "http_requests_total",
    "Toplam HTTP istek sayısı",
    ["method", "status", "endpoint"],
)
REQ_LATENCY = Histogram(
    "http_request_duration_seconds",
    "İstek süresi (saniye)",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

app = FastAPI(title="payment-svc", version=SERVICE_VERSION)


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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": SERVICE_VERSION, "service": "payment-svc", "latency_ms": SIMULATED_LATENCY_MS}


@app.post("/pay")
async def pay():
    """%95 başarı, %5 random 500. Yapay latency ile gerçekçi ödeme çağrısı."""
    await asyncio.sleep(SIMULATED_LATENCY_MS / 1000.0)
    if random.random() < 0.05:
        return JSONResponse(status_code=500, content={"status": "provider_error"})
    return {"status": "paid", "txid": random.randint(100000, 999999)}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
