FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies for ProjectDiscovery tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install ProjectDiscovery tools (subfinder, httpx)
ENV PDTOOLS_VERSION=v1.0.0
RUN wget -q https://github.com/projectdiscovery/subfinder/releases/download/v2.6.6/subfinder_2.6.6_linux_amd64.zip -O /tmp/subfinder.zip \
    && unzip -q /tmp/subfinder.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/subfinder \
    && rm /tmp/subfinder.zip

# Install httpx as httpx-pd to avoid conflict with Python httpx package
RUN wget -q https://github.com/projectdiscovery/httpx/releases/download/v1.6.8/httpx_1.6.8_linux_amd64.zip -O /tmp/httpx.zip \
    && unzip -q /tmp/httpx.zip -d /tmp/ \
    && mv /tmp/httpx /usr/local/bin/httpx-pd \
    && chmod +x /usr/local/bin/httpx-pd \
    && rm /tmp/httpx.zip

# Create data directory for SQLite database
RUN mkdir -p /data && chmod 777 /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
