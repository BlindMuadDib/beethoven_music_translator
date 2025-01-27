# Use a multi-architecture base image
FROM python:3.9-slim

#Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk \
    ffmpeg \
    libasound2-dev \
    libsdl2-2.0-0 libsdl2-mixer-2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the application files
COPY . .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Expose a port if your app uses networking (optional)
# EXPOSE 5757

# Command to run your app

CMD ["python3", "/app/singalonglyrics.py"]
