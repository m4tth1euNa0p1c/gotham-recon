# Gotham Recon - API Documentation

## Overview

This document describes all available data from the Gotham Recon backend services.

---

## 1. GraphQL API (BFF Gateway - Port 8080)

### Endpoint
```
POST http://localhost:8080/graphql
```

### Queries

#### 1.1 Get Single Mission
```graphql
query GetMission($id: String!) {
  mission(id: $id) {
    id
    targetDomain
    mode           # STEALTH | BALANCED | AGGRESSIVE
    status         # PENDING | RUNNING | PAUSED | COMPLETED | FAILED | CANCELLED
    currentPhase
    createdAt
    progress       # JSON with phases_completed, current_metrics
  }
}
```

#### 1.2 Get All Missions (Paginated)
```graphql
query GetMissions($limit: Int, $offset: Int) {
  missions(limit: $limit, offset: $offset) {
    missions {
      id
      targetDomain
      mode
      status
      currentPhase
      createdAt
      progress
    }
    total
  }
}
```

#### 1.3 Get Nodes (Graph Assets)
```graphql
query GetNodes($missionId: String!, $filter: NodeFilter, $limit: Int) {
  nodes(missionId: $missionId, filter: $filter, limit: $limit) {
    id
    type           # See NodeType enum below
    properties     # JSON - varies by type
  }
}

# NodeFilter input:
# {
#   types: [NodeType]  # Filter by node types
# }
```

#### 1.4 Get Edges (Relationships)
```graphql
query GetEdges($missionId: String!) {
  edges(missionId: $missionId) {
    fromNode
    toNode
    relation       # CONTAINS, SERVES, HAS_ENDPOINT, etc.
  }
}
```

#### 1.5 Get Graph Statistics
```graphql
query GetStats($missionId: String!) {
  graphStats(missionId: $missionId) {
    missionId
    totalNodes
    totalEdges
    nodesByType    # JSON: { "SUBDOMAIN": 48, "HTTP_SERVICE": 10, ... }
  }
}
```

#### 1.6 Get Attack Paths
```graphql
query GetAttackPaths($missionId: String!, $top: Int) {
  attackPaths(missionId: $missionId, top: $top) {
    target
    score
    actions
    reasons
  }
}
```

#### 1.7 Get Workflow Nodes (Agent Runs, Tool Calls)
```graphql
query GetWorkflowNodes($missionId: String!, $types: [NodeType]) {
  workflowNodes(missionId: $missionId, types: $types) {
    id
    type           # AGENT_RUN | TOOL_CALL | LLM_REASONING
    properties
  }
}
```

#### 1.8 Get Workflow Layout
```graphql
query GetWorkflowLayout($missionId: String!) {
  workflowLayout(missionId: $missionId)  # Returns JSON
}
```

### Mutations

#### Start Mission
```graphql
mutation StartMission($input: MissionInput!) {
  startMission(input: $input) {
    id
    targetDomain
    status
  }
}

# MissionInput:
# {
#   targetDomain: String!
#   mode: MissionMode
#   seedSubdomains: [String]
# }
```

#### Cancel Mission
```graphql
mutation CancelMission($id: String!) {
  cancelMission(id: $id)
}
```

#### Delete Mission
```graphql
mutation DeleteMission($missionId: String!) {
  deleteMission(missionId: $missionId)
}
```

### Subscriptions (WebSocket)

#### Graph Events
```graphql
subscription GraphEvents($missionId: String!) {
  graphEvents(missionId: $missionId) {
    runId
    eventType      # NODE_ADDED | NODE_UPDATED | EDGE_ADDED | etc.
    source
    payload        # JSON
    timestamp
  }
}
```

#### Log Events
```graphql
subscription Logs($missionId: String!) {
  logs(missionId: $missionId) {
    runId
    level          # DEBUG | INFO | WARNING | ERROR
    phase
    message
    timestamp
    metadata       # JSON
  }
}
```

---

## 2. Node Types & Properties

### 2.1 SUBDOMAIN
```json
{
  "id": "subdomain:www.example.com",
  "type": "SUBDOMAIN",
  "properties": {
    "name": "www.example.com",
    "subdomain": "www.example.com",
    "source": "subfinder",           // subfinder | wayback | dns | manual
    "mission_id": "uuid"
  }
}
```

### 2.2 HTTP_SERVICE
```json
{
  "id": "http_service:https://www.example.com",
  "type": "HTTP_SERVICE",
  "properties": {
    "url": "https://www.example.com",
    "status_code": 200,
    "title": "Page Title",
    "technology": "['WordPress', 'PHP', 'MySQL']",
    "ip": "192.168.1.1",
    "mission_id": "uuid"
  }
}
```

### 2.3 ENDPOINT
```json
{
  "id": "endpoint:/api/v1/users",
  "type": "ENDPOINT",
  "properties": {
    "path": "/api/v1/users",
    "method": "GET",
    "category": "API",              // API | ADMIN | AUTH | LEGACY | WAYBACK
    "source": "js_intel",           // js_intel | wayback | html_crawl
    "risk_score": 75,
    "mission_id": "uuid"
  }
}
```

### 2.4 PARAMETER
```json
{
  "id": "param:endpoint:/api/users:id",
  "type": "PARAMETER",
  "properties": {
    "name": "id",
    "location": "path",             // path | query | body | header
    "endpoint_id": "endpoint:/api/users",
    "param_type": "integer",
    "mission_id": "uuid"
  }
}
```

### 2.5 HYPOTHESIS (Security Finding)
```json
{
  "id": "hypothesis:IDOR:endpoint:/api/users",
  "type": "HYPOTHESIS",
  "properties": {
    "title": "Insecure Direct Object References",
    "attack_type": "IDOR",          // See Attack Types below
    "target_id": "endpoint:/api/users",
    "confidence": 0.8,              // 0.0 - 1.0
    "status": "unverified",         // unverified | confirmed | false_positive
    "mission_id": "uuid"
  }
}
```

### 2.6 VULNERABILITY (Confirmed)
```json
{
  "id": "vuln:CVE-2024-1234:endpoint:/login",
  "type": "VULNERABILITY",
  "properties": {
    "title": "SQL Injection in Login",
    "cve_id": "CVE-2024-1234",
    "severity": "HIGH",             // CRITICAL | HIGH | MEDIUM | LOW | INFO
    "target_id": "endpoint:/login",
    "evidence": "Payload: ' OR 1=1--",
    "mission_id": "uuid"
  }
}
```

### 2.7 TECHNOLOGY
```json
{
  "id": "tech:WordPress:6.8.3",
  "type": "TECHNOLOGY",
  "properties": {
    "name": "WordPress",
    "version": "6.8.3",
    "category": "CMS",
    "mission_id": "uuid"
  }
}
```

### 2.8 IP
```json
{
  "id": "ip:192.168.1.1",
  "type": "IP",
  "properties": {
    "address": "192.168.1.1",
    "asn": "AS12345",
    "org": "Example Inc",
    "mission_id": "uuid"
  }
}
```

### 2.9 DOMAIN
```json
{
  "id": "domain:example.com",
  "type": "DOMAIN",
  "properties": {
    "name": "example.com",
    "registrar": "GoDaddy",
    "mission_id": "uuid"
  }
}
```

### 2.10 AGENT_RUN (Workflow)
```json
{
  "id": "agent-pathfinder-1702666849000",
  "type": "AGENT_RUN",
  "properties": {
    "agent_id": "pathfinder",
    "agent_name": "pathfinder",
    "task": "Subdomain enumeration",
    "phase": "OSINT",
    "status": "completed",          // pending | running | completed | error
    "start_time": "2025-12-15T18:00:00Z",
    "end_time": "2025-12-15T18:05:00Z",
    "duration": 300000,             // milliseconds
    "mission_id": "uuid"
  }
}
```

### 2.11 TOOL_CALL (Workflow)
```json
{
  "id": "tool-subfinder-1702666849000",
  "type": "TOOL_CALL",
  "properties": {
    "tool_name": "subfinder",
    "agent_id": "pathfinder",
    "arguments": {"domain": "example.com"},
    "status": "success",            // pending | running | success | error
    "result_count": 48,
    "start_time": "2025-12-15T18:00:00Z",
    "end_time": "2025-12-15T18:02:00Z",
    "duration": 120000,
    "mission_id": "uuid"
  }
}
```

---

## 3. Attack Types (Hypothesis)

| Type | Description |
|------|-------------|
| `SQLI` | SQL Injection |
| `XSS` | Cross-Site Scripting |
| `IDOR` | Insecure Direct Object References |
| `SSRF` | Server-Side Request Forgery |
| `LFI` | Local File Inclusion |
| `RFI` | Remote File Inclusion |
| `RCE` | Remote Code Execution |
| `AUTH_BYPASS` | Authentication Bypass |
| `OPEN_REDIRECT` | Open Redirect |
| `INFO_DISCLOSURE` | Information Disclosure |
| `CSRF` | Cross-Site Request Forgery |
| `XXE` | XML External Entity |
| `SSTI` | Server-Side Template Injection |

---

## 4. REST APIs

### 4.1 Orchestrator (Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/llm/status` | LLM availability status |
| POST | `/api/v1/missions` | Create new mission |
| GET | `/api/v1/missions` | List all missions |
| GET | `/api/v1/missions/{id}` | Get mission details |
| DELETE | `/api/v1/missions/{id}` | Delete mission |
| POST | `/api/v1/missions/{id}/cancel` | Cancel running mission |
| DELETE | `/api/v1/data/clear` | Clear all data |
| GET | `/api/v1/sse/logs/{id}` | SSE stream for logs |

#### Mission Response (Full)
```json
{
  "id": "uuid",
  "target_domain": "example.com",
  "mode": "aggressive",
  "status": "completed",
  "current_phase": null,
  "created_at": "2025-12-15T18:00:00Z",
  "updated_at": "2025-12-15T18:30:00Z",
  "progress": {
    "phases_completed": ["passive", "active"],
    "current_metrics": {
      "crewai": {
        "mission_id": "uuid",
        "target_domain": "example.com",
        "status": "completed",
        "duration": 207.03,
        "summary": {
          "subdomains": 48,
          "http_services": 19,
          "endpoints": 0,
          "dns_records": 20
        },
        "phases": {
          "passive": {
            "phase": "passive_recon",
            "duration": 172.34,
            "result": {
              "subdomains": ["www.example.com", ...],
              "wayback": [],
              "dns": [
                {
                  "subdomain": "www.example.com",
                  "ips": ["192.168.1.1"],
                  "records": {
                    "A": ["192.168.1.1"],
                    "CNAME": ["cdn.example.com."],
                    "TXT": ["v=spf1..."],
                    "NS": ["ns1.example.com."]
                  }
                }
              ]
            }
          },
          "active": {
            "phase": "active_recon",
            "duration": 4.71,
            "result": {
              "http_services": [
                {
                  "host": "https://www.example.com",
                  "url": "https://www.example.com",
                  "status_code": 200,
                  "title": "Example Site",
                  "technologies": ["WordPress", "PHP", "MySQL"],
                  "ip": "192.168.1.1"
                }
              ],
              "js_intel": [
                {
                  "url": "https://www.example.com",
                  "js": {
                    "js_files": ["/wp-content/themes/theme/app.js"],
                    "endpoints": ["/api/v1/users"],
                    "secrets": []
                  }
                }
              ],
              "html": [
                {"path": "/login", "forms": 1}
              ]
            }
          },
          "intel": { ... },
          "planning": { ... }
        },
        "results": { ... }
      }
    }
  }
}
```

### 4.2 Graph Service (Port 8001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/nodes` | Create node |
| GET | `/api/v1/nodes` | List nodes |
| GET | `/api/v1/nodes/{id}` | Get node |
| PUT | `/api/v1/nodes/{id}` | Update node |
| DELETE | `/api/v1/nodes/{id}` | Delete node |
| POST | `/api/v1/nodes/query` | Query nodes with filter |
| POST | `/api/v1/nodes/batch` | Batch create nodes |
| POST | `/api/v1/edges` | Create edge |
| GET | `/api/v1/missions/{id}/edges` | Get mission edges |
| POST | `/api/v1/edges/batch` | Batch create edges |
| GET | `/api/v1/missions/{id}/stats` | Get mission statistics |
| GET | `/api/v1/missions/{id}/export` | Export mission data |
| POST | `/api/v1/layouts/{id}` | Save workflow layout |
| GET | `/api/v1/layouts/{id}` | Get workflow layout |
| DELETE | `/api/v1/missions/{id}` | Delete mission data |
| DELETE | `/api/v1/missions/{id}/history` | Delete mission history |
| DELETE | `/api/v1/data/clear` | Clear all data |

---

## 5. Real-Time Events (SSE/Kafka)

### Event Types

#### Log Events (Topic: logs.recon)
```json
{
  "event_type": "LOG",
  "mission_id": "uuid",
  "run_id": "uuid",
  "timestamp": 1702666849.123,
  "iso_timestamp": "2025-12-15T18:00:49Z",
  "payload": {
    "level": "INFO",
    "phase": "passive_recon",
    "message": "Subfinder found 48 subdomains",
    "metadata": {}
  }
}
```

#### Agent Started
```json
{
  "event_type": "agent_started",
  "mission_id": "uuid",
  "payload": {
    "run_id": "agent-pathfinder-1702666849000",
    "agent_id": "pathfinder",
    "agent_name": "pathfinder",
    "task": "Subdomain enumeration",
    "phase": "OSINT",
    "model": "crewai",
    "start_time": "2025-12-15T18:00:00.000Z"
  }
}
```

#### Agent Finished
```json
{
  "event_type": "agent_finished",
  "mission_id": "uuid",
  "payload": {
    "run_id": "agent-pathfinder-1702666849000",
    "agent_id": "pathfinder",
    "result": "Completed",
    "status": "success",
    "duration": 120000,
    "end_time": "2025-12-15T18:02:00.000Z"
  }
}
```

#### Tool Called
```json
{
  "event_type": "tool_called",
  "mission_id": "uuid",
  "payload": {
    "call_id": "tool-subfinder-1702666849000",
    "tool_name": "subfinder",
    "agent_id": "pathfinder",
    "arguments": {"input": "domain=example.com"},
    "start_time": "2025-12-15T18:00:00.000Z"
  }
}
```

#### Tool Finished
```json
{
  "event_type": "tool_finished",
  "mission_id": "uuid",
  "payload": {
    "call_id": "tool-subfinder-1702666849000",
    "tool_name": "subfinder",
    "result": {"count": 48},
    "status": "success",
    "duration": 60000,
    "end_time": "2025-12-15T18:01:00.000Z"
  }
}
```

#### Graph Events (Topic: graph.events)
```json
{
  "event_type": "NODE_ADDED",
  "mission_id": "uuid",
  "payload": {
    "node": {
      "id": "subdomain:www.example.com",
      "type": "SUBDOMAIN",
      "properties": { ... }
    }
  }
}
```

---

## 6. Mission Phases

| Phase | Description | Duration |
|-------|-------------|----------|
| `passive_recon` | Subdomain enum, Wayback, DNS | ~170s |
| `active_recon` | HTTPX probe, JS mining, HTML crawl | ~5s |
| `endpoint_intel` | Risk scoring, hypothesis generation | ~20s |
| `planning` | Attack path identification | ~10s |

---

## 7. UI Data Requirements

### Mission List Page
- Mission ID, target domain, status, mode
- Created/updated timestamps
- Phase progress (phases_completed)
- Summary stats (subdomains, services, endpoints)

### Mission Detail Page

#### Stats Section
- Total nodes/edges
- Nodes by type breakdown
- Duration per phase
- Technologies detected (aggregated)

#### Subdomains Tab
- List of all subdomains
- Source (subfinder, wayback, dns)
- DNS records (A, CNAME, TXT, NS)
- Associated IPs

#### HTTP Services Tab
- URL, status code, title
- Technologies array
- IP address
- Response headers (if available)

#### Endpoints Tab
- Path, method
- Category (API, ADMIN, AUTH, etc.)
- Source (js_intel, wayback, html_crawl)
- Risk score
- Associated parameters

#### Hypotheses Tab
- Title, attack type
- Target endpoint
- Confidence score (0-1)
- Status (unverified, confirmed, false_positive)

#### Vulnerabilities Tab
- Title, CVE ID
- Severity (CRITICAL to INFO)
- Target, evidence
- Remediation suggestions

#### Technologies Tab
- Name, version
- Category
- Associated services

#### Agent Pipeline Tab
- Agent runs timeline
- Tool calls per agent
- Duration visualization
- Status indicators

#### Graph View
- Interactive node/edge visualization
- Filter by node type
- Hierarchical layout
- Node detail on click
