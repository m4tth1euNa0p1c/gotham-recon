# Modèle de Données - Recon Gotham v3.0

> **Documentation des schémas de base de données**

---

## Vue d'Ensemble

Recon Gotham utilise deux systèmes de stockage:
- **PostgreSQL**: Base principale pour les missions (Orchestrator)
- **SQLite**: Base légère pour le graphe d'assets (Graph Service)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA ARCHITECTURE                             │
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────────────┐   │
│  │      PostgreSQL      │    │          SQLite              │   │
│  │    (Orchestrator)    │    │      (Graph Service)         │   │
│  ├──────────────────────┤    ├──────────────────────────────┤   │
│  │ • missions           │    │ • nodes                      │   │
│  │ • mission_logs       │    │ • edges                      │   │
│  │ • phase_metrics      │    │ • logs                       │   │
│  │                      │    │ • layouts                    │   │
│  └──────────────────────┘    └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## PostgreSQL (Orchestrator)

### Table: missions

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Identifiant unique |
| `target_domain` | VARCHAR(255) | NOT NULL | Domaine cible |
| `mode` | VARCHAR(20) | NOT NULL | STEALTH/AGGRESSIVE/BALANCED |
| `status` | VARCHAR(20) | NOT NULL | PENDING/RUNNING/COMPLETED/FAILED/CANCELLED |
| `current_phase` | VARCHAR(50) | NULLABLE | Phase en cours |
| `progress` | JSONB | DEFAULT '{}' | Métriques et résultats |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Date de création |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Date de mise à jour |

```sql
CREATE TABLE missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_domain VARCHAR(255) NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'AGGRESSIVE',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    current_phase VARCHAR(50),
    progress JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_missions_status ON missions(status);
CREATE INDEX idx_missions_target ON missions(target_domain);
CREATE INDEX idx_missions_created ON missions(created_at DESC);
```

### Table: mission_logs

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | ID auto-incrémenté |
| `mission_id` | UUID | FOREIGN KEY | Référence mission |
| `level` | VARCHAR(10) | NOT NULL | DEBUG/INFO/WARNING/ERROR |
| `phase` | VARCHAR(50) | NULLABLE | Phase concernée |
| `message` | TEXT | NOT NULL | Message du log |
| `metadata` | JSONB | DEFAULT '{}' | Données additionnelles |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Timestamp |

```sql
CREATE TABLE mission_logs (
    id SERIAL PRIMARY KEY,
    mission_id UUID NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    level VARCHAR(10) NOT NULL,
    phase VARCHAR(50),
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_logs_mission ON mission_logs(mission_id);
CREATE INDEX idx_logs_level ON mission_logs(level);
CREATE INDEX idx_logs_created ON mission_logs(created_at DESC);
```

### Table: phase_metrics

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | ID auto-incrémenté |
| `mission_id` | UUID | FOREIGN KEY | Référence mission |
| `phase` | VARCHAR(50) | NOT NULL | Nom de la phase |
| `duration_ms` | INTEGER | NOT NULL | Durée en millisecondes |
| `result` | JSONB | DEFAULT '{}' | Résultats de la phase |
| `started_at` | TIMESTAMP | NOT NULL | Début de la phase |
| `completed_at` | TIMESTAMP | NULLABLE | Fin de la phase |

```sql
CREATE TABLE phase_metrics (
    id SERIAL PRIMARY KEY,
    mission_id UUID NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    phase VARCHAR(50) NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    result JSONB DEFAULT '{}',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_metrics_mission ON phase_metrics(mission_id);
CREATE INDEX idx_metrics_phase ON phase_metrics(phase);
```

---

## SQLite (Graph Service)

### Table: nodes

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | Identifiant unique du noeud |
| `type` | TEXT | NOT NULL | Type de noeud (voir NodeTypes) |
| `mission_id` | TEXT | NOT NULL | ID de la mission |
| `properties` | TEXT | JSON | Propriétés du noeud |
| `created_at` | TEXT | ISO 8601 | Date de création |
| `updated_at` | TEXT | ISO 8601 | Date de mise à jour |

```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    properties TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_nodes_mission ON nodes(mission_id);
CREATE INDEX idx_nodes_type ON nodes(type);
CREATE INDEX idx_nodes_mission_type ON nodes(mission_id, type);
```

### Table: edges

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | Identifiant unique |
| `from_node` | TEXT | NOT NULL | ID du noeud source |
| `to_node` | TEXT | NOT NULL | ID du noeud destination |
| `edge_type` | TEXT | NOT NULL | Type de relation |
| `mission_id` | TEXT | NOT NULL | ID de la mission |
| `properties` | TEXT | JSON | Propriétés additionnelles |
| `created_at` | TEXT | ISO 8601 | Date de création |

```sql
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    from_node TEXT NOT NULL,
    to_node TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    properties TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_edges_mission ON edges(mission_id);
CREATE INDEX idx_edges_from ON edges(from_node);
CREATE INDEX idx_edges_to ON edges(to_node);
CREATE INDEX idx_edges_type ON edges(edge_type);
```

### Table: logs

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | ID auto-incrémenté |
| `mission_id` | TEXT | NOT NULL | ID de la mission |
| `level` | TEXT | NOT NULL | Niveau de log |
| `phase` | TEXT | NULLABLE | Phase concernée |
| `message` | TEXT | NOT NULL | Message |
| `metadata` | TEXT | JSON | Métadonnées |
| `created_at` | TEXT | ISO 8601 | Timestamp |

```sql
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id TEXT NOT NULL,
    level TEXT NOT NULL,
    phase TEXT,
    message TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_glogs_mission ON logs(mission_id);
```

### Table: layouts

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `mission_id` | TEXT | PRIMARY KEY | ID de la mission |
| `positions` | TEXT | NOT NULL | JSON des positions |
| `zoom` | REAL | NULLABLE | Niveau de zoom |
| `pan` | TEXT | NULLABLE | JSON du pan {x, y} |
| `updated_at` | TEXT | ISO 8601 | Date de mise à jour |

```sql
CREATE TABLE layouts (
    mission_id TEXT PRIMARY KEY,
    positions TEXT NOT NULL,
    zoom REAL,
    pan TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
```

---

## Types de Noeuds (NodeTypes)

### Asset Nodes

```json
{
  "DOMAIN": {
    "description": "Domaine racine",
    "id_format": "domain:{name}",
    "properties": {
      "name": "string",
      "registrar": "string?",
      "created_date": "datetime?"
    }
  },
  "SUBDOMAIN": {
    "description": "Sous-domaine découvert",
    "id_format": "subdomain:{name}",
    "properties": {
      "name": "string",
      "subdomain": "string",
      "source": "subfinder|wayback|dns|manual",
      "first_seen": "datetime"
    }
  },
  "HTTP_SERVICE": {
    "description": "Service HTTP actif",
    "id_format": "http_service:{url}",
    "properties": {
      "url": "string",
      "status_code": "integer",
      "title": "string?",
      "technology": "string[]",
      "ip": "string?",
      "content_length": "integer?",
      "response_time_ms": "integer?"
    }
  },
  "ENDPOINT": {
    "description": "Endpoint API ou page",
    "id_format": "endpoint:{path}",
    "properties": {
      "path": "string",
      "method": "GET|POST|PUT|DELETE|PATCH",
      "category": "API|ADMIN|AUTH|LEGACY|STATIC|WAYBACK",
      "source": "js_intel|wayback|html_crawl|robots",
      "risk_score": "integer (0-100)",
      "origin": "string",
      "confidence": "float (0-1)"
    }
  },
  "PARAMETER": {
    "description": "Paramètre d'URL",
    "id_format": "param:{endpoint_id}:{name}",
    "properties": {
      "name": "string",
      "location": "path|query|body|header",
      "endpoint_id": "string",
      "param_type": "string|integer|boolean|array",
      "required": "boolean"
    }
  },
  "IP_ADDRESS": {
    "description": "Adresse IP",
    "id_format": "ip:{address}",
    "properties": {
      "address": "string",
      "asn": "string?",
      "org": "string?",
      "country": "string?"
    }
  },
  "DNS_RECORD": {
    "description": "Enregistrement DNS",
    "id_format": "dns:{type}:{subdomain}",
    "properties": {
      "type": "A|AAAA|CNAME|MX|TXT|NS|SOA",
      "value": "string",
      "subdomain": "string",
      "ttl": "integer?"
    }
  }
}
```

### Security Nodes

```json
{
  "HYPOTHESIS": {
    "description": "Hypothèse de vulnérabilité",
    "id_format": "hypothesis:{attack_type}:{target_id}",
    "properties": {
      "title": "string",
      "attack_type": "SQLI|XSS|IDOR|SSRF|LFI|RFI|RCE|AUTH_BYPASS|OPEN_REDIRECT|INFO_DISCLOSURE|CSRF|XXE|SSTI",
      "target_id": "string",
      "confidence": "float (0-1)",
      "rationale": "string?",
      "status": "unverified|confirmed|false_positive"
    }
  },
  "VULNERABILITY": {
    "description": "Vulnérabilité confirmée",
    "id_format": "vuln:{cve_id}:{target_id}",
    "properties": {
      "title": "string",
      "cve_id": "string?",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "cvss_score": "float?",
      "target_id": "string",
      "evidence": "string?",
      "remediation": "string?"
    }
  },
  "ATTACK_PATH": {
    "description": "Chemin d'attaque suggéré",
    "id_format": "attack_path:{target}:{hash}",
    "properties": {
      "target": "string",
      "score": "integer (0-100)",
      "actions": "string[]",
      "reasons": "string[]"
    }
  }
}
```

### Workflow Nodes

```json
{
  "AGENT_RUN": {
    "description": "Exécution d'un agent",
    "id_format": "agent-{agent_id}-{timestamp}",
    "properties": {
      "agent_id": "string",
      "agent_name": "string",
      "task": "string",
      "phase": "OSINT|ACTIVE_RECON|ENDPOINT_INTEL|VERIFICATION|REPORTING",
      "status": "pending|running|completed|error",
      "model": "string?",
      "start_time": "datetime",
      "end_time": "datetime?",
      "duration": "integer (ms)"
    }
  },
  "TOOL_CALL": {
    "description": "Appel d'un outil",
    "id_format": "tool-{tool_name}-{timestamp}",
    "properties": {
      "tool_name": "string",
      "agent_id": "string?",
      "arguments": "object",
      "status": "pending|running|success|error",
      "result_count": "integer?",
      "error_message": "string?",
      "start_time": "datetime",
      "end_time": "datetime?",
      "duration": "integer (ms)"
    }
  },
  "LLM_REASONING": {
    "description": "Raisonnement LLM",
    "id_format": "llm-{hash}-{timestamp}",
    "properties": {
      "prompt": "string",
      "response": "string",
      "model": "string",
      "tokens_used": "integer",
      "latency_ms": "integer"
    }
  }
}
```

---

## Types de Relations (EdgeTypes)

### Asset Relations

| Type | De | Vers | Description |
|------|----|----- |-------------|
| `HAS_SUBDOMAIN` | DOMAIN | SUBDOMAIN | Domaine contient sous-domaine |
| `RESOLVES_TO` | SUBDOMAIN | IP_ADDRESS | DNS A/AAAA résolution |
| `HAS_DNS` | SUBDOMAIN | DNS_RECORD | Subdomain a enregistrement DNS |
| `SERVES` | IP_ADDRESS | HTTP_SERVICE | IP héberge service |
| `EXPOSES_HTTP` | SUBDOMAIN | HTTP_SERVICE | Subdomain expose HTTP |
| `EXPOSES_ENDPOINT` | HTTP_SERVICE | ENDPOINT | Service expose endpoint |
| `HAS_PARAM` | ENDPOINT | PARAMETER | Endpoint a paramètre |
| `USES_TECH` | HTTP_SERVICE | TECHNOLOGY | Service utilise technologie |

### Security Relations

| Type | De | Vers | Description |
|------|----|----- |-------------|
| `HAS_HYPOTHESIS` | ENDPOINT | HYPOTHESIS | Endpoint a hypothèse |
| `HAS_VULNERABILITY` | ENDPOINT | VULNERABILITY | Endpoint a vulnérabilité |
| `TARGETS` | ATTACK_PATH | ENDPOINT | Chemin cible endpoint |
| `CONFIRMS` | VULNERABILITY | HYPOTHESIS | Vuln confirme hypothèse |

### Workflow Relations

| Type | De | Vers | Description |
|------|----|----- |-------------|
| `TRIGGERS` | AGENT_RUN | AGENT_RUN | Agent déclenche agent |
| `USES_TOOL` | AGENT_RUN | TOOL_CALL | Agent utilise outil |
| `PRODUCES` | TOOL_CALL | NODE | Outil produit asset |
| `REFINES` | AGENT_RUN | HYPOTHESIS | Agent affine hypothèse |
| `REASONS_ABOUT` | AGENT_RUN | LLM_REASONING | Agent raisonne |
| `LINKS_TO` | NODE | NODE | Lien générique |

---

## Exemples de Requêtes

### PostgreSQL

```sql
-- Missions récentes
SELECT * FROM missions
ORDER BY created_at DESC
LIMIT 10;

-- Missions par statut
SELECT status, COUNT(*) as count
FROM missions
GROUP BY status;

-- Logs d'erreur d'une mission
SELECT * FROM mission_logs
WHERE mission_id = 'uuid' AND level = 'ERROR'
ORDER BY created_at DESC;

-- Durée moyenne par phase
SELECT phase, AVG(duration_ms) as avg_duration
FROM phase_metrics
GROUP BY phase;
```

### SQLite

```sql
-- Noeuds par type pour une mission
SELECT type, COUNT(*) as count
FROM nodes
WHERE mission_id = 'uuid'
GROUP BY type;

-- Endpoints à haut risque
SELECT * FROM nodes
WHERE mission_id = 'uuid'
  AND type = 'ENDPOINT'
  AND json_extract(properties, '$.risk_score') >= 70;

-- Relations d'un noeud
SELECT * FROM edges
WHERE mission_id = 'uuid'
  AND (from_node = 'node_id' OR to_node = 'node_id');

-- Workflow complet
SELECT n.*, e.to_node as child_id, e.edge_type
FROM nodes n
LEFT JOIN edges e ON n.id = e.from_node
WHERE n.mission_id = 'uuid'
  AND n.type IN ('AGENT_RUN', 'TOOL_CALL')
ORDER BY json_extract(n.properties, '$.start_time');
```

---

## Maintenance

### Backup

```bash
# PostgreSQL
pg_dump -U gotham gotham > backup_$(date +%Y%m%d).sql

# SQLite
sqlite3 graph.db ".backup 'backup_$(date +%Y%m%d).db'"
```

### Nettoyage

```sql
-- PostgreSQL: Supprimer les vieilles missions
DELETE FROM missions
WHERE created_at < NOW() - INTERVAL '30 days'
  AND status IN ('COMPLETED', 'FAILED');

-- SQLite: Vacuum après suppression
VACUUM;
```
