FROM docker.io/pytorch/pytorch:2.3.1-cuda12.1-cudnn8-devel AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    sox \
    # Clean up apt cache
    && rm -rf /var/lib/apt/lists/*

COPY ./separator-requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r separator-requirements.txt

FROM docker.io/pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    sox \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/conda/lib/python3.10/site-packages /opt/conda/lib/python3.10/site-packages
COPY --from=builder /opt/conda/bin /usr/local/bin

# This will pre-download the htdemucs_6s model into the image layer
ENV PYTHONPATH=/opt/conda/lib/python3.10/site-packages
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs_6s')"

COPY ./musictranslator/separator_wrapper.py /app/separator_wrapper.py

EXPOSE 22227

CMD ["/bin/sh", "-c", "export PYTHONPATH=/opt/conda/lib/python3.10/site-packages && gunicorn --bind 0.0.0.0:22227 separator_wrapper:app --workers 3 --timeout 300"]
