# Architecture Overview - Recon Gotham v3.2

## Introduction

Recon Gotham v3.2 est une plateforme de reconnaissance offensive automatisée basée sur une architecture microservices event-driven. Elle combine l'intelligence artificielle (agents CrewAI) avec des outils de sécurité traditionnels pour cartographier la surface d'attaque de domaines web.

**Nouveautés v3.2:**
- **Reflection Architecture** - Auto-validation et enrichissement des résultats
- **UI AssetGraph amélioré** - Support complet des nodes AGENT_RUN, TOOL_CALL, DNS_RECORD
- **SSE Reconnexion** - Gestion des SNAPSHOT et Last-Event-ID

---

## Principes Architecturaux

### 1. Microservices

Chaque composant fonctionnel est isolé dans son propre service avec:
- Son propre cycle de vie
- Sa propre base de données (Database per Service)
- Ses propres API REST/gRPC
- Communication asynchrone via Kafka

### 2. Event-Driven Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        KAFKA BROKER                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │ graph.events│ │ logs.recon  │ │mission.state│ │workflow.trace││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────┘
         ▲                ▲                ▲                ▲
         │                │                │                │
    ┌────┴────┐     ┌─────┴────┐     ┌─────┴────┐     ┌────┴────┐
    │ Graph   │     │Orchestrator│    │ Phase   │     │  BFF    │
    │ Service │     │           │     │Services │     │ Gateway │
    └─────────┘     └───────────┘     └─────────┘     └─────────┘
```

### 3. CQRS (Command Query Responsibility Segregation)

Le Graph Service implémente CQRS:
- **Commands**: Création/Modification de noeuds et edges
- **Queries**: Lecture optimisée avec filtres et pagination
- **Events**: Diffusion des changements via Kafka

### 4. API Gateway Pattern

Le BFF Gateway centralise:
- GraphQL pour les requêtes complexes
- WebSocket pour le temps réel
- SSE pour le streaming d'événements
- Agrégation des données de multiples services

---

## Couches de l'Architecture

### Layer 1: Presentation (Frontend)

```
┌─────────────────────────────────────────────────────────────────┐
│                     GOTHAM-UI (Next.js 14)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      App Router                           │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐ │   │
│  │  │Dashboard│ │ Mission │ │Workflow │ │    Settings     │ │   │
│  │  │  Page   │ │ Details │ │  View   │ │      Page       │ │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Zustand Stores                         │   │
│  │  ┌────────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ │   │
│  │  │missionStore│ │graphStore │ │workflowStore│ │uiStore  │ │   │
│  │  └────────────┘ └───────────┘ └───────────┘ └──────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Providers                               │   │
│  │  ┌────────────────────┐ ┌────────────────────────────┐   │   │
│  │  │ LiveStreamProvider │ │    React Query Provider    │   │   │
│  │  │   (WebSocket/SSE)  │ │      (Data Fetching)       │   │   │
│  │  └────────────────────┘ └────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 2: API Gateway

```
┌─────────────────────────────────────────────────────────────────┐
│                    BFF GATEWAY (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Strawberry GraphQL                     │   │
│  │  Queries  │  Mutations  │  Subscriptions                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Service Proxies                        │   │
│  │  ┌────────────┐ ┌───────────┐ ┌───────────────────────┐  │   │
│  │  │Orchestrator│ │  Graph    │ │   Phase Services      │  │   │
│  │  │   Proxy    │ │  Proxy    │ │      Proxies          │  │   │
│  │  └────────────┘ └───────────┘ └───────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Event Streaming                         │   │
│  │  ┌────────────────┐ ┌────────────────────────────────┐   │   │
│  │  │ Kafka Consumer │ │   SSE/WebSocket Publishers    │   │   │
│  │  │   (Events)     │ │      (Real-time delivery)      │   │   │
│  │  └────────────────┘ └────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 3: Application Services

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION SERVICES                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              RECON ORCHESTRATOR (8000)                    │   │
│  │  ┌────────────┐ ┌────────────┐ ┌───────────────────────┐ │   │
│  │  │  Mission   │ │   Phase    │ │    CrewAI Engine      │ │   │
│  │  │  Manager   │ │ Coordinator│ │   (Agents + Tasks)    │ │   │
│  │  └────────────┘ └────────────┘ └───────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                GRAPH SERVICE (8001)                       │   │
│  │  ┌────────────┐ ┌────────────┐ ┌───────────────────────┐ │   │
│  │  │   Node     │ │   Edge     │ │    Query Engine       │ │   │
│  │  │  Manager   │ │  Manager   │ │   (Filters, Stats)    │ │   │
│  │  └────────────┘ └────────────┘ └───────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    PHASE SERVICES                           │ │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │ │
│  │  │ OSINT  │ │ Active │ │Endpoint│ │ Verify │ │Reporter│   │ │
│  │  │ (8002) │ │ (8003) │ │ (8004) │ │ (8005) │ │ (8006) │   │ │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 4: Infrastructure

```
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      KAFKA                                │   │
│  │  Topics: graph.events | logs.recon | mission.state        │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────┐ ┌──────────────────────────────────┐   │
│  │     PostgreSQL      │ │           SQLite                 │   │
│  │  (Orchestrator DB)  │ │      (Graph Service DB)          │   │
│  └─────────────────────┘ └──────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   SCANNER PROXY                           │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐ │   │
│  │  │Subfinder│ │  HTTPX  │ │ Nuclei  │ │      FFUF       │ │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      OLLAMA                               │   │
│  │         Local LLM (qwen2.5-coder:7b, qwen2.5:14b)        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flux de Données

### 1. Flux d'une Mission

```
User Request → BFF Gateway → Orchestrator
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Create Mission Record     │
                    │     (PostgreSQL)              │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │     Start Phase Pipeline      │
                    └──────────────┬───────────────┘
                                   │
     ┌─────────────────────────────┼─────────────────────────────┐
     ▼                             ▼                             ▼
┌─────────┐                 ┌─────────────┐              ┌─────────────┐
│  OSINT  │ ──────────────▶ │Active Recon │ ──────────▶ │ Endpoint    │
│ Phase 1 │                 │   Phase 3   │              │ Intel Ph 4  │
└─────────┘                 └─────────────┘              └──────┬──────┘
                                                                │
     ┌──────────────────────────────────────────────────────────┘
     ▼
┌─────────────┐              ┌─────────────┐
│Verification │ ──────────▶ │  Reporter   │
│  Phase 5    │              │   Phase 6   │
└─────────────┘              └──────┬──────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │     Mission Complete          │
                    │     (Graph + Reports ready)   │
                    └───────────────────────────────┘
```

### 2. Flux des Événements

```
┌──────────────────────────────────────────────────────────────────┐
│                    EVENT FLOW                                     │
│                                                                   │
│  Service Action                                                   │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────┐                                                  │
│  │ Produce     │                                                  │
│  │ Event       │──────────────────────────────┐                  │
│  └─────────────┘                              │                  │
│                                               ▼                  │
│                                    ┌───────────────────┐         │
│                                    │    KAFKA          │         │
│                                    │    Topic          │         │
│                                    └─────────┬─────────┘         │
│                                              │                   │
│            ┌─────────────────────────────────┼──────────────┐    │
│            ▼                                 ▼              ▼    │
│    ┌───────────────┐               ┌────────────────┐ ┌────────┐│
│    │ Graph Service │               │  BFF Gateway   │ │ Other  ││
│    │ (Persist)     │               │ (Stream to UI) │ │Consumer││
│    └───────────────┘               └────────────────┘ └────────┘│
│                                              │                   │
│                                              ▼                   │
│                                    ┌────────────────────┐        │
│                                    │   WebSocket/SSE    │        │
│                                    │   to Frontend      │        │
│                                    └────────────────────┘        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Event Envelope v2 (v3.1)

### Structure Standardisée

Tous les événements émis suivent le format Event Envelope v2:

```json
{
  "schema_version": "v2",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "AGENT_STARTED",
  "ts": "2025-12-15T18:00:00.000Z",
  "mission_id": "mission-uuid",
  "trace_id": "trc_a1b2c3d4e5f67890",
  "span_id": "spn_12345678",
  "producer": "recon-orchestrator",
  "phase": "OSINT",
  "payload": {
    "agent_id": "pathfinder",
    "task": "subdomain_enumeration"
  }
}
```

### Champs de Traçabilité

| Champ | Description | Génération |
|-------|-------------|------------|
| `schema_version` | Version du format | Constante "v2" |
| `event_id` | ID unique de l'événement | UUID v4 |
| `trace_id` | ID de trace distribuée | `trc_` + 16 hex chars |
| `span_id` | ID du span dans la trace | `spn_` + 8 hex chars |
| `producer` | Service émetteur | Nom du service |

### Failure Taxonomy (P1.1)

Les erreurs suivent une taxonomie structurée:

```json
{
  "event_type": "ERROR",
  "payload": {
    "error_code": "E202",
    "message": "Tool execution failed: subfinder timeout",
    "stage": "OSINT",
    "retryable": true,
    "recoverable": true,
    "details": {
      "tool": "subfinder",
      "timeout_ms": 30000
    }
  }
}
```

### Codes d'Erreur

| Code | Catégorie | Description |
|------|-----------|-------------|
| E101 | Network | Timeout réseau |
| E102 | Network | DNS resolution failed |
| E103 | Network | Connection refused |
| E201 | Parsing | JSON parse error |
| E202 | Tool | Tool execution failed |
| E203 | Tool | Tool not found |
| E301 | Validation | Input validation failed |
| E302 | Validation | Out of scope |
| E401 | Auth | Unauthorized |
| E402 | Auth | Rate limited |
| E501 | Internal | Internal error |
| E502 | Internal | Database error |
| E503 | Internal | Kafka error |
| E504 | Internal | Service unavailable |

### Stages de Mission

| Stage | Description |
|-------|-------------|
| INIT | Initialisation de la mission |
| OSINT | Reconnaissance passive |
| ACTIVE_RECON | Reconnaissance active |
| ENDPOINT_INTEL | Enrichissement des endpoints |
| VERIFICATION | Tests de sécurité |
| REPORTING | Génération de rapports |
| FINALIZE | Finalisation |

---

## Composants Clés

### Orchestrator Service

Le cerveau du système qui:
- Gère le cycle de vie des missions (CRUD)
- Coordonne l'exécution des phases
- Intègre le moteur CrewAI pour les agents
- Émet des événements de progression

### Graph Service

Le système de stockage central qui:
- Stocke tous les assets découverts (noeuds et edges)
- Implémente CQRS pour les performances
- Supporte les requêtes complexes (filtres, stats, export)
- Diffuse les changements en temps réel

### BFF Gateway

Le point d'entrée unifié qui:
- Expose une API GraphQL riche
- Gère les souscriptions temps réel
- Agrège les données de multiples services
- Authentifie et autorise les requêtes

### Phase Services

Services spécialisés par phase:
- **OSINT**: Reconnaissance passive (Subfinder, Wayback)
- **Active Recon**: Probing HTTP (HTTPX, crawling)
- **Endpoint Intel**: Enrichissement et scoring
- **Verification**: Tests de sécurité contrôlés
- **Reporter**: Génération de rapports

### Scanner Proxy

Interface unifiée vers les outils de sécurité:
- Abstraction des détails d'implémentation
- Gestion du caching et de l'idempotence
- Exécution distribuée possible
- Support gRPC et HTTP

---

## Scalabilité

### Horizontal Scaling

```
                    ┌─────────────────────────────┐
                    │       Load Balancer         │
                    └──────────────┬──────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│ BFF Gateway 1 │          │ BFF Gateway 2 │          │ BFF Gateway N │
└───────────────┘          └───────────────┘          └───────────────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     Kafka Cluster           │
                    │   (3+ brokers for HA)       │
                    └─────────────────────────────┘
```

### Points de Scaling

| Composant | Méthode | Notes |
|-----------|---------|-------|
| BFF Gateway | Replicas horizontaux | Stateless, facile à scaler |
| Phase Services | Replicas + Kafka partitions | Consumer groups |
| Graph Service | Read replicas | Pour les queries lourdes |
| Kafka | Partitions + Replicas | Débit et durabilité |
| Scanner Proxy | Worker pool | Queue de tâches |

---

## Sécurité

### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              API Gateway (BFF)                          │ │
│  │  • JWT Validation                                       │ │
│  │  • Rate Limiting                                        │ │
│  │  • CORS Policy                                          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Service-to-Service                         │ │
│  │  • Internal API Keys                                    │ │
│  │  • mTLS (optional)                                      │ │
│  │  • Network Isolation (Docker network)                   │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Data Security                              │ │
│  │  • Encrypted at rest (database)                         │ │
│  │  • Scope validation (target domain)                     │ │
│  │  • Audit logging                                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Scope Validation

Le système implémente une validation stricte du scope:

```python
def is_in_scope(hostname: str, target_domain: str) -> bool:
    """
    Vérifie qu'un hostname appartient au domaine cible.
    Empêche la reconnaissance hors-scope.
    """
    if not target_domain:
        return True
    return hostname.endswith(target_domain) or hostname == target_domain
```

---

## Observabilité

### Logging

```
┌─────────────────────────────────────────────────────────────┐
│                    STRUCTURED LOGGING                        │
│                                                              │
│  {                                                           │
│    "timestamp": "2025-12-15T18:00:00.000Z",                 │
│    "level": "INFO",                                          │
│    "service": "orchestrator",                                │
│    "run_id": "uuid",                                         │
│    "mission_id": "uuid",                                     │
│    "phase": "passive_recon",                                 │
│    "message": "Subfinder completed",                         │
│    "metadata": {                                             │
│      "subdomains_found": 48,                                 │
│      "duration_ms": 12500                                    │
│    }                                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

### Metrics

| Métrique | Type | Description |
|----------|------|-------------|
| `mission_duration_seconds` | Histogram | Durée totale des missions |
| `phase_duration_seconds` | Histogram | Durée par phase |
| `nodes_created_total` | Counter | Total de noeuds créés |
| `tool_calls_total` | Counter | Total d'appels d'outils |
| `errors_total` | Counter | Total d'erreurs |

### Health Checks

Tous les services exposent `/health`:

```json
{
  "status": "healthy",
  "service": "graph-service",
  "kafka": "connected",
  "database": "connected",
  "timestamp": "2025-12-15T18:00:00Z"
}
```

---

## Prochaines Évolutions

### Roadmap Technique

1. **v3.1**: ✅ POC Robustness (Event Envelope v2, Idempotence, SSE Reconnect)
2. **v3.2**: ✅ Reflection Architecture + UI Fixes
3. **v3.3**: Support multi-tenant + API publique OAuth2
4. **v4.0**: Architecture distribuée complète

### v3.2 Implémenté

- [x] **Reflection Architecture** (P0.6)
  - [x] ReflectorAgent pour validation des résultats
  - [x] ResultAnalyzer (subfinder, httpx, dns, wayback)
  - [x] ScriptGenerator avec 6 templates
  - [x] PythonScriptExecutorTool avec validation AST
  - [x] ReflectionLoop intégré dans crew_runner
- [x] **UI AssetGraph Fixes**
  - [x] Support AGENT_RUN nodes (couleur, shape, edges)
  - [x] Support TOOL_CALL nodes (couleur, shape, edges vers agents)
  - [x] Support DNS_RECORD nodes
  - [x] Correction edges HYPOTHESIS
  - [x] Gestion événements SNAPSHOT
- [x] **GraphQL Schema Fix**
  - [x] MissionConnection.items (correction pour UI)

### v3.1 Implémenté

- [x] Event Envelope v2 (schema_version, trace_id, span_id)
- [x] Idempotence via edge.id déterministe (SHA1)
- [x] `make_json_safe()` pour sérialisation robuste
- [x] Atomic batch endpoint (`/api/v1/graph/batchUpsert`)
- [x] SSE reconnexion (Ring buffer + Last-Event-ID + Snapshot)
- [x] Failure taxonomy (error_code, stage, retryable)

### Améliorations Prévues

- [ ] Cache Redis pour les requêtes fréquentes
- [ ] OpenTelemetry pour le tracing distribué
- [ ] Helm charts pour Kubernetes
- [ ] Support de multiples LLM providers
- [ ] LLM-powered script generation (templates dynamiques)
- [ ] Cross-tool correlation analysis
