# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENVIRONMENT=production \
    DATA_DIR=/data \
    DATABASE_URL=sqlite:////data/integration_simulator.db \
    PRODUCTS_DIR=/app/products \
    STATIC_DIR=/app/frontend/dist \
    ENABLE_OPENAPI_DOCS=false \
    LOG_LEVEL=INFO

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY products/ /app/products/
COPY guides/ /app/guides/
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

RUN mkdir -p /data && chown -R appuser:appuser /data /app

USER appuser
WORKDIR /app/backend

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/api/v1/ready || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
