# order-svc Dockerfile
# v1 ve v2 farkı build sırasında APP_VERSION build-arg ile belirlenir.
# Build örnekleri:
#   docker build -t order-svc:v1 --build-arg APP_VERSION=v1 .
#   docker build -t order-svc:v2 --build-arg APP_VERSION=v2 .
FROM python:3.11-slim

ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION}
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8001

# v2 için cold start simülasyonu default açık (Lab 1'de readiness sorunu için)
# Deployment YAML'ından override edilebilir.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
