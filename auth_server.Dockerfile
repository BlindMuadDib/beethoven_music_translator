FROM python:3.12-slim

WORKDIR /app

COPY auth_server/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY auth_server/app.py ./app.py

EXPOSE 45769

CMD ["gunicorn", "--bind", "0.0.0.0:45769", "app:create_app()"]
