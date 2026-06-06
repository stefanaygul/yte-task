# payment-svc Dockerfile
# Build örnekleri:
#   docker build -t payment-svc:v1 --build-arg APP_VERSION=v1 .
#   docker build -t payment-svc:v2 --build-arg APP_VERSION=v2 .
FROM python:3.11-slim

ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION}
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
