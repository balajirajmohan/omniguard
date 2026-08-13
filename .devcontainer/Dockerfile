FROM python:3.11-slim

# System deps (needed for some Python wheels on Linux)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install Python dependencies (layer-cached separately from source code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The rest of the source is mounted by the dev container at runtime,
# so we don't COPY it here — that keeps rebuilds fast.
