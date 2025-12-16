# Graph Service

> **Service CQRS pour la gestion du graphe d'assets**
>
> Port: 8001 | Base URL: `http://localhost:8001`
>
> Version: 3.2.0 | Dernière mise à jour: Décembre 2025

---

## Changelog v3.2

### Reflection Integration

| Feature | Description |
|---------|-------------|
| **Reflection enrichment** | Support des enrichissements automatiques depuis le ReflectionLoop |
| **Graph updates from scripts** | Intégration des résultats de scripts d'investigation |
| **Reflection metrics** | Tracking des nodes/edges ajoutés par réflexion |

### Node Type Updates

| Type | Description |
|------|-------------|
| **DNS_RECORD** | Nouveau type pour les enregistrements DNS (A, AAAA, CNAME, MX, TXT) |

---

## Vue d'Ensemble

Le Graph Service est le service de stockage central pour tous les assets découverts pendant les missions de reconnaissance. Il implémente le pattern CQRS (Command Query Responsibility Segregation) pour optimiser les performances de lecture et d'écriture.

### Responsabilités

- Stockage des noeuds (assets, workflow, sécurité)
- Gestion des relations (edges)
- Requêtes complexes avec filtres
- Export du graphe complet
- Diffusion des changements en temps réel
- Stockage des layouts de visualisation

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       GRAPH SERVICE                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      FastAPI Router                         │ │
│  │  /api/v1/nodes | /api/v1/edges | /api/v1/missions | /ws    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                     Write Path (CQRS)                      │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │   Validator  │──▶│   Writer    │──▶│  Kafka Producer │ │  │
│  │  │    (DTO)     │  │  (SQLite)   │  │   (Events)      │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                     Read Path (CQRS)                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │Query Builder │──▶│   SQLite    │──▶│    Response     │ │  │
│  │  │  (Filters)   │  │   Reader    │  │   Formatter     │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │                   WebSocket Handler                        │  │
│  │  ┌──────────────────────────────────────────────────────┐ │  │
│  │  │ Kafka Consumer → Event Router → WebSocket Broadcast  │ │  │
│  │  └──────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Idempotence (v3.1)

### Deterministic Edge IDs (P0.2)

Les edges utilisent des IDs déterministes calculés via SHA1:

```python
def generate_edge_id(from_node: str, to_node: str, relation: str, mission_id: str) -> str:
    """
    Génère un ID d'edge déterministe.
    Formula: edge_key = "{relation}|{from}|{to}|{mission}" → sha1[:16]
    """
    edge_key = f"{relation}|{from_node}|{to_node}|{mission_id}"
    return hashlib.sha1(edge_key.encode()).hexdigest()[:16]
```

**Avantages:**
- Même edge = même ID (idempotent)
- INSERT OR IGNORE évite les doublons
- Résilient aux re-traitements

### Upsert Behavior

| Opération | Comportement |
|-----------|--------------|
| Nodes | `INSERT OR REPLACE` - Met à jour si existe |
| Edges | `INSERT OR IGNORE` - Ignore si existe |

---

## API Endpoints

### Nodes

#### POST `/api/v1/nodes`
Créer un nouveau noeud.

**Request Body:**
```json
{
  "id": "subdomain:www.example.com",
  "type": "SUBDOMAIN",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "properties": {
    "name": "www.example.com",
    "subdomain": "www.example.com",
    "source": "subfinder"
  }
}
```

**Response 201:**
```json
{
  "id": "subdomain:www.example.com",
  "type": "SUBDOMAIN",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "properties": {
    "name": "www.example.com",
    "subdomain": "www.example.com",
    "source": "subfinder"
  },
  "created_at": "2025-12-15T18:00:00Z",
  "updated_at": "2025-12-15T18:00:00Z"
}
```

#### GET `/api/v1/nodes`
Lister les noeuds avec filtres.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `mission_id` | string | Filtrer par mission |
| `type` | string | Filtrer par type de noeud |
| `limit` | integer | Limite (default: 1000) |

**Response 200:**
```json
{
  "nodes": [
    {
      "id": "subdomain:www.example.com",
      "type": "SUBDOMAIN",
      "mission_id": "...",
      "properties": { /* ... */ },
      "created_at": "2025-12-15T18:00:00Z",
      "updated_at": "2025-12-15T18:00:00Z"
    }
  ],
  "total": 48,
  "limit": 1000,
  "offset": 0
}
```

#### GET `/api/v1/nodes/{node_id}`
Obtenir un noeud par ID.

#### PUT `/api/v1/nodes/{node_id}`
Mettre à jour les propriétés d'un noeud.

**Request Body:**
```json
{
  "properties": {
    "risk_score": 75,
    "category": "API"
  }
}
```

#### DELETE `/api/v1/nodes/{node_id}`
Supprimer un noeud.

#### POST `/api/v1/nodes/query`
Requête avancée avec filtres.

**Request Body:**
```json
{
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "node_types": ["ENDPOINT", "HYPOTHESIS"],
  "risk_score_min": 50,
  "limit": 100,
  "offset": 0
}
```

#### POST `/api/v1/nodes/batch`
Créer plusieurs noeuds en batch.

**Request Body:**
```json
[
  {
    "id": "subdomain:www.example.com",
    "type": "SUBDOMAIN",
    "mission_id": "...",
    "properties": { /* ... */ }
  },
  {
    "id": "subdomain:api.example.com",
    "type": "SUBDOMAIN",
    "mission_id": "...",
    "properties": { /* ... */ }
  }
]
```

**Response 201:**
```json
{
  "created": 2,
  "nodes": [ /* ... */ ]
}
```

---

### Edges

#### POST `/api/v1/edges`
Créer une relation entre deux noeuds.

**Request Body:**
```json
{
  "from_node": "subdomain:www.example.com",
  "to_node": "http_service:https://www.example.com",
  "edge_type": "EXPOSES_HTTP",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "properties": {}
}
```

**Response 201:**
```json
{
  "status": "created",
  "edge": {
    "id": "edge-xxx",
    "from_node": "subdomain:www.example.com",
    "to_node": "http_service:https://www.example.com",
    "edge_type": "EXPOSES_HTTP",
    "mission_id": "...",
    "properties": {},
    "created_at": "2025-12-15T18:00:00Z"
  }
}
```

#### POST `/api/v1/edges/batch`
Créer plusieurs edges en batch.

#### GET `/api/v1/missions/{mission_id}/edges`
Obtenir toutes les edges d'une mission.

**Response 200:**
```json
{
  "edges": [
    {
      "id": "edge-xxx",
      "from_node": "subdomain:www.example.com",
      "to_node": "http_service:https://www.example.com",
      "edge_type": "EXPOSES_HTTP",
      "mission_id": "...",
      "properties": {},
      "created_at": "2025-12-15T18:00:00Z"
    }
  ],
  "total": 512
}
```

---

### Batch Upsert (v3.1)

#### POST `/api/v1/graph/batchUpsert`
Atomic batch upsert de noeuds et edges dans une transaction unique (P0.4).

**Request Body:**
```json
{
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "nodes": [
    {
      "id": "subdomain:www.example.com",
      "type": "SUBDOMAIN",
      "properties": {
        "name": "www.example.com",
        "source": "subfinder"
      }
    },
    {
      "id": "subdomain:api.example.com",
      "type": "SUBDOMAIN",
      "properties": {
        "name": "api.example.com",
        "source": "subfinder"
      }
    }
  ],
  "edges": [
    {
      "from_node": "domain:example.com",
      "to_node": "subdomain:www.example.com",
      "relation": "HAS_SUBDOMAIN"
    },
    {
      "from_node": "domain:example.com",
      "to_node": "subdomain:api.example.com",
      "relation": "HAS_SUBDOMAIN"
    }
  ]
}
```

**Response 200:**
```json
{
  "status": "success",
  "nodes_created": 2,
  "edges_created": 2,
  "nodes": [
    {
      "id": "subdomain:www.example.com",
      "type": "SUBDOMAIN",
      "mission_id": "550e8400-...",
      "properties": { /* ... */ },
      "created_at": "2025-12-15T18:00:00Z"
    }
  ],
  "edges": [
    {
      "id": "a1b2c3d4e5f67890",
      "from_node": "domain:example.com",
      "to_node": "subdomain:www.example.com",
      "relation": "HAS_SUBDOMAIN",
      "mission_id": "550e8400-...",
      "created_at": "2025-12-15T18:00:00Z"
    }
  ]
}
```

**Caractéristiques:**
- Transaction atomique (tout ou rien)
- Nodes: INSERT OR REPLACE (upsert)
- Edges: INSERT OR IGNORE (idempotent)
- IDs d'edges déterministes via SHA1

**Error Response 500:**
```json
{
  "detail": "Batch upsert failed: <error message>",
  "error": "<error details>"
}
```

---

### Statistics & Export

#### GET `/api/v1/missions/{mission_id}/stats`
Obtenir les statistiques du graphe.

**Response 200:**
```json
{
  "total_nodes": 256,
  "total_edges": 512,
  "nodes_by_type": {
    "DOMAIN": 1,
    "SUBDOMAIN": 48,
    "HTTP_SERVICE": 19,
    "ENDPOINT": 156,
    "PARAMETER": 32,
    "HYPOTHESIS": 15,
    "VULNERABILITY": 0,
    "IP_ADDRESS": 12,
    "DNS_RECORD": 20,
    "AGENT_RUN": 16,
    "TOOL_CALL": 12
  },
  "edges_by_type": {
    "HAS_SUBDOMAIN": 48,
    "RESOLVES_TO": 48,
    "EXPOSES_HTTP": 19,
    "EXPOSES_ENDPOINT": 156,
    "HAS_PARAM": 32,
    "HAS_HYPOTHESIS": 15,
    "TRIGGERS": 16,
    "USES_TOOL": 12,
    "PRODUCES": 256
  },
  "risk_distribution": {
    "critical": 0,
    "high": 5,
    "medium": 25,
    "low": 126,
    "info": 0
  }
}
```

#### GET `/api/v1/missions/{mission_id}/export`
Exporter le graphe complet en JSON.

**Response 200:**
```json
{
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "nodes": [ /* all nodes */ ],
  "edges": [ /* all edges */ ],
  "timestamp": "2025-12-15T18:30:00Z"
}
```

---

### Workflow

#### POST `/api/v1/workflow/query`
Requête spécifique aux noeuds de workflow.

**Request Body:**
```json
{
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "node_types": ["AGENT_RUN", "TOOL_CALL"]
}
```

**Response 200:**
```json
{
  "nodes": [
    {
      "id": "agent-pathfinder-1702666849000",
      "type": "AGENT_RUN",
      "mission_id": "...",
      "properties": {
        "agent_id": "pathfinder",
        "agent_name": "pathfinder",
        "task": "Subdomain enumeration",
        "phase": "OSINT",
        "status": "completed",
        "start_time": "2025-12-15T18:00:00Z",
        "end_time": "2025-12-15T18:02:00Z",
        "duration": 120000
      }
    }
  ],
  "edges": [
    {
      "from_node": "agent-pathfinder-xxx",
      "to_node": "tool-subfinder-xxx",
      "edge_type": "USES_TOOL"
    }
  ],
  "total_nodes": 28,
  "total_edges": 56
}
```

---

### Layouts

#### POST `/api/v1/layouts/{mission_id}`
Sauvegarder un layout de visualisation.

**Request Body:**
```json
{
  "positions": {
    "agent-pathfinder-xxx": { "x": 100, "y": 200 },
    "tool-subfinder-xxx": { "x": 250, "y": 300 }
  },
  "zoom": 0.8,
  "pan": { "x": 50, "y": 100 }
}
```

**Response 200:**
```json
{
  "status": "saved",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### GET `/api/v1/layouts/{mission_id}`
Récupérer un layout sauvegardé.

**Response 200:**
```json
{
  "positions": {
    "agent-pathfinder-xxx": { "x": 100, "y": 200 }
  },
  "zoom": 0.8,
  "pan": { "x": 50, "y": 100 },
  "updated_at": "2025-12-15T18:30:00Z"
}
```

---

### Data Management

#### DELETE `/api/v1/missions/{mission_id}`
Supprimer une mission et toutes ses données.

#### DELETE `/api/v1/missions/{mission_id}/history`
Supprimer uniquement l'historique (logs) d'une mission.

#### DELETE `/api/v1/data/clear?confirm=YES`
Supprimer TOUTES les données.

---

### WebSocket

#### WS `/ws/graph/{mission_id}`
Connexion WebSocket pour les événements temps réel.

**Events Reçus:**
```json
{
  "type": "node_added",
  "data": {
    "id": "subdomain:www.example.com",
    "type": "SUBDOMAIN",
    "properties": { /* ... */ }
  }
}

{
  "type": "edge_added",
  "data": {
    "from_node": "subdomain:www.example.com",
    "to_node": "http_service:https://www.example.com",
    "edge_type": "EXPOSES_HTTP"
  }
}

{
  "type": "node_updated",
  "data": {
    "id": "endpoint:/api/users",
    "changes": {
      "risk_score": 75
    }
  }
}
```

---

## Types de Noeuds

### Asset Nodes

| Type | Description | Propriétés Clés |
|------|-------------|-----------------|
| `DOMAIN` | Domaine racine | `name` |
| `SUBDOMAIN` | Sous-domaine | `name`, `subdomain`, `source` |
| `HTTP_SERVICE` | Service HTTP | `url`, `status_code`, `title`, `technology`, `ip` |
| `ENDPOINT` | Endpoint API/Page | `path`, `method`, `category`, `risk_score`, `source` |
| `PARAMETER` | Paramètre | `name`, `location`, `endpoint_id`, `param_type` |
| `IP_ADDRESS` | Adresse IP | `address`, `asn`, `org` |
| `DNS_RECORD` | Enregistrement DNS | `type`, `value`, `subdomain` |
| `ASN` | Autonomous System | `number`, `name`, `org` |
| `ORG` | Organisation | `name` |

### Security Nodes

| Type | Description | Propriétés Clés |
|------|-------------|-----------------|
| `HYPOTHESIS` | Hypothèse de vulnérabilité | `title`, `attack_type`, `target_id`, `confidence`, `status` |
| `VULNERABILITY` | Vulnérabilité confirmée | `title`, `cve_id`, `severity`, `target_id`, `evidence` |
| `ATTACK_PATH` | Chemin d'attaque | `target`, `score`, `actions`, `reasons` |

### Workflow Nodes

| Type | Description | Propriétés Clés |
|------|-------------|-----------------|
| `AGENT_RUN` | Exécution d'agent | `agent_id`, `agent_name`, `task`, `phase`, `status`, `duration` |
| `TOOL_CALL` | Appel d'outil | `tool_name`, `agent_id`, `arguments`, `status`, `result_count` |
| `LLM_REASONING` | Raisonnement LLM | `prompt`, `response`, `model`, `tokens` |

---

## Types de Relations

| Type | De → Vers | Description |
|------|-----------|-------------|
| `HAS_SUBDOMAIN` | DOMAIN → SUBDOMAIN | Domaine possède sous-domaine |
| `RESOLVES_TO` | SUBDOMAIN → IP_ADDRESS | DNS résolution |
| `SERVES` | IP_ADDRESS → HTTP_SERVICE | IP héberge service |
| `EXPOSES_HTTP` | SUBDOMAIN → HTTP_SERVICE | Subdomain expose HTTP |
| `EXPOSES_ENDPOINT` | HTTP_SERVICE → ENDPOINT | Service expose endpoint |
| `HAS_PARAM` | ENDPOINT → PARAMETER | Endpoint a paramètre |
| `HAS_HYPOTHESIS` | ENDPOINT → HYPOTHESIS | Endpoint a hypothèse |
| `HAS_VULNERABILITY` | ENDPOINT → VULNERABILITY | Endpoint a vulnérabilité |
| `TARGETS` | ATTACK_PATH → ENDPOINT | Chemin cible endpoint |
| `TRIGGERS` | AGENT_RUN → AGENT_RUN | Agent déclenche agent |
| `USES_TOOL` | AGENT_RUN → TOOL_CALL | Agent utilise outil |
| `PRODUCES` | TOOL_CALL → NODE | Outil produit asset |
| `REFINES` | AGENT_RUN → HYPOTHESIS | Agent affine hypothèse |
| `LINKS_TO` | NODE → NODE | Lien générique |

---

## Base de Données

### Schéma SQLite

```sql
-- Missions
CREATE TABLE missions (
    id TEXT PRIMARY KEY,
    target_domain TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    current_phase TEXT,
    progress TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Nodes
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    properties TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE INDEX idx_nodes_mission_id ON nodes(mission_id);
CREATE INDEX idx_nodes_type ON nodes(type);
CREATE INDEX idx_nodes_mission_type ON nodes(mission_id, type);

-- Edges
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    from_node TEXT NOT NULL,
    to_node TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    properties TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE INDEX idx_edges_mission_id ON edges(mission_id);
CREATE INDEX idx_edges_from_node ON edges(from_node);
CREATE INDEX idx_edges_to_node ON edges(to_node);

-- Logs
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    level TEXT NOT NULL,
    phase TEXT,
    message TEXT NOT NULL,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);

CREATE INDEX idx_logs_mission_id ON logs(mission_id);

-- Layouts
CREATE TABLE layouts (
    mission_id TEXT PRIMARY KEY,
    positions TEXT NOT NULL,  -- JSON
    zoom REAL,
    pan TEXT,  -- JSON
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mission_id) REFERENCES missions(id)
);
```

---

## Kafka Events

### Topics Produits

| Topic | Events |
|-------|--------|
| `graph.events` | NODE_ADDED, NODE_UPDATED, NODE_DELETED, EDGE_ADDED, EDGE_DELETED, ATTACK_PATH_ADDED |

### Format des Events

```json
{
  "event_type": "NODE_ADDED",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1702666849123,
  "payload": {
    "node": {
      "id": "subdomain:www.example.com",
      "type": "SUBDOMAIN",
      "properties": {
        "name": "www.example.com",
        "source": "subfinder"
      }
    }
  }
}
```

---

## Configuration

### Variables d'Environnement

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_PATH` | Chemin SQLite | `/app/data/graph.db` |
| `KAFKA_BOOTSTRAP_SERVERS` | Serveurs Kafka | `kafka:9092` |
| `KAFKA_TOPIC_GRAPH_EVENTS` | Topic pour events | `graph.events` |

---

## Performance

### Optimisations

1. **Indexes SQLite**: Index sur mission_id, type, et combinés
2. **Batch Operations**: Support pour création en batch
3. **Query Pagination**: Limite et offset pour grandes requêtes
4. **Event Batching**: Events Kafka regroupés

### Limites Recommandées

| Opération | Limite |
|-----------|--------|
| Nodes par batch | 1000 |
| Edges par batch | 2000 |
| Query limit max | 10000 |
| WebSocket connections | 100 |
