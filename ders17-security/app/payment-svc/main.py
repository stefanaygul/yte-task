# payment-svc — Ders 17 Güvenlik Lab
# Minimal yardımcı servis. Lab senaryolarında doğrudan kullanılmıyor ama
# "iki servisli" gerçekçi topoloji için duruyor.

import random
import logging

from fastapi import FastAPI, HTTPException

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("payment-svc")

app = FastAPI(title="payment-svc", version="1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/pay")
async def pay():
    # %95 başarı, %5 random 500
    if random.random() < 0.05:
        raise HTTPException(status_code=500, detail="payment provider error")
    return {"status": "paid", "txid": random.randint(100000, 999999)}
