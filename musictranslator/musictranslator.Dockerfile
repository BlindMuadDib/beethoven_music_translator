# Use a multi-architecture base image
FROM python:3.9-slim-buster

#Set the working directory in the container
WORKDIR /app

# Install libmagic before python-magic
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libmagic-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Flask
RUN pip install --upgrade pip
RUN pip install --no-cache-dir Flask python-magic requests

# Copy the application files
COPY . .

# Basic health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:20005 || exit 1

# Command to run the app
CMD ["python", "-m", "main.py"]
