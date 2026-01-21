# Déploiement Docker Compose

> **Guide de déploiement avec Docker Compose**

---

## Prérequis

### Versions Requises

```bash
# Vérifier les versions
docker --version          # >= 24.0
docker compose version    # >= 2.20
```

### Ressources Système

| Ressource | Minimum | Recommandé |
|-----------|---------|------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB | 50 GB |

---

## Configuration

### 1. Cloner le Repository

```bash
git clone https://github.com/gotham/recon-gotham.git
cd recon-gotham
```

### 2. Configurer l'Environnement

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer avec vos valeurs
nano .env
```

### 3. Variables d'Environnement

```bash
# === DATABASE ===
POSTGRES_USER=gotham
POSTGRES_PASSWORD=gotham_secret_2025
POSTGRES_DB=gotham
DATABASE_URL=postgresql://gotham:gotham_secret_2025@postgres:5432/gotham

# === KAFKA ===
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# === SERVICES ===
ORCHESTRATOR_URL=http://orchestrator:8000
GRAPH_SERVICE_URL=http://graph-service:8001
BFF_GATEWAY_URL=http://bff-gateway:8080

# === OLLAMA (LLM) ===
OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=qwen2.5:14b
OLLAMA_CODER_MODEL=qwen2.5-coder:7b

# === CREWAI ===
CREWAI_ENABLED=true
```

---

## Lancement

### Démarrage Complet

```bash
# Démarrer tous les services
docker compose up -d

# Suivre les logs
docker compose logs -f

# Vérifier le statut
docker compose ps
```

### Démarrage par Profil

```bash
# Infrastructure seulement (Kafka, PostgreSQL)
docker compose --profile infra up -d

# Services backend seulement
docker compose --profile backend up -d

# Frontend seulement
docker compose --profile frontend up -d
```

### Démarrage Sélectif

```bash
# Services essentiels
docker compose up -d postgres kafka zookeeper
docker compose up -d graph-service orchestrator bff-gateway

# Ajouter l'UI
docker compose up -d gotham-ui
```

---

## Structure docker-compose.yml

```yaml
version: '3.8'

services:
  # === INFRASTRUCTURE ===

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-gotham}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-gotham}
      POSTGRES_DB: ${POSTGRES_DB:-gotham}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gotham"]
      interval: 10s
      timeout: 5s
      retries: 5

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD", "kafka-topics", "--bootstrap-server", "localhost:9092", "--list"]
      interval: 30s
      timeout: 10s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  # === BACKEND SERVICES ===

  graph-service:
    build:
      context: ./services/graph-service
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - DATABASE_PATH=/app/data/graph.db
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - graph_data:/app/data
    depends_on:
      kafka:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  orchestrator:
    build:
      context: ./services/recon-orchestrator
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - GRAPH_SERVICE_URL=http://graph-service:8001
      - OLLAMA_BASE_URL=http://ollama:11434
      - MODEL_NAME=${MODEL_NAME:-qwen2.5:14b}
      - CREWAI_ENABLED=true
    volumes:
      - ./output:/app/output
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
      graph-service:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  bff-gateway:
    build:
      context: ./services/bff-gateway
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      - ORCHESTRATOR_URL=http://orchestrator:8000
      - GRAPH_SERVICE_URL=http://graph-service:8001
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    depends_on:
      orchestrator:
        condition: service_healthy
      graph-service:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # === PHASE SERVICES ===

  osint-runner:
    build:
      context: ./services/osint-runner
      dockerfile: Dockerfile
    ports:
      - "8002:8002"
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - GRAPH_SERVICE_URL=http://graph-service:8001
    depends_on:
      - kafka
      - graph-service

  active-recon:
    build:
      context: ./services/active-recon
      dockerfile: Dockerfile
    ports:
      - "8003:8003"
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - GRAPH_SERVICE_URL=http://graph-service:8001
    depends_on:
      - kafka
      - graph-service

  endpoint-intel:
    build:
      context: ./services/endpoint-intel
      dockerfile: Dockerfile
    ports:
      - "8004:8004"
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - GRAPH_SERVICE_URL=http://graph-service:8001
    depends_on:
      - kafka
      - graph-service

  verification:
    build:
      context: ./services/verification
      dockerfile: Dockerfile
    ports:
      - "8005:8005"
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - GRAPH_SERVICE_URL=http://graph-service:8001
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - kafka
      - graph-service

  reporter:
    build:
      context: ./services/reporter
      dockerfile: Dockerfile
    ports:
      - "8006:8006"
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - GRAPH_SERVICE_URL=http://graph-service:8001
    volumes:
      - ./output:/app/output
    depends_on:
      - kafka
      - graph-service

  planner:
    build:
      context: ./services/planner
      dockerfile: Dockerfile
    ports:
      - "8007:8007"
    environment:
      - GRAPH_SERVICE_URL=http://graph-service:8001
    depends_on:
      - graph-service

  scanner-proxy:
    build:
      context: ./services/scanner-proxy
      dockerfile: Dockerfile
    ports:
      - "8051:8051"
      - "50051:50051"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  # === FRONTEND ===

  gotham-ui:
    build:
      context: ./gotham-ui
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_GRAPHQL_URL=http://localhost:8080/graphql
      - NEXT_PUBLIC_WS_URL=ws://localhost:8080/graphql
      - NEXT_PUBLIC_SSE_URL=http://localhost:8080/api/v1/sse
    depends_on:
      - bff-gateway

volumes:
  postgres_data:
  graph_data:
  ollama_data:
  output:

networks:
  default:
    name: gotham-network
```

---

## Commandes Utiles

### Gestion des Services

```bash
# Démarrer tous les services
docker compose up -d

# Arrêter tous les services
docker compose down

# Redémarrer un service
docker compose restart orchestrator

# Voir les logs d'un service
docker compose logs -f orchestrator

# Entrer dans un container
docker compose exec orchestrator bash

# Reconstruire une image
docker compose build orchestrator
docker compose up -d orchestrator
```

### Nettoyage

```bash
# Supprimer tous les containers et volumes
docker compose down -v

# Nettoyer les images non utilisées
docker image prune -a

# Nettoyer tout (attention!)
docker system prune -a --volumes
```

### Debug

```bash
# Vérifier les ports
docker compose ps

# Voir les ressources utilisées
docker stats

# Inspecter un container
docker inspect gotham-orchestrator

# Voir les logs Kafka
docker compose logs kafka
```

---

## Health Checks

### Vérification Manuelle

```bash
# Health check de chaque service
curl http://localhost:8000/health  # Orchestrator
curl http://localhost:8001/health  # Graph Service
curl http://localhost:8080/health  # BFF Gateway

# Vérifier Kafka
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Vérifier PostgreSQL
docker compose exec postgres psql -U gotham -c "SELECT 1"
```

### Script de Vérification

```bash
#!/bin/bash
# health-check.sh

services=(
  "http://localhost:8000/health:Orchestrator"
  "http://localhost:8001/health:Graph-Service"
  "http://localhost:8080/health:BFF-Gateway"
)

for service in "${services[@]}"; do
  url="${service%%:*}"
  name="${service##*:}"
  if curl -sf "$url" > /dev/null; then
    echo "✅ $name: OK"
  else
    echo "❌ $name: FAILED"
  fi
done
```

---

## Mise à Jour

### Mise à Jour des Services

```bash
# Pull les dernières images
docker compose pull

# Reconstruire et redémarrer
docker compose build --no-cache
docker compose up -d
```

### Mise à Jour de la Base de Données

```bash
# Backup avant mise à jour
docker compose exec postgres pg_dump -U gotham gotham > backup.sql

# Appliquer les migrations
docker compose exec orchestrator python -m alembic upgrade head
```

---

## Troubleshooting

### Problèmes Courants

#### Kafka ne démarre pas (NodeExistsException)

```bash
# Symptôme: Kafka crash avec "KeeperErrorCode = NodeExists"
# Cause: Race condition au redémarrage avec ZooKeeper

# Solution: Redémarrer séquentiellement
docker compose restart zookeeper
sleep 5
docker compose restart kafka
```

#### BFF "Error fetching missions: ReadTimeout"

```bash
# Symptôme: [BFF] Error fetching missions: ReadTimeout
# Cause: L'orchestrator est occupé avec une mission CrewAI (single worker)

# Solution 1: Attendre que la mission se termine
# Solution 2: Redémarrer l'orchestrator si bloqué
docker compose restart recon-orchestrator

# Note: Le timeout BFF est configuré à 60s depuis v3.2.1
```

#### UI affiche "No missions found"

```bash
# Symptôme: La page history n'affiche rien
# Cause: L'UI ne peut pas atteindre le BFF Gateway

# Vérifier que tous les services sont healthy
docker ps --format "table {{.Names}}\t{{.Status}}"

# Vérifier que le BFF répond
curl http://localhost:8080/health

# Vérifier GraphQL
curl -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ missions { items { id } } }"}'

# Si le GraphQL timeout, l'orchestrator est probablement bloqué
docker compose restart recon-orchestrator
```

#### Orchestrator "unhealthy"

```bash
# Symptôme: Container orchestrator marqué "unhealthy"
# Cause: L'exécution CrewAI bloque le worker uvicorn unique

# Vérifier le statut
docker ps --filter name=orchestrator

# Redémarrer si nécessaire
docker compose restart recon-orchestrator
```

#### Service ne répond pas

```bash
# Vérifier les logs
docker compose logs <service>

# Redémarrer le service
docker compose restart <service>

# Vérifier les dépendances
docker compose ps
```

#### Port déjà utilisé

```bash
# Trouver le processus
lsof -i :8000

# Changer le port dans .env ou docker-compose.yml
```

### Logs de Debug

```bash
# Activer les logs détaillés
docker compose logs -f --tail=100

# Filtrer par service
docker compose logs -f orchestrator bff-gateway

# Exporter les logs
docker compose logs > logs.txt
```

---

## Production

### Recommandations

1. **Utiliser des secrets Docker** pour les mots de passe
2. **Configurer des replicas** pour la haute disponibilité
3. **Activer TLS** pour les communications
4. **Configurer des backups** automatiques
5. **Monitorer** avec Prometheus/Grafana

### Docker Secrets

```yaml
# docker-compose.prod.yml
services:
  postgres:
    secrets:
      - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

### Replicas

```yaml
# docker-compose.prod.yml
services:
  bff-gateway:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
```
