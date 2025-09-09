# --- Stage 1: The Builder ---
FROM python:3.12-bookworm AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gfortran \
        libsndfile1-dev \
        libopenblas-dev \
        ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels

COPY musictranslator/harmonic_service/requirements.txt .

RUN pip wheel --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm AS runner

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
        libopenblas0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY musictranslator/harmonic_service /app/harmonic_service

COPY --from=builder /wheels /wheels/

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /app/harmonic_service/requirements.txt \
    && rm -rf /wheels

EXPOSE 20006

CMD ["gunicorn", "--bind", "0.0.0.0:20006", "harmonic_service.app:app", "--workers", "1", "--timeout", "1200"]
