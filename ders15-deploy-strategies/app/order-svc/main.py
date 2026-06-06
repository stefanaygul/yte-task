# order-svc — Sipariş servisi (Ders 15 Deploy Strategies Lab)
# v1 ve v2 farkı:
#   - v2 /orders response'unda "discount" alanı döner (breaking change simülasyonu)
#   - v2 default STARTUP_DELAY_SECONDS=10 (cold start simülasyonu)
#
# Tüm "kaos" davranışları env var ile kontrol edilir; image yeniden build
# etmeden Deployment YAML'ından kaos enjekte edilebilir.

import os
import time
import random
import asyncio
import logging

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("order-svc")

# ---- Konfigürasyon (env vars) ----
APP_VERSION = os.getenv("APP_VERSION", "v1")
FEATURE_NEW_CHECKOUT = os.getenv("FEATURE_NEW_CHECKOUT", "false").lower() == "true"
CHAOS_LATENCY_MS = int(os.getenv("CHAOS_LATENCY_MS", "0"))
CHAOS_ERROR_RATE = float(os.getenv("CHAOS_ERROR_RATE", "0"))
STARTUP_DELAY_SECONDS = int(os.getenv("STARTUP_DELAY_SECONDS", "0"))
PAYMENT_SVC_URL = os.getenv("PAYMENT_SVC_URL", "http://payment-svc:8002")

# ---- Prometheus metrikleri ----
REQ_COUNT = Counter(
    "order_requests_total",
    "Toplam istek sayısı",
    ["method", "path", "status", "version"],
)
REQ_LATENCY = Histogram(
    "order_request_duration_seconds",
    "İstek süresi (saniye)",
    ["path", "version"],
)

# ---- App lifecycle ----
app = FastAPI(title="order-svc", version=APP_VERSION)
_ready = False  # readiness probe bunu kullanır


@app.on_event("startup")
async def _startup():
    """STARTUP_DELAY_SECONDS bittikten sonra readiness 200 dönmeye başlar.
    Lab 1'de v2 deploy edilince bu süre 10 saniye → rolling update yavaşlar."""
    global _ready
    if STARTUP_DELAY_SECONDS > 0:
        log.info(f"⏳ Startup delay: {STARTUP_DELAY_SECONDS}s (cold start simülasyonu)")
        await asyncio.sleep(STARTUP_DELAY_SECONDS)
    _ready = True
    log.info(f"✅ order-svc {APP_VERSION} hazır")


# ---- Kaos enjeksiyonu (her istek başına) ----
async def _inject_chaos():
    if CHAOS_LATENCY_MS > 0:
        await asyncio.sleep(CHAOS_LATENCY_MS / 1000.0)
    if CHAOS_ERROR_RATE > 0 and random.random() < CHAOS_ERROR_RATE:
        raise HTTPException(status_code=500, detail="chaos: injected error")


# ---- Endpoint'ler ----
@app.get("/health")
async def health():
    """Liveness probe için — process ayakta mı?"""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/ready")
async def ready():
    """Readiness probe için — trafiğe hazır mı? STARTUP_DELAY bitmeden 503 döner."""
    if not _ready:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready", "version": APP_VERSION}


@app.get("/version")
async def version():
    """Lab boyunca curl loop ile sürekli izlenir — v1/v2 geçişini gösterir."""
    return {
        "service": "order-svc",
        "version": APP_VERSION,
        "feature_new_checkout": FEATURE_NEW_CHECKOUT,
    }


@app.get("/orders")
async def list_orders():
    """Dummy sipariş listesi. v2'de her order'a 'discount' alanı eklenir
    (API breaking change simülasyonu — eski client'lar bu alanı bilmez)."""
    start = time.time()
    try:
        await _inject_chaos()
        orders = [
            {"id": 1, "item": "Kitap", "price": 100},
            {"id": 2, "item": "Kalem", "price": 20},
        ]
        if APP_VERSION == "v2":
            for o in orders:
                o["discount"] = 0.1  # v2 breaking change: yeni alan
        REQ_COUNT.labels("GET", "/orders", "200", APP_VERSION).inc()
        return {"version": APP_VERSION, "orders": orders}
    except HTTPException as e:
        REQ_COUNT.labels("GET", "/orders", str(e.status_code), APP_VERSION).inc()
        raise
    finally:
        REQ_LATENCY.labels("/orders", APP_VERSION).observe(time.time() - start)


@app.post("/orders")
async def create_order():
    """Yeni sipariş — payment-svc'yi çağırır. Hata zinciri için iyi bir
    test noktası (payment v2'de timeout farklı, canary'de fark edilebilir)."""
    start = time.time()
    try:
        await _inject_chaos()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{PAYMENT_SVC_URL}/pay", json={"amount": 100})
            r.raise_for_status()
            payment = r.json()
        REQ_COUNT.labels("POST", "/orders", "200", APP_VERSION).inc()
        return {"version": APP_VERSION, "order_id": random.randint(1000, 9999), "payment": payment}
    except httpx.HTTPError as e:
        REQ_COUNT.labels("POST", "/orders", "502", APP_VERSION).inc()
        raise HTTPException(status_code=502, detail=f"payment failed: {e}")
    finally:
        REQ_LATENCY.labels("/orders", APP_VERSION).observe(time.time() - start)


@app.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint'i."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
