# Gotham Recon - API Contracts & Schemas

## Table of Contents
1. [GraphQL Schema](#graphql-schema)
2. [Kafka Topics](#kafka-topics)
3. [WebSocket Endpoints](#websocket-endpoints)
4. [REST Endpoints](#rest-endpoints)

---

## GraphQL Schema

**Endpoint:** `http://localhost:8080/graphql`
**WebSocket:** `ws://localhost:8080/graphql`

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
  COMPLETED
  FAILED
  CANCELLED
}

enum NodeType {
  DOMAIN
  SUBDOMAIN
  HTTP_SERVICE
  ENDPOINT
  PARAMETER
  HYPOTHESIS
  VULNERABILITY
  ATTACK_PATH
  IP_ADDRESS
  DNS_RECORD
}

enum EventType {
  NODE_ADDED
  NODE_UPDATED
  NODE_DELETED
  EDGE_ADDED
  EDGE_DELETED
  ATTACK_PATH_ADDED
}

# Types
type Mission {
  id: String!
  targetDomain: String!
  mode: MissionMode!
  status: MissionStatus!
  currentPhase: String
  createdAt: String!
  progress: JSON!
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
  eventType: EventType!
  source: String!
  payload: JSON!
  timestamp: String!
}

type LogEntry {
  runId: String!
  level: String!
  phase: String!
  message: String!
  timestamp: String!
  metadata: JSON!
}

# Input Types
input MissionInput {
  targetDomain: String!
  mode: MissionMode = AGGRESSIVE
  seedSubdomains: [String!]
}

input NodeFilter {
  types: [NodeType!]
  riskScoreMin: Int
}
```

### Queries

```graphql
type Query {
  # Get single mission by ID
  mission(id: String!): Mission

  # List missions with pagination
  missions(limit: Int = 20, offset: Int = 0): MissionConnection!

  # Get nodes for a mission with optional filters
  nodes(missionId: String!, filter: NodeFilter, limit: Int = 100): [Node!]!

  # Get edges for a mission
  edges(missionId: String!): [Edge!]!

  # Get graph statistics
  graphStats(missionId: String!): GraphStats

  # Get top attack paths
  attackPaths(missionId: String!, top: Int = 5): [AttackPath!]!
}
```

### Mutations

```graphql
type Mutation {
  # Start a new reconnaissance mission
  startMission(input: MissionInput!): Mission!

  # Cancel a running mission
  cancelMission(id: String!): Boolean!
}
```

### Subscriptions

```graphql
type Subscription {
  # Subscribe to real-time graph events
  graphEvents(runId: String!): GraphEvent!

  # Subscribe to real-time logs
  logs(runId: String!): LogEntry!
}
```

### Example Queries

```graphql
# Start a mission
mutation StartMission {
  startMission(input: {
    targetDomain: "example.com"
    mode: AGGRESSIVE
    seedSubdomains: ["www", "api", "admin"]
  }) {
    id
    status
    createdAt
  }
}

# Get mission with nodes
query GetMissionData($id: String!) {
  mission(id: $id) {
    id
    status
    currentPhase
    progress
  }
  nodes(missionId: $id, limit: 100) {
    id
    type
    properties
  }
  graphStats(missionId: $id) {
    totalNodes
    totalEdges
    nodesByType
  }
}

# Subscribe to events
subscription WatchGraph($runId: String!) {
  graphEvents(runId: $runId) {
    eventType
    source
    payload
    timestamp
  }
}
```

---

## Kafka Topics

### Topic: `graph.events`

**Purpose:** Real-time graph mutations (nodes/edges added/updated/deleted)

**Key:** `run_id` (mission ID)

**Message Schema:**
```json
{
  "run_id": "uuid-mission-id",
  "event_type": "node_added|node_updated|node_deleted|edge_added|edge_deleted|attack_path_added",
  "source": "osint|active_recon|endpoint_intel|verification|planner|orchestrator",
  "payload": {
    "node": {
      "id": "subdomain:www.example.com",
      "type": "SUBDOMAIN",
      "mission_id": "uuid-mission-id",
      "properties": {
        "label": "www.example.com",
        "risk_score": 30
      }
    }
  },
  "timestamp": "2025-12-12T12:34:56.789Z"
}
```

**Event Types:**
- `node_added` - New node created
- `node_updated` - Existing node properties modified
- `node_deleted` - Node removed from graph
- `edge_added` - New relationship created
- `edge_deleted` - Relationship removed
- `attack_path_added` - New attack path computed

### Topic: `logs.recon`

**Purpose:** Structured logs from all pipeline phases

**Key:** `run_id` (mission ID)

**Message Schema:**
```json
{
  "run_id": "uuid-mission-id",
  "level": "DEBUG|INFO|WARNING|ERROR",
  "phase": "osint|safety_net|active_recon|endpoint_intel|verification|reporting",
  "message": "Found 52 subdomains for example.com",
  "timestamp": "2025-12-12T12:34:56.789Z",
  "metadata": {
    "agent": "SUBFINDER",
    "count": 52,
    "duration_ms": 1234
  }
}
```

**Log Levels:**
- `DEBUG` - Detailed diagnostic information
- `INFO` - General progress messages
- `WARNING` - Non-critical issues (rate limiting, missing data)
- `ERROR` - Critical failures

---

## WebSocket Endpoints

### Graph Service: `/ws/graph/{mission_id}`

**URL:** `ws://localhost:8001/ws/graph/{mission_id}`

**Connection Flow:**
1. Client connects with mission ID
2. Server sends initial snapshot: `{"type": "snapshot", "data": {...}}`
3. Server streams events as they occur
4. Client can send `"ping"` for keepalive, server responds `"pong"`

**Initial Snapshot:**
```json
{
  "type": "snapshot",
  "data": {
    "mission_id": "uuid",
    "nodes": [...],
    "edges": [...],
    "timestamp": "2025-12-12T12:34:56Z"
  }
}
```

**Event Message:**
```json
{
  "run_id": "uuid",
  "event_type": "node_added",
  "source": "osint",
  "payload": {"node": {...}},
  "timestamp": "2025-12-12T12:34:56Z"
}
```

### Orchestrator: `/ws/logs/{mission_id}`

**URL:** `ws://localhost:8000/ws/logs/{mission_id}`

**Message Format:**
```json
{
  "run_id": "uuid",
  "level": "INFO",
  "phase": "osint",
  "message": "Starting subdomain enumeration",
  "timestamp": "2025-12-12T12:34:56Z",
  "metadata": {}
}
```

---

## REST Endpoints

### Graph Service (Port 8001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/nodes` | Create node |
| GET | `/api/v1/nodes/{id}` | Get node by ID |
| PUT | `/api/v1/nodes/{id}` | Update node |
| DELETE | `/api/v1/nodes/{id}` | Delete node |
| POST | `/api/v1/nodes/query` | Query nodes with filters |
| POST | `/api/v1/nodes/batch` | Batch create nodes |
| POST | `/api/v1/edges` | Create edge |
| POST | `/api/v1/edges/batch` | Batch create edges |
| GET | `/api/v1/missions/{id}/stats` | Get mission statistics |
| GET | `/api/v1/missions/{id}/edges` | Get mission edges |
| GET | `/api/v1/missions/{id}/export` | Export full graph |

### Orchestrator (Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/missions` | Create mission |
| GET | `/api/v1/missions` | List missions |
| GET | `/api/v1/missions/{id}` | Get mission details |
| POST | `/api/v1/missions/{id}/cancel` | Cancel mission |
| POST | `/api/v1/missions/{id}/phases/{phase}` | Trigger specific phase |
| GET | `/api/v1/sse/logs/{id}` | SSE endpoint for logs |

### BFF Gateway (Port 8080)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/graphql` | GraphQL endpoint |
| WS | `/graphql` | GraphQL subscriptions |
| GET | `/api/v1/sse/events/{id}` | SSE endpoint for graph events |

---

## Node Type Reference

| Type | Description | Common Properties |
|------|-------------|-------------------|
| `DOMAIN` | Root domain | `label`, `registrar`, `whois` |
| `SUBDOMAIN` | Discovered subdomain | `label`, `source`, `risk_score` |
| `HTTP_SERVICE` | HTTP(S) service | `port`, `protocol`, `status_code` |
| `ENDPOINT` | API/Web endpoint | `url`, `method`, `parameters`, `risk_score` |
| `PARAMETER` | URL/body parameter | `name`, `type`, `injectable` |
| `HYPOTHESIS` | Security hypothesis | `category`, `confidence`, `description` |
| `VULNERABILITY` | Confirmed vulnerability | `cve`, `severity`, `cvss`, `verified` |
| `ATTACK_PATH` | Computed attack path | `score`, `actions`, `reasons` |
| `IP_ADDRESS` | IP address | `ip`, `asn`, `country` |
| `DNS_RECORD` | DNS record | `type`, `value`, `ttl` |

## Edge Type Reference

| Type | From | To | Description |
|------|------|----|-------------|
| `HAS_SUBDOMAIN` | DOMAIN | SUBDOMAIN | Domain has subdomain |
| `RESOLVES_TO` | SUBDOMAIN | IP_ADDRESS | DNS resolution |
| `EXPOSES_HTTP` | SUBDOMAIN | HTTP_SERVICE | Exposes HTTP service |
| `EXPOSES_ENDPOINT` | HTTP_SERVICE | ENDPOINT | Exposes API endpoint |
| `HAS_PARAM` | ENDPOINT | PARAMETER | Has URL parameter |
| `HAS_HYPOTHESIS` | ENDPOINT | HYPOTHESIS | Has security hypothesis |
| `HAS_VULNERABILITY` | ENDPOINT | VULNERABILITY | Has confirmed vulnerability |
| `TARGETS` | ATTACK_PATH | * | Attack path targets node |
| `SERVES` | IP_ADDRESS | HTTP_SERVICE | IP serves HTTP |

---

*Document version: 1.0.0*
*Generated: December 2025*
