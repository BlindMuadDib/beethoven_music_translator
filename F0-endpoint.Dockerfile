FROM python:3.9-slim

WORKDIR /app

COPY musictranslator/f0_service/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY musictranslator/f0_service /app/f0_service

EXPOSE 20006

CMD ["gunicorn", "--bind", "0.0.0.0:20006", "f0_service.app:app", "--workers", "5", "--timeout", "1200"]
