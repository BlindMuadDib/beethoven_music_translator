FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install --no-cache-dir demucs flask

COPY separator_wrapper.py .

EXPOSE 22227

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:22227 || exit 1

CMD ["python" "separator_wrapper.py"]
