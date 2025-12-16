FROM python:3.12-slim-bookworm

# Install base dependencies first
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages FIRST (before httpx binary)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install ProjectDiscovery httpx AFTER pip install
# This will overwrite the Python httpx CLI wrapper
RUN curl -sL https://github.com/projectdiscovery/httpx/releases/download/v1.6.9/httpx_1.6.9_linux_amd64.zip -o /tmp/httpx.zip \
    && unzip -o /tmp/httpx.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/httpx \
    && rm /tmp/httpx.zip \
    && /usr/local/bin/httpx -version

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
