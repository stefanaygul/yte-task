# order-svc Dockerfile — Ders 18 Performans Testi Lab
# python:3.11-slim üzerine FastAPI servisi.
FROM python:3.11-slim

WORKDIR /app

# Önce requirements (layer cache verimliliği)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8001
# --workers 1 bilinçli: tek worker → CPU bottleneck'i net görünür (Lab 2).
# Prod'da CPU çekirdeği başına worker artırılır; workshop'ta scaling'i HPA yapacak.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
