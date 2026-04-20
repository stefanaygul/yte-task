# Chaos E-Commerce — Resilience Lab

Black Friday gecesi 03:00. Sistem "çalışıyor" ama her şey yanlış gidiyor.
Bu repo kasıtlı bug'larla dolu bir e-commerce uygulaması. Görevin: bul, anla, düzelt.

## Stack
- **API:** Python (FastAPI)
- **Database:** PostgreSQL 15
- **Cache:** Redis 7
- **Queue:** RabbitMQ 3
- **Worker:** Python consumer

## Hızlı Başlangıç

```bash
docker-compose up --build
```

API: http://localhost:8000
RabbitMQ Management: http://localhost:15672 (guest/guest)
Swagger UI: http://localhost:8000/docs

## Endpoints

| Method | Path | Açıklama |
|--------|------|----------|
| GET | /health | Health check |
| GET | /products/ | Ürün listesi |
| GET | /products/{id} | Ürün detayı |
| POST | /products/ | Yeni ürün ekle |
| POST | /orders/ | Sipariş oluştur |
| GET | /orders/ | Sipariş listesi |
| GET | /orders/{id} | Sipariş detayı |

## Örnek İstekler

```bash
# Ürünleri listele
curl http://localhost:8000/products/

# Sipariş ver
curl -X POST http://localhost:8000/orders/ \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "test@test.com", "items": [{"product_id": 1, "quantity": 2}]}'
```

## Load Test

```bash
cd loadtest
pip install -r requirements.txt
locust -f locustfile.py --host=http://localhost:8000
```

Locust UI: http://localhost:8089

## Görevler

| Rol | Dosya |
|-----|-------|
| Backend Developer | [tasks/BACKEND_TASKS.md](tasks/BACKEND_TASKS.md) |
| DevOps / Infra | [tasks/DEVOPS_TASKS.md](tasks/DEVOPS_TASKS.md) |
