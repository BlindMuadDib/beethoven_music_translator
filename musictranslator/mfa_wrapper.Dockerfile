FROM python:3.9-slim-buster
WORKDIR /app
COPY requirements.txt
RUN pip install -r requirements.txt
COPY mfa_wrapper.py
COPY music/ ./music/
CMD ["python", "mfa_wrapper.py"]
