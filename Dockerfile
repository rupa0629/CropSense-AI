# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libnsl2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Copy small verification scripts and run TensorFlow import check to fail fast on incompatible images
COPY scripts/ ./scripts/
RUN python scripts/check_tensorflow.py

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libnsl2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system appgroup \
    && useradd --system --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

COPY --from=builder /usr/local /usr/local
COPY . /app
RUN mkdir -p /app/data \
    && chmod +x /app/scripts/start.sh \
    && chown -R appuser:appgroup /app

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8000/health/ready'); sys.exit(0)" || exit 1
CMD ["sh", "/app/scripts/start.sh"]
