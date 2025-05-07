FROM python:3.11-slim-buster

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    sox \
    # Clean up apt cache
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install --no-cache-dir demucs flask gunicorn

COPY ./musictranslator/separator_wrapper.py /app/separator_wrapper.py

EXPOSE 22227

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:22227 || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:22227", "separator_wrapper:app", "--workers", "3", "--timeout", "300"]
