FROM mmcauliffe/montreal-forced-aligner:latest
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 24725
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:24725 || exit 1
CMD ["python", "mfa_wrapper.py"]
