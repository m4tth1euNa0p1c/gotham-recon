# GraphQL Schema Reference

> **Schéma complet de l'API GraphQL BFF Gateway**

---

## Endpoint

```
POST http://localhost:8080/graphql
WS   ws://localhost:8080/graphql (Subscriptions)
```

---

## Enums

### MissionMode

```graphql
enum MissionMode {
  STEALTH      # Reconnaissance passive uniquement
  AGGRESSIVE   # Toutes les phases activées
  BALANCED     # Compromis couverture/discrétion
}
```

### MissionStatus

```graphql
enum MissionStatus {
  PENDING      # En attente de démarrage
  RUNNING      # En cours d'exécution
  PAUSED       # Mise en pause (future)
  COMPLETED    # Terminée avec succès
  FAILED       # Échec
  CANCELLED    # Annulée par l'utilisateur
}
```

### NodeType

```graphql
enum NodeType {
  # Asset Nodes
  DOMAIN           # Domaine racine
  SUBDOMAIN        # Sous-domaine découvert
  HTTP_SERVICE     # Service HTTP actif
  ENDPOINT         # Endpoint API/page
  PARAMETER        # Paramètre d'URL
  IP_ADDRESS       # Adresse IP
  DNS_RECORD       # Enregistrement DNS
  ASN              # Autonomous System Number
  ORG              # Organisation

  # Security Nodes
  HYPOTHESIS       # Hypothèse de vulnérabilité
  VULNERABILITY    # Vulnérabilité confirmée
  ATTACK_PATH      # Chemin d'attaque suggéré

  # Workflow Nodes
  AGENT_RUN        # Exécution d'un agent
  TOOL_CALL        # Appel d'un outil
  LLM_REASONING    # Raisonnement LLM
}
```

---

## Types

### Mission

```graphql
type Mission {
  id: String!
  targetDomain: String!
  mode: MissionMode!
  status: MissionStatus!
  currentPhase: String
  createdAt: DateTime!
  updatedAt: DateTime
  progress: JSON
}
```

**Exemple de `progress`:**
```json
{
  "phases_completed": ["OSINT", "ACTIVE_RECON"],
  "current_metrics": {
    "crewai": {
      "mission_id": "uuid",
      "target_domain": "example.com",
      "status": "completed",
      "duration": 207.03,
      "summary": {
        "subdomains": 48,
        "http_services": 19,
        "endpoints": 156,
        "dns_records": 20
      }
    }
  }
}
```

### MissionList

```graphql
type MissionList {
  items: [Mission!]!
  total: Int!
}
```

### Node

```graphql
type Node {
  id: String!
  type: NodeType!
  properties: JSON!
}
```

**Exemples de `properties` par type:**

```json
// SUBDOMAIN
{
  "name": "www.example.com",
  "subdomain": "www.example.com",
  "source": "subfinder",
  "mission_id": "uuid"
}

// HTTP_SERVICE
{
  "url": "https://www.example.com",
  "status_code": 200,
  "title": "Example Site",
  "technology": ["WordPress", "PHP"],
  "ip": "192.168.1.1"
}

// ENDPOINT
{
  "path": "/api/v1/users",
  "method": "GET",
  "category": "API",
  "source": "js_intel",
  "risk_score": 75
}

// HYPOTHESIS
{
  "title": "Insecure Direct Object References",
  "attack_type": "IDOR",
  "target_id": "endpoint:/api/users",
  "confidence": 0.8,
  "status": "unverified"
}

// AGENT_RUN
{
  "agent_id": "pathfinder",
  "agent_name": "pathfinder",
  "task": "Subdomain enumeration",
  "phase": "OSINT",
  "status": "completed",
  "start_time": "2025-12-15T18:00:00Z",
  "end_time": "2025-12-15T18:02:00Z",
  "duration": 120000
}

// TOOL_CALL
{
  "tool_name": "subfinder",
  "agent_id": "pathfinder",
  "arguments": {"domain": "example.com"},
  "status": "success",
  "result_count": 48,
  "duration": 60000
}
```

### Edge

```graphql
type Edge {
  fromNode: String!
  toNode: String!
  relation: String!
}
```

### GraphStats

```graphql
type GraphStats {
  missionId: String!
  totalNodes: Int!
  totalEdges: Int!
  nodesByType: JSON!
}
```

**Exemple de `nodesByType`:**
```json
{
  "DOMAIN": 1,
  "SUBDOMAIN": 48,
  "HTTP_SERVICE": 19,
  "ENDPOINT": 156,
  "PARAMETER": 32,
  "HYPOTHESIS": 15,
  "VULNERABILITY": 0,
  "AGENT_RUN": 16,
  "TOOL_CALL": 12
}
```

### AttackPath

```graphql
type AttackPath {
  target: String!
  score: Int!
  actions: [String!]!
  reasons: [String!]!
}
```

### GraphEvent

```graphql
type GraphEvent {
  runId: String!
  eventType: String!
  source: String
  payload: JSON!
  timestamp: DateTime!
}
```

### LogEvent

```graphql
type LogEvent {
  runId: String!
  level: String!
  phase: String
  message: String!
  timestamp: DateTime!
  metadata: JSON
}
```

---

## Inputs

### MissionInput

```graphql
input MissionInput {
  targetDomain: String!
  mode: MissionMode
  seedSubdomains: [String!]
}
```

### NodeFilter

```graphql
input NodeFilter {
  types: [NodeType!]
}
```

---

## Queries

### mission

Obtenir une mission par ID.

```graphql
query GetMission($id: String!) {
  mission(id: $id) {
    id
    targetDomain
    mode
    status
    currentPhase
    createdAt
    progress
  }
}
```

### missions

Lister les missions avec pagination.

```graphql
query GetMissions($limit: Int, $offset: Int) {
  missions(limit: $limit, offset: $offset) {
    items {
      id
      targetDomain
      mode
      status
      createdAt
    }
    total
  }
}
```

### nodes

Obtenir les noeuds d'une mission avec filtres optionnels.

```graphql
query GetNodes($missionId: String!, $filter: NodeFilter, $limit: Int) {
  nodes(missionId: $missionId, filter: $filter, limit: $limit) {
    id
    type
    properties
  }
}
```

### edges

Obtenir les relations d'une mission.

```graphql
query GetEdges($missionId: String!) {
  edges(missionId: $missionId) {
    fromNode
    toNode
    relation
  }
}
```

### graphStats

Obtenir les statistiques du graphe.

```graphql
query GetStats($missionId: String!) {
  graphStats(missionId: $missionId) {
    missionId
    totalNodes
    totalEdges
    nodesByType
  }
}
```

### attackPaths

Obtenir les chemins d'attaque suggérés.

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

### workflowNodes

Obtenir les noeuds de workflow (agents et outils).

```graphql
query GetWorkflowNodes($missionId: String!, $types: [NodeType!]) {
  workflowNodes(missionId: $missionId, types: $types) {
    id
    type
    properties
  }
}
```

### workflowLayout

Obtenir le layout sauvegardé du workflow.

```graphql
query GetWorkflowLayout($missionId: String!) {
  workflowLayout(missionId: $missionId)
}
```

---

## Mutations

### startMission

Créer et démarrer une nouvelle mission.

```graphql
mutation StartMission($input: MissionInput!) {
  startMission(input: $input) {
    id
    targetDomain
    status
  }
}
```

**Variables:**
```json
{
  "input": {
    "targetDomain": "example.com",
    "mode": "AGGRESSIVE",
    "seedSubdomains": ["www.example.com", "api.example.com"]
  }
}
```

### cancelMission

Annuler une mission en cours.

```graphql
mutation CancelMission($id: String!) {
  cancelMission(id: $id)
}
```

### deleteMission

Supprimer une mission et toutes ses données.

```graphql
mutation DeleteMission($missionId: String!) {
  deleteMission(missionId: $missionId)
}
```

### saveWorkflowLayout

Sauvegarder le layout du workflow.

```graphql
mutation SaveLayout($missionId: String!, $positions: JSON!, $zoom: Float, $pan: JSON) {
  saveWorkflowLayout(missionId: $missionId, positions: $positions, zoom: $zoom, pan: $pan)
}
```

**Variables:**
```json
{
  "missionId": "uuid",
  "positions": {
    "agent-pathfinder-xxx": { "x": 100, "y": 200 }
  },
  "zoom": 0.8,
  "pan": { "x": 50, "y": 100 }
}
```

---

## Subscriptions

### graphEvents

S'abonner aux événements du graphe en temps réel.

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
```

**Event Types:**
- `NODE_ADDED` - Nouveau noeud créé
- `NODE_UPDATED` - Noeud mis à jour
- `NODE_DELETED` - Noeud supprimé
- `EDGE_ADDED` - Nouvelle relation créée
- `EDGE_DELETED` - Relation supprimée
- `ATTACK_PATH_ADDED` - Nouveau chemin d'attaque

### logs

S'abonner aux logs de mission en temps réel.

```graphql
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

**Log Levels:**
- `DEBUG` - Informations de debug
- `INFO` - Informations générales
- `WARNING` - Avertissements
- `ERROR` - Erreurs

---

## Exemples Complets

### Mission Complète avec Stats

```graphql
query GetMissionComplete($id: String!) {
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
  attackPaths(missionId: $id, top: 5) {
    target
    score
    actions
    reasons
  }
}
```

### Dashboard avec Missions Récentes

```graphql
query Dashboard {
  missions(limit: 10, offset: 0) {
    items {
      id
      targetDomain
      status
      createdAt
      progress
    }
    total
  }
}
```

### Workflow Complet

```graphql
query GetWorkflow($missionId: String!) {
  agentRuns: workflowNodes(missionId: $missionId, types: [AGENT_RUN]) {
    id
    type
    properties
  }
  toolCalls: workflowNodes(missionId: $missionId, types: [TOOL_CALL]) {
    id
    type
    properties
  }
  layout: workflowLayout(missionId: $missionId)
}
```

### Endpoints à Haut Risque

```graphql
query GetHighRiskEndpoints($missionId: String!) {
  endpoints: nodes(missionId: $missionId, filter: { types: [ENDPOINT] }, limit: 100) {
    id
    type
    properties
  }
  hypotheses: nodes(missionId: $missionId, filter: { types: [HYPOTHESIS] }, limit: 100) {
    id
    type
    properties
  }
}
```

---

## Scalaires Personnalisés

### DateTime

Format ISO 8601: `2025-12-15T18:00:00.000Z`

### JSON

Objet JSON arbitraire, utilisé pour les propriétés dynamiques.

---

## Erreurs

### Format

```json
{
  "errors": [
    {
      "message": "Mission not found",
      "locations": [{ "line": 2, "column": 3 }],
      "path": ["mission"]
    }
  ],
  "data": null
}
```

### Codes Courants

| Code | Description |
|------|-------------|
| `MISSION_NOT_FOUND` | Mission inexistante |
| `INVALID_INPUT` | Données d'entrée invalides |
| `SERVICE_UNAVAILABLE` | Service backend indisponible |
| `UNAUTHORIZED` | Non autorisé |
