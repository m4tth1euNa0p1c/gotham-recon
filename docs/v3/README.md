# Recon Gotham v3.2 - Documentation Technique Complète

> **Plateforme de Reconnaissance Offensive Multi-Agents**
>
> Version: 3.2.0 | Dernière mise à jour: Décembre 2025

---

## Changelog v3.2 (Reflection Architecture + UI Fixes)

### P0.6 - Reflection Architecture (Nouveau)

| Feature | Description |
|---------|-------------|
| **ReflectorAgent** | Agent spécialisé pour la validation et l'enrichissement des résultats |
| **ResultAnalyzer** | Analyse les résultats des outils (subfinder, httpx, dns, wayback) pour détecter les gaps |
| **ScriptGenerator** | Génère des scripts Python d'investigation à partir de templates |
| **PythonScriptExecutorTool** | Exécution sécurisée de scripts avec validation AST |
| **ReflectionLoop** | Orchestration du cycle de réflexion après chaque tool call |

**Templates de scripts disponibles:**
- `dns_bruteforce` - Bruteforce DNS pour découvrir des sous-domaines cachés
- `tech_fingerprint` - Fingerprinting technologique avancé
- `config_checker` - Détection de fichiers de configuration exposés
- `port_check` - Scan de ports additionnels
- `header_analysis` - Analyse approfondie des headers HTTP
- `certificate_check` - Analyse des certificats SSL/TLS

### UI Fixes (AssetGraph)

| Fix | Description |
|-----|-------------|
| **AGENT_RUN nodes** | Ajout couleur (#14b8a6), shape, edges vers DOMAIN |
| **TOOL_CALL nodes** | Ajout couleur (#0ea5e9), shape barrel, edges vers AGENT_RUN |
| **DNS_RECORD nodes** | Nouveau type avec edges vers SUBDOMAIN |
| **HYPOTHESIS edges** | Correction des connexions vers ENDPOINT/HTTP_SERVICE |
| **SNAPSHOT handling** | Gestion des événements SNAPSHOT dans workflowStore |
| **GraphQL items fix** | Correction MissionConnection.items pour l'UI |

---

## Changelog v3.1 (POC Robustness)

### P0 - Must-Have (Implémenté)

| ID | Feature | Description |
|----|---------|-------------|
| **P0.1** | Event Envelope v2 | Schema version, event_id, trace_id, span_id, producer |
| **P0.2** | Idempotence | Deterministic edge.id via SHA1 hash + INSERT OR IGNORE |
| **P0.3** | JSON Safety | `make_json_safe()` recursive pour éviter les erreurs de sérialisation |
| **P0.4** | Atomic Batch | `POST /api/v1/graph/batchUpsert` avec transaction atomique |
| **P0.5** | SSE Reconnect | Ring buffer + Last-Event-ID + snapshot endpoint |

### P1 - Recommended (Implémenté)

| ID | Feature | Description |
|----|---------|-------------|
| **P1.1** | Failure Taxonomy | error_code (E101-E504), stage, retryable, recoverable |

### Nouveaux Endpoints

- `POST /api/v1/graph/batchUpsert` - Atomic batch upsert (Graph Service)
- `GET /api/v1/sse/snapshot/{run_id}` - Snapshot pour reconnexion (BFF Gateway)
- `GET /api/v1/sse/events/{run_id}?lastEventId=X` - SSE avec reconnexion (BFF Gateway)

---

## Table des Matières

### Architecture
- [Vue d'ensemble](./architecture/overview.md) - Architecture globale du système
- [Diagrammes](./architecture/diagrams.md) - Schémas d'architecture et flux de données
- [Patterns de conception](./architecture/patterns.md) - CQRS, Event Sourcing, Microservices

### Services Backend
- [Recon Orchestrator](./services/orchestrator.md) - Service principal de coordination (Port 8000)
- [Graph Service](./services/graph-service.md) - CQRS Read/Write pour Asset Graph (Port 8001)
- [BFF Gateway](./services/bff-gateway.md) - API Gateway GraphQL (Port 8080)
- [OSINT Runner](./services/osint-runner.md) - Phase 1 - Reconnaissance passive (Port 8002)
- [Active Recon](./services/active-recon.md) - Phase 3 - HTTP probing (Port 8003)
- [Endpoint Intel](./services/endpoint-intel.md) - Phase 4 - Enrichissement (Port 8004)
- [Verification](./services/verification.md) - Phase 5 - Tests de sécurité (Port 8005)
- [Reporter](./services/reporter.md) - Phase 6 - Génération de rapports (Port 8006)
- [Planner](./services/planner.md) - Scoring des chemins d'attaque (Port 8007)
- [Scanner Proxy](./services/scanner-proxy.md) - Interface gRPC pour outils (Port 8051)

### API Reference
- [OpenAPI Specification](./api/openapi.yaml) - Spécification OpenAPI 3.1 complète
- [GraphQL Schema](./api/graphql-schema.md) - Schéma GraphQL complet
- [REST Endpoints](./api/rest-endpoints.md) - Documentation des endpoints REST
- [WebSocket Events](./api/websocket-events.md) - Événements temps réel
- [Kafka Topics](./api/kafka-topics.md) - Topics et messages Kafka

### Base de Données
- [Modèle de données](./database/data-model.md) - Schéma conceptuel
- [Schémas PostgreSQL](./database/postgresql-schemas.md) - Tables et relations
- [SQLite Schema](./database/sqlite-schema.md) - Schéma du Graph Service
- [Migrations](./database/migrations.md) - Gestion des migrations

### Déploiement
- [Docker Compose](./deployment/docker-compose.md) - Configuration Docker
- [Variables d'environnement](./deployment/environment.md) - Configuration
- [Kubernetes](./deployment/kubernetes.md) - Déploiement K8s (optionnel)
- [Production Checklist](./deployment/production.md) - Liste de vérification

### Configuration
- [Agents CrewAI](./configuration/agents.md) - Configuration des agents
- [Tasks CrewAI](./configuration/tasks.md) - Définition des tâches
- [Budget & Limites](./configuration/budget.md) - Seuils et contraintes
- [Modes d'exécution](./configuration/modes.md) - Stealth vs Aggressive

### Frontend
- [Architecture UI](./frontend/architecture.md) - Structure Next.js
- [Composants](./frontend/components.md) - Bibliothèque de composants
- [State Management](./frontend/state.md) - Stores Zustand
- [Real-time](./frontend/realtime.md) - WebSocket et SSE

### Guides
- [Quick Start](./guides/quickstart.md) - Démarrage rapide
- [Mission Workflow](./guides/mission-workflow.md) - Flux d'une mission
- [Troubleshooting](./guides/troubleshooting.md) - Résolution de problèmes
- [Contributing](./guides/contributing.md) - Guide de contribution

---

## Quick Start

### Prérequis

```bash
# Versions requises
Docker >= 24.0
Docker Compose >= 2.20
Node.js >= 18.0 (pour l'UI)
Python >= 3.11 (pour le développement)
```

### Lancement rapide

```bash
# 1. Cloner le repository
git clone https://github.com/gotham/recon-gotham.git
cd recon-gotham

# 2. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos configurations

# 3. Lancer l'infrastructure
docker-compose up -d

# 4. Lancer l'UI (optionnel)
cd gotham-ui && npm install && npm run dev

# 5. Accéder aux services
# - UI: http://localhost:3000
# - GraphQL Playground: http://localhost:8080/graphql
# - API Orchestrator: http://localhost:8000/docs
```

### Lancer une mission

```bash
# Via API REST
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain": "example.com", "mode": "AGGRESSIVE"}'

# Via GraphQL
curl -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { startMission(input: { targetDomain: \"example.com\", mode: AGGRESSIVE }) { id status } }"
  }'

# Via CLI (développement)
python run_mission.py example.com --mode aggressive
```

---

## Architecture Globale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GOTHAM-UI (Next.js)                            │
│                                  Port 3000                                   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ GraphQL / WebSocket / SSE
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BFF GATEWAY (FastAPI)                              │
│                    GraphQL + REST + Subscriptions                            │
│                                  Port 8080                                   │
└────────────┬──────────────────────┬─────────────────────────┬───────────────┘
             │                      │                         │
             ▼                      ▼                         ▼
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────────────┐
│ RECON ORCHESTRATOR │  │   GRAPH SERVICE    │  │        KAFKA               │
│     Port 8000      │  │     Port 8001      │  │      Port 9092             │
│  Mission Control   │  │  CQRS Read/Write   │  │  Event Streaming           │
└─────────┬──────────┘  └─────────┬──────────┘  └─────────────┬──────────────┘
          │                       │                           │
          │  HTTP Calls           │ SQL                       │ Pub/Sub
          ▼                       ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE SERVICES (Pipeline)                            │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────────┤
│ OSINT Runner │ Active Recon │ Endpoint     │ Verification │ Reporter        │
│   Port 8002  │   Port 8003  │ Intel 8004   │   Port 8005  │ Port 8006       │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────────────┘
          │                                                       │
          ▼                                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SCANNER PROXY (gRPC)                                │
│                    Subfinder | HTTPX | Nuclei | FFUF                         │
│                           Port 8051 / 50051                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| **Backend Framework** | FastAPI | 0.109+ |
| **Agent Framework** | CrewAI | 0.80+ |
| **Message Broker** | Apache Kafka | 3.6+ |
| **Database (Orchestrator)** | PostgreSQL | 15+ |
| **Database (Graph)** | SQLite | 3.40+ |
| **API Gateway** | Strawberry GraphQL | 0.219+ |
| **Frontend** | Next.js | 14.2+ |
| **UI Framework** | React | 18+ |
| **State Management** | Zustand | 4.5+ |
| **Graph Visualization** | React Flow | 11+ |
| **Containerization** | Docker | 24+ |
| **LLM Provider** | Ollama | Latest |

---

## Ports et Services

| Service | Port | Protocole | Description |
|---------|------|-----------|-------------|
| Gotham UI | 3000 | HTTP | Interface utilisateur Next.js |
| BFF Gateway | 8080 | HTTP/WS | API Gateway GraphQL |
| Orchestrator | 8000 | HTTP/WS | Coordination des missions |
| Graph Service | 8001 | HTTP/WS | Gestion du graphe d'assets |
| OSINT Runner | 8002 | HTTP | Reconnaissance passive |
| Active Recon | 8003 | HTTP | Reconnaissance active |
| Endpoint Intel | 8004 | HTTP | Enrichissement endpoints |
| Verification | 8005 | HTTP | Tests de sécurité |
| Reporter | 8006 | HTTP | Génération de rapports |
| Planner | 8007 | HTTP | Scoring des attaques |
| Scanner Proxy HTTP | 8051 | HTTP | Interface HTTP pour outils |
| Scanner Proxy gRPC | 50051 | gRPC | Interface gRPC pour outils |
| Kafka | 9092 | TCP | Message broker |
| Kafka UI | 9093 | HTTP | Interface Kafka |
| PostgreSQL | 5432 | TCP | Base de données |
| Ollama | 11434 | HTTP | LLM local |

---

## Types de Noeuds (Asset Graph)

### Noeuds d'Assets
| Type | Description | Exemple d'ID |
|------|-------------|--------------|
| `DOMAIN` | Domaine racine | `domain:example.com` |
| `SUBDOMAIN` | Sous-domaine découvert | `subdomain:www.example.com` |
| `HTTP_SERVICE` | Service HTTP actif | `http_service:https://www.example.com` |
| `ENDPOINT` | Chemin API/page | `endpoint:/api/v1/users` |
| `PARAMETER` | Paramètre d'URL | `param:endpoint:/api/users:id` |
| `IP_ADDRESS` | Adresse IP | `ip:192.168.1.1` |
| `DNS_RECORD` | Enregistrement DNS | `dns:A:example.com` |
| `ASN` | Autonomous System | `asn:AS12345` |
| `ORG` | Organisation | `org:Example Inc` |

### Noeuds de Sécurité
| Type | Description | Exemple d'ID |
|------|-------------|--------------|
| `HYPOTHESIS` | Hypothèse de vulnérabilité | `hypothesis:IDOR:endpoint:/api/users` |
| `VULNERABILITY` | Vulnérabilité confirmée | `vuln:CVE-2024-1234:endpoint:/login` |
| `ATTACK_PATH` | Chemin d'attaque suggéré | `attack_path:/admin:sqli` |

### Noeuds de Workflow
| Type | Description | Exemple d'ID |
|------|-------------|--------------|
| `AGENT_RUN` | Exécution d'un agent | `agent-pathfinder-1702666849000` |
| `TOOL_CALL` | Appel d'un outil | `tool-subfinder-1702666849000` |
| `LLM_REASONING` | Raisonnement LLM | `llm-reasoning-1702666849000` |

---

## Types de Relations (Edges)

### Relations d'Assets
| Type | De → Vers | Description |
|------|-----------|-------------|
| `HAS_SUBDOMAIN` | DOMAIN → SUBDOMAIN | Domaine contient sous-domaine |
| `RESOLVES_TO` | SUBDOMAIN → IP_ADDRESS | Résolution DNS |
| `SERVES` | IP_ADDRESS → HTTP_SERVICE | IP héberge service |
| `EXPOSES_HTTP` | SUBDOMAIN → HTTP_SERVICE | Subdomain expose HTTP |
| `EXPOSES_ENDPOINT` | HTTP_SERVICE → ENDPOINT | Service expose endpoint |
| `HAS_PARAM` | ENDPOINT → PARAMETER | Endpoint a paramètre |
| `HAS_HYPOTHESIS` | ENDPOINT → HYPOTHESIS | Endpoint a hypothèse |
| `HAS_VULNERABILITY` | ENDPOINT → VULNERABILITY | Endpoint a vulnérabilité |
| `TARGETS` | ATTACK_PATH → ENDPOINT | Chemin cible endpoint |

### Relations de Workflow
| Type | De → Vers | Description |
|------|-----------|-------------|
| `TRIGGERS` | AGENT_RUN → AGENT_RUN | Agent déclenche agent |
| `USES_TOOL` | AGENT_RUN → TOOL_CALL | Agent utilise outil |
| `PRODUCES` | TOOL_CALL → NODE | Outil produit asset |
| `REFINES` | AGENT_RUN → HYPOTHESIS | Agent affine hypothèse |
| `LINKS_TO` | NODE → NODE | Lien générique |

---

## Licence

Ce projet est sous licence MIT. Voir [LICENSE](../LICENSE) pour plus de détails.

---

## Support

- **Documentation**: https://docs.gotham-recon.io
- **Issues**: https://github.com/gotham/recon-gotham/issues
- **Discussions**: https://github.com/gotham/recon-gotham/discussions
