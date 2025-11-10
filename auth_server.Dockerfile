FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential libpq-dev

COPY auth_server/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY auth_server/app.py ./app.py

EXPOSE 45769

CMD ["gunicorn", "--workers", "4", "--worker-class", "gthread", "--bind", "0.0.0.0:45769", "app:create_app()"]
