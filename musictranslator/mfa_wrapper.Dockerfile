FROM mmcauliffe/montreal-forced-aligner:latest
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 24725
CMD ["python", "mfa_wrapper.py"]
