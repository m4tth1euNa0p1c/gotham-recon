# BFF Gateway Service

> **API Gateway GraphQL avec souscriptions temps réel**
>
> Port: 8080 | Base URL: `http://localhost:8080`
>
> Version: 3.2.1 | Dernière mise à jour: Décembre 2025

---

## Changelog v3.2.1

### Performance & Reliability Fixes

| Fix | Description |
|-----|-------------|
| **HTTP Timeout** | Augmentation du timeout de 10s à 60s pour les requêtes vers l'orchestrator |
| **Error Logging** | Amélioration du logging avec type d'exception et traceback complet |
| **Kafka Reconnection** | Meilleure gestion de la reconnexion Kafka après redémarrage |

### Code Changes

```python
# Avant (v3.2.0)
async with httpx.AsyncClient(timeout=10.0) as client:

# Après (v3.2.1)
async with httpx.AsyncClient(timeout=60.0) as client:
```

**Raison:** L'orchestrator peut être lent à répondre pendant l'exécution d'une mission CrewAI (single worker uvicorn). Le timeout de 60s permet d'éviter les erreurs `ReadTimeout` fréquentes.

---

## Changelog v3.2.0

### GraphQL Schema Fixes

| Fix | Description |
|-----|-------------|
| **MissionConnection.items** | Renommage de `missions` vers `items` pour compatibilité UI |
| **SNAPSHOT event** | Support du type d'événement SNAPSHOT dans le streaming |
| **DNS_RECORD NodeType** | Ajout du type DNS_RECORD dans l'enum NodeType |

### SSE Improvements

| Feature | Description |
|---------|-------------|
| **Last-Event-ID** | Support complet du header pour reconnexion |
| **Ring Buffer** | Buffer circulaire de 1000 événements par mission |
| **SNAPSHOT fallback** | Envoi automatique du snapshot si événements trop anciens |

---

## Vue d'Ensemble

Le BFF (Backend-For-Frontend) Gateway est le point d'entrée unifié pour le frontend. Il expose une API GraphQL riche avec support des queries, mutations et subscriptions temps réel.

### Responsabilités

- API GraphQL (queries, mutations, subscriptions)
- Agrégation des données de multiples services
- Streaming SSE/WebSocket pour le temps réel
- Proxy vers les services backend
- Gestion des souscriptions Kafka

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       BFF GATEWAY                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Strawberry GraphQL                        │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐    │ │
│  │  │   Queries    │ │  Mutations   │ │  Subscriptions   │    │ │
│  │  └──────────────┘ └──────────────┘ └──────────────────┘    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │                    Service Proxies                         │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐   │  │
│  │  │ Orchestrator │ │    Graph     │ │  Phase Services  │   │  │
│  │  │    Proxy     │ │    Proxy     │ │     Proxies      │   │  │
│  │  └──────────────┘ └──────────────┘ └──────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │                   Event Streaming                          │  │
│  │  ┌────────────────┐ ┌────────────────────────────────┐    │  │
│  │  │Kafka Consumer  │ │  SSE/WebSocket Publishers      │    │  │
│  │  │(graph.events,  │ │  (Real-time to clients)        │    │  │
│  │  │ logs.recon)    │ │                                │    │  │
│  │  └────────────────┘ └────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## GraphQL Schema

### Types

```graphql
# Enums
enum MissionMode {
  STEALTH
  AGGRESSIVE
  BALANCED
}

enum MissionStatus {
  PENDING
  RUNNING
  PAUSED
  COMPLETED
  FAILED
  CANCELLED
}

enum NodeType {
  # Assets
  DOMAIN
  SUBDOMAIN
  HTTP_SERVICE
  ENDPOINT
  PARAMETER
  IP_ADDRESS
  DNS_RECORD
  ASN
  ORG
  # Security
  HYPOTHESIS
  VULNERABILITY
  ATTACK_PATH
  # Workflow
  AGENT_RUN
  TOOL_CALL
  LLM_REASONING
}

# Types principaux
type Mission {
  id: String!
  targetDomain: String!
  mode: MissionMode!
  status: MissionStatus!
  currentPhase: String
  createdAt: DateTime!
  progress: JSON
}

type Node {
  id: String!
  type: NodeType!
  properties: JSON!
}

type Edge {
  fromNode: String!
  toNode: String!
  relation: String!
}

type GraphStats {
  missionId: String!
  totalNodes: Int!
  totalEdges: Int!
  nodesByType: JSON!
}

type AttackPath {
  target: String!
  score: Int!
  actions: [String!]!
  reasons: [String!]!
}

type GraphEvent {
  runId: String!
  eventType: String!
  source: String
  payload: JSON!
  timestamp: DateTime!
}

type LogEvent {
  runId: String!
  level: String!
  phase: String
  message: String!
  timestamp: DateTime!
  metadata: JSON
}

type MissionList {
  items: [Mission!]!
  total: Int!
}

# Inputs
input MissionInput {
  targetDomain: String!
  mode: MissionMode
  seedSubdomains: [String!]
}

input NodeFilter {
  types: [NodeType!]
}
```

### Queries

```graphql
type Query {
  # Missions
  mission(id: String!): Mission
  missions(limit: Int, offset: Int): MissionList!

  # Graph Data
  nodes(missionId: String!, filter: NodeFilter, limit: Int): [Node!]!
  edges(missionId: String!): [Edge!]!
  graphStats(missionId: String!): GraphStats

  # Security
  attackPaths(missionId: String!, top: Int): [AttackPath!]!

  # Workflow
  workflowNodes(missionId: String!, types: [NodeType!]): [Node!]!
  workflowLayout(missionId: String!): JSON
}
```

### Mutations

```graphql
type Mutation {
  # Missions
  startMission(input: MissionInput!): Mission!
  cancelMission(id: String!): Boolean!
  deleteMission(missionId: String!): Boolean!

  # Workflow
  saveWorkflowLayout(missionId: String!, positions: JSON!, zoom: Float, pan: JSON): Boolean!
}
```

### Subscriptions

```graphql
type Subscription {
  # Real-time graph events
  graphEvents(missionId: String!): GraphEvent!

  # Real-time logs
  logs(missionId: String!): LogEvent!
}
```

---

## REST Endpoints

### GraphQL

#### POST `/graphql`
Endpoint GraphQL principal.

**Request:**
```json
{
  "query": "query GetMission($id: String!) { mission(id: $id) { id targetDomain status } }",
  "variables": { "id": "550e8400-e29b-41d4-a716-446655440000" }
}
```

**Response:**
```json
{
  "data": {
    "mission": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "targetDomain": "example.com",
      "status": "COMPLETED"
    }
  }
}
```

### SSE Endpoints

#### GET `/api/v1/sse/events/{run_id}`
Server-Sent Events pour les événements du graphe avec support de reconnexion (P0.5).

**Headers Supportés:**
| Header | Description |
|--------|-------------|
| `Last-Event-ID` | ID du dernier événement reçu pour le replay |

**Event Format:**
```
id: evt_123_a1b2c3d4
event: graph_event
data: {"event_type": "NODE_ADDED", "payload": {"node": {"id": "...", "type": "SUBDOMAIN"}}, "sse_event_id": "evt_123_a1b2c3d4"}

id: evt_124_b2c3d4e5
event: log
data: {"level": "INFO", "phase": "OSINT", "message": "Subfinder completed", "sse_event_id": "evt_124_b2c3d4e5"}
```

**Comportement de Reconnexion:**
1. Si `Last-Event-ID` est fourni et trouvé dans le ring buffer → replay des événements manqués
2. Si non trouvé → envoi d'un snapshot complet du graphe
3. Nouveau stream d'événements en temps réel

#### GET `/api/v1/sse/snapshot/{run_id}`
Obtenir un snapshot du graphe et l'état du ring buffer (P0.5).

**Response 200:**
```json
{
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "snapshot": {
    "nodes": [
      {
        "id": "subdomain:www.example.com",
        "type": "SUBDOMAIN",
        "properties": { /* ... */ }
      }
    ],
    "edges": [
      {
        "from_node": "domain:example.com",
        "to_node": "subdomain:www.example.com",
        "relation": "HAS_SUBDOMAIN"
      }
    ],
    "stats": {
      "total_nodes": 48,
      "total_edges": 96,
      "nodes_by_type": { /* ... */ }
    }
  },
  "ring_buffer": {
    "size": 1000,
    "current_count": 256,
    "oldest_event_id": "evt_1_a1b2c3d4",
    "newest_event_id": "evt_256_x9y8z7w6"
  },
  "timestamp": "2025-12-15T18:30:00Z"
}
```

### Ring Buffer (v3.1)

Le BFF Gateway maintient un ring buffer circulaire de 1000 événements par mission:

```
┌─────────────────────────────────────────────────────────────┐
│                    RING BUFFER (1000 events)                 │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐    │
│  │evt_1│evt_2│evt_3│ ... │evt_N│  ←  │     │     │     │    │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘    │
│                             ▲                                │
│                        write pointer                         │
└─────────────────────────────────────────────────────────────┘

Client reconnects with Last-Event-ID: evt_50
      │
      ▼
┌─────────────┐
│ Lookup evt_50│
└──────┬──────┘
       │
       ▼ Found?
    ┌──┴──┐
    │ Yes │───▶ Replay evt_51 → evt_N → live stream
    └──┬──┘
       │ No
       ▼
┌─────────────┐
│Send Snapshot│───▶ Full graph state → live stream
└─────────────┘
```

**Avantages:**
- Reconnexion transparente pour le client
- Pas de perte d'événements (dans la fenêtre du buffer)
- Snapshot automatique si événements trop anciens

### Debug

#### GET `/api/v1/debug/subscriptions`
Debug des souscriptions actives.

**Response:**
```json
{
  "event_queues": {
    "550e8400-...": 2
  },
  "log_queues": {
    "550e8400-...": 1
  },
  "kafka_connected": true
}
```

---

## Exemples de Requêtes GraphQL

### Obtenir une mission avec stats

```graphql
query GetMissionWithStats($id: String!) {
  mission(id: $id) {
    id
    targetDomain
    mode
    status
    currentPhase
    createdAt
    progress
  }
  graphStats(missionId: $id) {
    totalNodes
    totalEdges
    nodesByType
  }
}
```

### Lister les missions

```graphql
query GetMissions($limit: Int, $offset: Int) {
  missions(limit: $limit, offset: $offset) {
    items {
      id
      targetDomain
      status
      createdAt
    }
    total
  }
}
```

### Obtenir les noeuds par type

```graphql
query GetNodesByType($missionId: String!, $types: [NodeType!]) {
  nodes(missionId: $missionId, filter: { types: $types }, limit: 100) {
    id
    type
    properties
  }
}

# Variables
{
  "missionId": "550e8400-...",
  "types": ["SUBDOMAIN", "HTTP_SERVICE"]
}
```

### Obtenir le workflow

```graphql
query GetWorkflow($missionId: String!) {
  workflowNodes(missionId: $missionId, types: [AGENT_RUN, TOOL_CALL]) {
    id
    type
    properties
  }
  workflowLayout(missionId: $missionId)
}
```

### Démarrer une mission

```graphql
mutation StartMission($input: MissionInput!) {
  startMission(input: $input) {
    id
    targetDomain
    status
  }
}

# Variables
{
  "input": {
    "targetDomain": "example.com",
    "mode": "AGGRESSIVE",
    "seedSubdomains": ["www.example.com", "api.example.com"]
  }
}
```

### Souscrire aux événements

```graphql
subscription GraphEvents($missionId: String!) {
  graphEvents(missionId: $missionId) {
    runId
    eventType
    source
    payload
    timestamp
  }
}

subscription Logs($missionId: String!) {
  logs(missionId: $missionId) {
    runId
    level
    phase
    message
    timestamp
    metadata
  }
}
```

---

## Configuration

### Variables d'Environnement

| Variable | Description | Default |
|----------|-------------|---------|
| `ORCHESTRATOR_URL` | URL de l'orchestrateur | `http://orchestrator:8000` |
| `GRAPH_SERVICE_URL` | URL du Graph Service | `http://graph-service:8001` |
| `KAFKA_BOOTSTRAP_SERVERS` | Serveurs Kafka | `kafka:9092` |
| `CORS_ORIGINS` | Origins CORS autorisés | `*` |

---

## WebSocket (GraphQL Subscriptions)

### Connexion

```javascript
// Client-side avec graphql-ws
import { createClient } from 'graphql-ws';

const client = createClient({
  url: 'ws://localhost:8080/graphql',
});

// Subscribe to graph events
client.subscribe(
  {
    query: `subscription ($missionId: String!) {
      graphEvents(missionId: $missionId) {
        eventType
        payload
        timestamp
      }
    }`,
    variables: { missionId: '550e8400-...' },
  },
  {
    next: (data) => console.log('Event:', data),
    error: (err) => console.error('Error:', err),
    complete: () => console.log('Complete'),
  }
);
```

### Protocole

Le BFF Gateway utilise le protocole `graphql-transport-ws` pour les subscriptions WebSocket.

---

## Kafka Integration

### Topics Consommés

| Topic | Usage |
|-------|-------|
| `graph.events` | Événements du graphe (NODE_ADDED, etc.) |
| `logs.recon` | Logs et traces d'exécution |

### Flow des Événements

```
Kafka Topic (graph.events)
          │
          ▼
   ┌─────────────┐
   │   Consumer  │
   │   Group     │
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │Event Router │
   │(by mission) │
   └──────┬──────┘
          │
     ┌────┴────┐
     ▼         ▼
┌─────────┐ ┌─────────┐
│  SSE    │ │WebSocket│
│ Clients │ │ Clients │
└─────────┘ └─────────┘
```

---

## GraphQL Playground

Le BFF Gateway expose un GraphQL Playground interactif à:

```
http://localhost:8080/graphql
```

### Fonctionnalités
- Auto-complétion du schéma
- Documentation intégrée
- Exécution de queries/mutations
- Test des subscriptions

---

## Performance

### Optimisations

1. **DataLoader**: Batching des requêtes au Graph Service
2. **Caching**: Cache LRU pour les requêtes fréquentes
3. **Query Complexity**: Limite de complexité des queries
4. **Connection Pooling**: Pool de connexions HTTP

### Limites

| Resource | Limite |
|----------|--------|
| Query depth | 10 |
| Query complexity | 1000 |
| Concurrent subscriptions | 100 |
| SSE connections | 500 |
