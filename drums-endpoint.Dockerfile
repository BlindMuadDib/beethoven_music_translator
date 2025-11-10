FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED 1
ENV PIP_NO_CACHE_DIR 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsndfile1 \
        build-essential \
        pkg-config \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY musictranslator/drum_analysis_service/requirements.txt .

RUN pip install -r requirements.txt

FROM python:3.12-slim-bookworm AS runner

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV NUMBA_DISABLE_PERFORMANCE_WARNINGS=1
ENV NUMBA_LOG_LEVEL=WARNING

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY musictranslator/drum_analysis_service /app/drum_analysis_service
COPY data_backend/drum_sample_features.json /app/data_backend/drum_sample_features.json

EXPOSE 25491

CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:25941", "--timeout", "1200", "drum_analysis_service.app:app"]
