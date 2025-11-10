# Use a multi-architecture base image
FROM python:3.11-slim

#Set the working directory in the container
WORKDIR /app

# Install libmagic before python-magic
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libmagic-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Flask
RUN pip install --upgrade pip
RUN pip install --no-cache-dir Flask python-magic requests gunicorn redis>=4.0 rq>=1.10

# Copy the application files
COPY musictranslator/ /app/musictranslator
COPY worker.py /app/worker.py

# Command to run the app
CMD ["gunicorn", "--bind", "0.0.0.0:20005", "musictranslator.main:app", "--workers", "3", "--timeout", "5000"]
