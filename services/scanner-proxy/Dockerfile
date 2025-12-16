FROM python:3.12-slim-bookworm

WORKDIR /app

# Install scanner tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install subfinder, httpx, nuclei (placeholder - use actual binaries in production)
# RUN wget -q https://github.com/projectdiscovery/subfinder/releases/latest/download/subfinder_linux_amd64.zip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 50051

CMD ["python", "main.py"]
