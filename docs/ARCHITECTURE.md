# Gotham Recon - Architecture & Wiring Guide

Complete guide for connecting frontend, backend, microservices, and real-time event streams.

---

## Table of Contents

1. [Infrastructure Overview](#1-infrastructure-overview)
2. [Service Ports & Health Checks](#2-service-ports--health-checks)
3. [Event Flow Architecture](#3-event-flow-architecture)
4. [Frontend Wiring](#4-frontend-wiring)
5. [Creating & Following a Mission](#5-creating--following-a-mission)
6. [Real-time Subscriptions](#6-real-time-subscriptions)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              GOTHAM RECON ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                     │
│  │   Browser    │────▶│  gotham-ui   │────▶│ bff-gateway  │                     │
│  │  :3000       │     │   Next.js    │     │   GraphQL    │                     │
│  └──────────────┘     └──────────────┘     └──────┬───────┘                     │
│                              │                     │                             │
│                              │ WS/SSE              │ HTTP/GraphQL                │
│                              ▼                     ▼                             │
│  ┌───────────────────────────────────────────────────────────────────┐          │
│  │                        BACKEND SERVICES                            │          │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │          │
│  │  │ recon-          │  │  graph-service  │  │   Phase         │    │          │
│  │  │ orchestrator    │  │  (CQRS R/W)     │  │   Services      │    │          │
│  │  │ :8000           │  │  :8001          │  │   :8002-8007    │    │          │
│  │  └────────┬────────┘  └────────┬────────┘  └─────────────────┘    │          │
│  │           │                    │                                   │          │
│  │           │   Kafka Events     │                                   │          │
│  │           ▼                    ▼                                   │          │
│  │  ┌─────────────────────────────────────────────────────────────┐  │          │
│  │  │                    MESSAGE BUS                               │  │          │
│  │  │  ┌─────────┐  ┌─────────────────────────────────────────┐   │  │          │
│  │  │  │  Kafka  │  │  Topics: graph.events, logs.recon       │   │  │          │
│  │  │  │  :9092  │  └─────────────────────────────────────────┘   │  │          │
│  │  │  └─────────┘                                                 │  │          │
│  │  └─────────────────────────────────────────────────────────────┘  │          │
│  │                                                                    │          │
│  │  ┌─────────────────────────────────────────────────────────────┐  │          │
│  │  │                    DATA STORES                               │  │          │
│  │  │  ┌─────────┐  ┌─────────┐  ┌───────────────┐                │  │          │
│  │  │  │Postgres │  │  Redis  │  │ Elasticsearch │                │  │          │
│  │  │  │  :5432  │  │  :6379  │  │    :9200      │                │  │          │
│  │  │  └─────────┘  └─────────┘  └───────────────┘                │  │          │
│  │  └─────────────────────────────────────────────────────────────┘  │          │
│  └───────────────────────────────────────────────────────────────────┘          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Service Ports & Health Checks

### Launch Stack

```bash
docker-compose up -d --build
```

### Health Check Commands

```bash
# Core Services
curl http://localhost:8000/health   # Orchestrator
curl http://localhost:8001/health   # Graph Service
curl http://localhost:8080/health   # BFF Gateway

# GraphQL Health
curl -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __typename }"}'

# Phase Services
curl http://localhost:8002/health   # OSINT Runner
curl http://localhost:8003/health   # Active Recon
curl http://localhost:8004/health   # Endpoint Intel
curl http://localhost:8005/health   # Verification
curl http://localhost:8006/health   # Reporter
curl http://localhost:8007/health   # Planner
```

### Service URLs

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **gotham-ui** | 3000 | http://localhost:3000 | Web Interface |
| **bff-gateway** | 8080 | http://localhost:8080/graphql | GraphQL API |
| **recon-orchestrator** | 8000 | http://localhost:8000 | Mission Control |
| **graph-service** | 8001 | http://localhost:8001 | Asset Graph |
| **grafana** | 3001 | http://localhost:3001 | Monitoring |
| **jaeger** | 16686 | http://localhost:16686 | Tracing |

---

## 3. Event Flow Architecture

### Kafka Topics

| Topic | Publisher | Content |
|-------|-----------|---------|
| `graph.events` | orchestrator, graph-service | Node/Edge mutations, workflow events |
| `logs.recon` | orchestrator | Structured mission logs |

### Event Types

```typescript
// Graph Events
type GraphEventType =
  | 'NODE_ADDED'
  | 'NODE_UPDATED'
  | 'NODE_DELETED'
  | 'EDGE_ADDED'
  | 'EDGE_DELETED'
  | 'ATTACK_PATH_ADDED';

// Workflow Events
type WorkflowEventType =
  | 'AGENT_STARTED'    // Agent begins execution
  | 'AGENT_FINISHED'   // Agent completes (success/error)
  | 'TOOL_CALLED'      // Tool invocation started
  | 'TOOL_FINISHED'    // Tool completes with result
  | 'ASSET_MUTATION';  // Asset created/updated by tool
```

### Event Payload Structure

```json
// Agent Started
{
  "event_type": "agent_started",
  "run_id": "mission-uuid",
  "source": "orchestrator",
  "timestamp": "2025-01-15T10:30:00Z",
  "payload": {
    "agent_id": "agent-osint",
    "agent_name": "OSINT Agent",
    "phase": "osint",
    "context": {}
  }
}

// Tool Called
{
  "event_type": "tool_called",
  "run_id": "mission-uuid",
  "source": "orchestrator",
  "timestamp": "2025-01-15T10:30:05Z",
  "payload": {
    "tool_id": "tool-osint-subfinder-1",
    "tool_name": "subfinder",
    "agent_id": "agent-osint",
    "input_hash": "abc123"
  }
}
```

---

## 4. Frontend Wiring

### Environment Configuration

Create `gotham-ui/.env.local`:

```env
# GraphQL Endpoint
NEXT_PUBLIC_GRAPHQL_URL=http://localhost:8080/graphql

# WebSocket URLs
NEXT_PUBLIC_WS_ORCHESTRATOR=ws://localhost:8000
NEXT_PUBLIC_WS_GRAPH=ws://localhost:8001

# SSE Endpoints
NEXT_PUBLIC_SSE_EVENTS=http://localhost:8080/api/v1/sse/events
NEXT_PUBLIC_SSE_LOGS=http://localhost:8000/api/v1/sse/logs
```

### Key Frontend Components

```
gotham-ui/src/
├── stores/
│   ├── missionStore.ts      # Mission state (status, logs)
│   ├── graphStore.ts        # Asset nodes/edges
│   ├── workflowStore.ts     # Workflow visualization state
│   └── uiStore.ts           # UI preferences
│
├── services/
│   ├── MissionService.ts    # Mission CRUD operations
│   ├── GraphService.ts      # Graph queries & subscriptions
│   ├── WorkflowService.ts   # Workflow event subscriptions
│   └── LayoutService.ts     # Layout persistence
│
├── components/
│   ├── workflow/
│   │   ├── WorkflowHierarchy.tsx  # Cytoscape graph (Agents/Tools/Assets)
│   │   ├── TracePanel.tsx         # Execution traces
│   │   ├── WorkflowControls.tsx   # LIVE/PAUSE, layer toggles
│   │   └── WorkflowPreview.tsx    # Dashboard widget
│   │
│   └── assets/
│       └── AssetGraph.tsx    # Asset relationship graph
│
└── app/
    └── mission/
        └── [id]/
            ├── page.tsx           # Mission dashboard
            └── workflow/
                └── page.tsx       # Full workflow view
```

### Service Connections

```typescript
// WorkflowService.ts - SSE Connection
class WorkflowServiceClass {
  private eventSource: EventSource | null = null;

  subscribe(missionId: string) {
    const url = `${process.env.NEXT_PUBLIC_SSE_EVENTS}/${missionId}`;
    this.eventSource = new EventSource(url);

    this.eventSource.addEventListener('agent_started', (e) => {
      const data = JSON.parse(e.data);
      this.handlers.agentStarted?.(data);
    });

    this.eventSource.addEventListener('tool_called', (e) => {
      const data = JSON.parse(e.data);
      this.handlers.toolCalled?.(data);
    });
  }
}

// GraphQL Subscription
const GRAPH_EVENTS_SUBSCRIPTION = gql`
  subscription GraphEvents($runId: String!) {
    graphEvents(runId: $runId) {
      eventType
      source
      payload
      timestamp
    }
  }
`;
```

---

## 5. Creating & Following a Mission

### Via REST API (curl/PowerShell)

**Bash:**
```bash
# Create mission
MISSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{
    "target_domain": "example.com",
    "mode": "aggressive",
    "seed_subdomains": ["www.example.com", "api.example.com"]
  }' | jq -r '.id')

echo "Mission ID: $MISSION_ID"
```

**PowerShell:**
```powershell
$body = @{
  target_domain = "example.com"
  mode = "aggressive"
  seed_subdomains = @("www.example.com", "api.example.com")
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/missions" `
  -Method Post -ContentType "application/json" -Body $body

$MISSION_ID = $response.id
Write-Host "Mission ID: $MISSION_ID"
```

### Via GraphQL

```graphql
mutation StartMission {
  startMission(input: {
    targetDomain: "example.com"
    mode: AGGRESSIVE
    seedSubdomains: ["www.example.com"]
  }) {
    id
    status
    targetDomain
    createdAt
  }
}
```

### Via UI

1. Open http://localhost:3000
2. Click "New Mission"
3. Enter target domain and configuration
4. Click "Start"
5. Navigate to `/mission/{id}/workflow` for live view

---

## 6. Real-time Subscriptions

### WebSocket - Mission Logs

```bash
# Using wscat
wscat -c ws://localhost:8000/ws/logs/$MISSION_ID
```

```javascript
// Browser
const ws = new WebSocket(`ws://localhost:8000/ws/logs/${missionId}`);
ws.onmessage = (event) => {
  const log = JSON.parse(event.data);
  console.log(`[${log.level}] ${log.message}`);
};
```

### WebSocket - Graph Events

```bash
# Using wscat
wscat -c ws://localhost:8001/ws/graph/$MISSION_ID
```

```javascript
// Browser - Receives snapshot then live updates
const ws = new WebSocket(`ws://localhost:8001/ws/graph/${missionId}`);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'snapshot') {
    // Initial state: { nodes: [...], edges: [...] }
  } else {
    // Live event: { event_type: 'NODE_ADDED', ... }
  }
};
```

### SSE - Event Stream

```bash
# Logs stream
curl -N http://localhost:8000/api/v1/sse/logs/$MISSION_ID

# Graph events stream
curl -N http://localhost:8080/api/v1/sse/events/$MISSION_ID
```

### GraphQL Subscription

```graphql
# In GraphQL Playground at http://localhost:8080/graphql

subscription WatchMission($runId: String!) {
  graphEvents(runId: $runId) {
    eventType
    source
    payload
    timestamp
  }
}

subscription WatchLogs($runId: String!) {
  logs(runId: $runId) {
    level
    message
    phase
    timestamp
  }
}
```

---

## 7. Troubleshooting

### Common Issues

#### Kafka Not Available

**Symptom:** Events not being published, warnings in orchestrator logs

**Fix:**
```bash
docker-compose restart kafka
sleep 10
docker-compose restart recon-orchestrator graph-service bff-gateway
```

#### WebSocket Connection Failed

**Symptom:** "WebSocket connection to 'ws://...' failed"

**Check:**
```bash
# Verify service is running
docker-compose ps | grep -E "(orchestrator|graph-service)"

# Check logs
docker-compose logs recon-orchestrator | tail -50
```

**Fix:** Ensure `.env.local` URLs match docker-compose ports

#### GraphQL Subscription Not Working

**Symptom:** No data received on subscription

**Check:**
```bash
# Test basic query first
curl -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ missions { id status } }"}'

# Check BFF logs
docker-compose logs bff-gateway | tail -50
```

#### Healthcheck Failures

**Symptom:** Services showing `(unhealthy)` in `docker-compose ps`

**Debug:**
```bash
# View detailed health status
docker inspect recon-gotham-bff-gateway-1 | jq '.[0].State.Health'

# Check service logs
docker-compose logs bff-gateway --tail 100

# Restart unhealthy service
docker-compose restart bff-gateway
```

### Verification Checklist

```bash
# 1. All services healthy
docker-compose ps

# 2. Kafka topics exist
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092

# 3. Mission can be created
curl -s -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain":"test.local","mode":"stealth"}' | jq

# 4. Events flow to graph-service
docker-compose logs graph-service | grep "event_type"

# 5. UI accessible
curl -s http://localhost:3000 | head -1
```

### Log Locations

| Service | Log Command |
|---------|-------------|
| All services | `docker-compose logs -f` |
| Orchestrator | `docker-compose logs -f recon-orchestrator` |
| Graph Service | `docker-compose logs -f graph-service` |
| BFF Gateway | `docker-compose logs -f bff-gateway` |
| UI Build | `docker-compose logs -f gotham-ui` |

---

## Quick Reference

### Start Everything
```bash
docker-compose up -d --build
```

### Create Mission & Watch
```bash
# Create
MISSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain":"example.com","mode":"aggressive"}' | jq -r '.id')

# Watch logs
curl -N http://localhost:8000/api/v1/sse/logs/$MISSION_ID

# Open UI
echo "Open: http://localhost:3000/mission/$MISSION_ID/workflow"
```

### Stop Everything
```bash
docker-compose down
```

### Full Reset
```bash
docker-compose down -v
docker-compose up -d --build
```
