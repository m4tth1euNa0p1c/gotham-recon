# Variables d'Environnement

> **Guide complet de configuration de l'environnement**

---

## Configuration Globale

### Fichier .env

```bash
# ============================================
# DATABASE
# ============================================

# PostgreSQL (Orchestrator)
POSTGRES_USER=gotham
POSTGRES_PASSWORD=gotham_secure_password_2025
POSTGRES_DB=gotham
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# SQLite (Graph Service)
GRAPH_DATABASE_PATH=/app/data/graph.db

# ============================================
# MESSAGING
# ============================================

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC_GRAPH_EVENTS=graph.events
KAFKA_TOPIC_LOGS=logs.recon
KAFKA_TOPIC_MISSION_STATE=mission.state
KAFKA_CONSUMER_GROUP=gotham-consumers

# ============================================
# SERVICES
# ============================================

# Internal Service URLs
ORCHESTRATOR_URL=http://orchestrator:8000
GRAPH_SERVICE_URL=http://graph-service:8001
BFF_GATEWAY_URL=http://bff-gateway:8080
OSINT_RUNNER_URL=http://osint-runner:8002
ACTIVE_RECON_URL=http://active-recon:8003
ENDPOINT_INTEL_URL=http://endpoint-intel:8004
VERIFICATION_URL=http://verification:8005
REPORTER_URL=http://reporter:8006
PLANNER_URL=http://planner:8007
SCANNER_PROXY_URL=http://scanner-proxy:8051

# ============================================
# LLM (OLLAMA)
# ============================================

OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=qwen2.5:14b
OLLAMA_CODER_MODEL=qwen2.5-coder:7b
OLLAMA_TIMEOUT=120

# ============================================
# CREWAI
# ============================================

CREWAI_ENABLED=true
CREWAI_VERBOSE=true
CREWAI_MAX_RPM=10
CREWAI_MAX_ITER=15

# ============================================
# SECURITY
# ============================================

# API Keys (optionnel)
API_KEY=your_api_key_here
JWT_SECRET=your_jwt_secret_here

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# ============================================
# LOGGING
# ============================================

LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/app/logs/gotham.log

# ============================================
# FRONTEND
# ============================================

NEXT_PUBLIC_GRAPHQL_URL=http://localhost:8080/graphql
NEXT_PUBLIC_WS_URL=ws://localhost:8080/graphql
NEXT_PUBLIC_SSE_URL=http://localhost:8080/api/v1/sse
NEXT_PUBLIC_REST_URL=http://localhost:8000/api/v1
```

---

## Variables par Service

### Orchestrator (Port 8000)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL PostgreSQL complète | Required |
| `KAFKA_BOOTSTRAP_SERVERS` | Serveurs Kafka | `kafka:9092` |
| `GRAPH_SERVICE_URL` | URL du Graph Service | `http://graph-service:8001` |
| `OLLAMA_BASE_URL` | URL Ollama | `http://ollama:11434` |
| `MODEL_NAME` | Modèle LLM principal | `qwen2.5:14b` |
| `OLLAMA_CODER_MODEL` | Modèle pour code | `qwen2.5-coder:7b` |
| `CREWAI_ENABLED` | Activer CrewAI | `true` |
| `LOG_LEVEL` | Niveau de log | `INFO` |

### Graph Service (Port 8001)

| Variable | Description | Default |
|----------|-------------|---------|
| `GRAPH_DATABASE_PATH` | Chemin SQLite | `/app/data/graph.db` |
| `KAFKA_BOOTSTRAP_SERVERS` | Serveurs Kafka | `kafka:9092` |
| `KAFKA_TOPIC_GRAPH_EVENTS` | Topic pour events | `graph.events` |
| `LOG_LEVEL` | Niveau de log | `INFO` |

### BFF Gateway (Port 8080)

| Variable | Description | Default |
|----------|-------------|---------|
| `ORCHESTRATOR_URL` | URL Orchestrator | `http://orchestrator:8000` |
| `GRAPH_SERVICE_URL` | URL Graph Service | `http://graph-service:8001` |
| `KAFKA_BOOTSTRAP_SERVERS` | Serveurs Kafka | `kafka:9092` |
| `CORS_ORIGINS` | Origins CORS | `*` |
| `LOG_LEVEL` | Niveau de log | `INFO` |

### Phase Services (Ports 8002-8006)

| Variable | Description | Default |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Serveurs Kafka | `kafka:9092` |
| `GRAPH_SERVICE_URL` | URL Graph Service | `http://graph-service:8001` |
| `OLLAMA_BASE_URL` | URL Ollama (Verification) | `http://ollama:11434` |
| `LOG_LEVEL` | Niveau de log | `INFO` |

### Frontend (Port 3000)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_GRAPHQL_URL` | URL GraphQL | `http://localhost:8080/graphql` |
| `NEXT_PUBLIC_WS_URL` | URL WebSocket | `ws://localhost:8080/graphql` |
| `NEXT_PUBLIC_SSE_URL` | URL SSE | `http://localhost:8080/api/v1/sse` |
| `NEXT_PUBLIC_REST_URL` | URL REST | `http://localhost:8000/api/v1` |

---

## Modes de Déploiement

### Développement

```bash
# .env.development
LOG_LEVEL=DEBUG
CREWAI_VERBOSE=true
RATE_LIMIT_ENABLED=false
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DATABASE_URL=postgresql://gotham:gotham@localhost:5432/gotham
```

### Production

```bash
# .env.production
LOG_LEVEL=INFO
CREWAI_VERBOSE=false
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60

# Utiliser des secrets Docker/K8s pour les passwords
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
JWT_SECRET_FILE=/run/secrets/jwt_secret
```

### Test

```bash
# .env.test
LOG_LEVEL=WARNING
CREWAI_ENABLED=false
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
DATABASE_URL=postgresql://gotham:gotham@localhost:5432/gotham_test
```

---

## Configuration Kafka

### Topics Requis

```bash
# Créer les topics
kafka-topics --create --topic graph.events --bootstrap-server kafka:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic logs.recon --bootstrap-server kafka:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic mission.state --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1
```

### Configuration Producteur

```bash
KAFKA_PRODUCER_ACKS=all
KAFKA_PRODUCER_RETRIES=3
KAFKA_PRODUCER_BATCH_SIZE=16384
KAFKA_PRODUCER_LINGER_MS=1
```

### Configuration Consommateur

```bash
KAFKA_CONSUMER_GROUP=gotham-consumers
KAFKA_CONSUMER_AUTO_OFFSET_RESET=earliest
KAFKA_CONSUMER_ENABLE_AUTO_COMMIT=true
```

---

## Configuration PostgreSQL

### Paramètres de Performance

```bash
# postgresql.conf
max_connections=100
shared_buffers=256MB
effective_cache_size=768MB
maintenance_work_mem=64MB
checkpoint_completion_target=0.9
wal_buffers=7864kB
default_statistics_target=100
random_page_cost=4
effective_io_concurrency=2
work_mem=2621kB
min_wal_size=1GB
max_wal_size=4GB
```

### Pool de Connexions

```bash
# Variables pool
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800
```

---

## Configuration Ollama

### Modèles Requis

```bash
# Télécharger les modèles
ollama pull qwen2.5:14b
ollama pull qwen2.5-coder:7b
```

### GPU Configuration

```bash
# Docker Compose avec GPU
OLLAMA_GPU=nvidia
NVIDIA_VISIBLE_DEVICES=all
```

### Sans GPU (CPU only)

```bash
OLLAMA_CPU_ONLY=true
OLLAMA_NUM_THREADS=8
```

---

## Sécurité

### API Keys

```bash
# Générer une clé API
openssl rand -hex 32
```

### JWT Configuration

```bash
JWT_SECRET=your_256_bit_secret_here
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600
```

### TLS/SSL

```bash
# Configuration TLS
SSL_CERT_PATH=/etc/ssl/certs/gotham.crt
SSL_KEY_PATH=/etc/ssl/private/gotham.key
SSL_CA_PATH=/etc/ssl/certs/ca.crt
```

---

## Validation

### Script de Validation

```bash
#!/bin/bash
# validate-env.sh

required_vars=(
  "DATABASE_URL"
  "KAFKA_BOOTSTRAP_SERVERS"
  "GRAPH_SERVICE_URL"
  "OLLAMA_BASE_URL"
)

for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "ERROR: $var is not set"
    exit 1
  else
    echo "OK: $var is set"
  fi
done

echo "All required variables are set!"
```

### Health Check des Variables

```python
# check_env.py
import os

required = {
    "DATABASE_URL": "postgresql://",
    "KAFKA_BOOTSTRAP_SERVERS": "",
    "OLLAMA_BASE_URL": "http://",
}

for var, prefix in required.items():
    value = os.getenv(var)
    if not value:
        print(f"ERROR: {var} is not set")
    elif prefix and not value.startswith(prefix):
        print(f"WARNING: {var} may be misconfigured")
    else:
        print(f"OK: {var}")
```

---

## Troubleshooting

### Erreur de Connexion PostgreSQL

```bash
# Vérifier la variable
echo $DATABASE_URL

# Tester la connexion
psql $DATABASE_URL -c "SELECT 1"
```

### Erreur Kafka

```bash
# Vérifier Kafka
kafka-broker-api-versions --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS

# Lister les topics
kafka-topics --list --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS
```

### Erreur Ollama

```bash
# Vérifier Ollama
curl $OLLAMA_BASE_URL/api/tags

# Vérifier le modèle
curl $OLLAMA_BASE_URL/api/show -d '{"name":"qwen2.5:14b"}'
```
