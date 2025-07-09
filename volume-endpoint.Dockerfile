FROM python:3.12-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY musictranslator/volume_service/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./musictranslator/volume_service ./volume_service

EXPOSE 39574

CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:39574", "volume_service.app:app"]
