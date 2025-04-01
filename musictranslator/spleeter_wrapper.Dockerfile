FROM debian:stable-slim

WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y curl python3-venv \
    build-essential libsndfile1-dev git gawk \
    && rm -rf /var/lib/apt/lists/*

# Clone the Spleeter repository
RUN git clone https://github.com/deezer/spleeter.git
# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy pyproject.toml and poetry.lock from spleeter
RUN cp /app/spleeter/pyproject.toml /app/pyproject.toml && cp /app/spleeter/poetry.lock /app/poetry.lock

# Modify pyproject.toml to allow Python 3.9+ using gawk
RUN gawk '{if ($0 ~ /python = ">=3.8,<3.12"/) print "python = \">=3.9,<3.12\""; else print $0;}' /app/pyproject.toml > /app/pyproject.toml.tmp && mv /app/pyproject.toml.tmp /app/pyproject.toml

# Modify pyproject.toml to allow Typer 0.4.0+
RUN sed -i 's/typer = "^0.3.2"/typer = "^0.4.0"/g' /app/pyproject.toml

# Install dependencies using Poetry, including Flask
RUN /root/.local/bin/poetry add flask && /root/.local/bin/poetry install --no-root

# Copy your application code
COPY spleeter_wrapper.py .

EXPOSE 22227

CMD ["/root/.local/bin/poetry", "run", "python", "spleeter_wrapper.py"]
