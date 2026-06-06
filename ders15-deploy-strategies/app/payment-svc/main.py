# payment-svc — Ödeme servisi (Ders 15 Deploy Strategies Lab)
# v1 ve v2 farkı:
#   - v2'de yapay timeout/latency farkı (canary'de fark edilebilir)
#   - v2 default response'unda "provider" alanı döner

import os
import time
import random
import asyncio
import logging

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("payment-svc")

# ---- Konfigürasyon ----
APP_VERSION = os.getenv("APP_VERSION", "v1")
CHAOS_LATENCY_MS = int(os.getenv("CHAOS_LATENCY_MS", "0"))
CHAOS_ERROR_RATE = float(os.getenv("CHAOS_ERROR_RATE", "0"))
STARTUP_DELAY_SECONDS = int(os.getenv("STARTUP_DELAY_SECONDS", "0"))

# v2'de baseline error rate biraz daha yüksek (gerçekçi: yeni kod, yeni bug'lar)
BASELINE_ERROR_RATE = 0.05 if APP_VERSION == "v1" else 0.08

# ---- Metrikler ----
REQ_COUNT = Counter(
    "payment_requests_total",
    "Toplam istek sayısı",
    ["method", "path", "status", "version"],
)
REQ_LATENCY = Histogram(
    "payment_request_duration_seconds",
    "İstek süresi (saniye)",
    ["path", "version"],
)

app = FastAPI(title="payment-svc", version=APP_VERSION)
_ready = False


@app.on_event("startup")
async def _startup():
    global _ready
    if STARTUP_DELAY_SECONDS > 0:
        log.info(f"⏳ Startup delay: {STARTUP_DELAY_SECONDS}s")
        await asyncio.sleep(STARTUP_DELAY_SECONDS)
    _ready = True
    log.info(f"✅ payment-svc {APP_VERSION} hazır (baseline error rate: {BASELINE_ERROR_RATE})")


async def _inject_chaos():
    """CHAOS env var'ları + baseline error rate uygulanır."""
    if CHAOS_LATENCY_MS > 0:
        await asyncio.sleep(CHAOS_LATENCY_MS / 1000.0)
    effective_error_rate = max(BASELINE_ERROR_RATE, CHAOS_ERROR_RATE)
    if random.random() < effective_error_rate:
        raise HTTPException(status_code=500, detail="payment provider failed")


@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/ready")
async def ready():
    if not _ready:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready", "version": APP_VERSION}


@app.get("/version")
async def version():
    return {"service": "payment-svc", "version": APP_VERSION}


@app.post("/pay")
async def pay():
    """Ödeme işlemi simülasyonu. v1: %5 hata, v2: %8 hata (baseline).
    CHAOS_ERROR_RATE ile manuel artırılabilir (canary abort senaryosu)."""
    start = time.time()
    try:
        await _inject_chaos()
        result = {
            "version": APP_VERSION,
            "txid": f"tx-{random.randint(100000, 999999)}",
            "status": "approved",
        }
        if APP_VERSION == "v2":
            result["provider"] = "stripe-v2"  # v2 yeni alan
        REQ_COUNT.labels("POST", "/pay", "200", APP_VERSION).inc()
        return result
    except HTTPException as e:
        REQ_COUNT.labels("POST", "/pay", str(e.status_code), APP_VERSION).inc()
        raise
    finally:
        REQ_LATENCY.labels("/pay", APP_VERSION).observe(time.time() - start)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
