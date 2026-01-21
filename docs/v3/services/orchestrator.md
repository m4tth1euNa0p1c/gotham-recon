# Recon Orchestrator Service

> **Service de coordination des missions de reconnaissance**
>
> Port: 8000 | Base URL: `http://localhost:8000`
>
> Version: 3.2.1 | Dernière mise à jour: Décembre 2025

---

## Changelog v3.2.1

### Nuclei Vulnerability Scanning

| Feature | Description |
|---------|-------------|
| **NucleiTool** | Intégration complète de Nuclei pour la détection de vulnérabilités |
| **Template Support** | Support des templates `cves`, `exposures`, `misconfiguration`, `vulnerabilities` |
| **Severity Mapping** | Mapping automatique des sévérités (CRITICAL → 9.0, HIGH → 7.0, etc.) |
| **CVSS Scoring** | Score CVSS calculé automatiquement pour chaque vulnérabilité |

### Outil Nuclei dans Docker

Le Dockerfile inclut maintenant Nuclei:

```dockerfile
# Install Nuclei for vulnerability scanning
RUN wget -q https://github.com/projectdiscovery/nuclei/releases/download/v3.3.7/nuclei_3.3.7_linux_amd64.zip -O /tmp/nuclei.zip \
    && unzip -q /tmp/nuclei.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/nuclei \
    && rm /tmp/nuclei.zip

# Download Nuclei templates
RUN mkdir -p /root/nuclei-templates \
    && nuclei -update-templates -silent || true
```

### Known Limitations

| Issue | Description | Workaround |
|-------|-------------|------------|
| **Single Worker** | Uvicorn avec 1 worker bloque pendant l'exécution CrewAI | Timeout BFF augmenté à 60s |
| **API Latency** | API peut être lente pendant une mission active | Retry automatique côté client |

---

## Changelog v3.2.0

### Reflection Architecture Integration

| Feature | Description |
|---------|-------------|
| **ReflectionLoop** | Cycle de réflexion après chaque appel d'outil |
| **ResultAnalyzer** | Analyse des résultats pour détecter les gaps |
| **ScriptGenerator** | Génération de scripts d'investigation |
| **PythonScriptExecutorTool** | Exécution sécurisée avec validation AST |
| **Reflection Stats** | Métriques de réflexion dans les résultats de mission |

---

## Vue d'Ensemble

Le Recon Orchestrator est le service central qui coordonne l'exécution des missions de reconnaissance. Il gère le cycle de vie des missions, orchestre les phases d'exécution, et intègre le moteur CrewAI pour les agents intelligents.

### Responsabilités

- Gestion CRUD des missions
- Orchestration des phases (OSINT → Active → Intel → Verification → Reporting)
- Intégration CrewAI (agents et tasks)
- Émission d'événements de progression via Kafka
- Streaming de logs en temps réel (SSE/WebSocket)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RECON ORCHESTRATOR                            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      FastAPI Router                         │ │
│  │  /api/v1/missions  |  /api/v1/sse/logs  |  /api/v1/llm     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │                    Core Services                           │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │   Mission    │  │    Phase     │  │    CrewAI        │ │  │
│  │  │   Manager    │  │  Coordinator │  │    Engine        │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┼───────────────────────────────┐  │
│  │                   Infrastructure                           │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
│  │  │  PostgreSQL  │  │    Kafka     │  │   Phase Service  │ │  │
│  │  │   (Missions) │  │  (Events)    │  │     Clients      │ │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### Health & Status

#### GET `/health`
Health check du service.

**Response 200:**
```json
{
  "status": "healthy",
  "service": "recon-orchestrator",
  "kafka": "connected",
  "database": "connected",
  "timestamp": "2025-12-15T18:00:00Z"
}
```

#### GET `/api/v1/llm/status`
Statut de la connexion LLM et configuration CrewAI.

**Response 200:**
```json
{
  "status": "connected",
  "provider": "ollama",
  "model": "qwen2.5:14b",
  "coder_model": "qwen2.5-coder:7b",
  "url": "http://ollama:11434",
  "crewai_available": true,
  "crewai_enabled": true
}
```

---

### Missions

#### POST `/api/v1/missions`
Créer et démarrer une nouvelle mission.

**Request Body:**
```json
{
  "target_domain": "example.com",
  "mode": "AGGRESSIVE",
  "seed_subdomains": ["www.example.com", "api.example.com"],
  "options": {
    "skip_wayback": false,
    "max_endpoints": 500
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target_domain` | string | Yes | Domaine cible à scanner |
| `mode` | enum | No | `STEALTH` / `AGGRESSIVE` / `BALANCED` (default: AGGRESSIVE) |
| `seed_subdomains` | array | No | Liste de sous-domaines à injecter |
| `options` | object | No | Options additionnelles |

**Response 201:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "target_domain": "example.com",
  "mode": "AGGRESSIVE",
  "status": "PENDING",
  "current_phase": null,
  "created_at": "2025-12-15T18:00:00Z",
  "updated_at": "2025-12-15T18:00:00Z",
  "progress": {}
}
```

#### GET `/api/v1/missions`
Lister toutes les missions.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Nombre max de résultats |
| `offset` | integer | 0 | Offset pour pagination |

**Response 200:**
```json
{
  "missions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "target_domain": "example.com",
      "mode": "AGGRESSIVE",
      "status": "COMPLETED",
      "current_phase": null,
      "created_at": "2025-12-15T18:00:00Z",
      "updated_at": "2025-12-15T18:30:00Z",
      "progress": {
        "phases_completed": ["OSINT", "ACTIVE_RECON", "ENDPOINT_INTEL"],
        "current_metrics": { /* ... */ }
      }
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

#### GET `/api/v1/missions/{mission_id}`
Obtenir les détails d'une mission.

**Response 200:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "target_domain": "example.com",
  "mode": "AGGRESSIVE",
  "status": "COMPLETED",
  "current_phase": null,
  "created_at": "2025-12-15T18:00:00Z",
  "updated_at": "2025-12-15T18:30:00Z",
  "progress": {
    "phases_completed": ["OSINT", "ACTIVE_RECON", "ENDPOINT_INTEL", "VERIFICATION", "REPORTING"],
    "current_metrics": {
      "crewai": {
        "mission_id": "550e8400-e29b-41d4-a716-446655440000",
        "target_domain": "example.com",
        "status": "completed",
        "duration": 207.03,
        "summary": {
          "subdomains": 48,
          "http_services": 19,
          "endpoints": 156,
          "dns_records": 20
        },
        "phases": {
          "passive": {
            "phase": "passive_recon",
            "duration": 172.34,
            "result": { /* ... */ }
          },
          "active": {
            "phase": "active_recon",
            "duration": 4.71,
            "result": { /* ... */ }
          }
        }
      }
    }
  }
}
```

#### DELETE `/api/v1/missions/{mission_id}`
Supprimer une mission et toutes ses données associées.

**Response 200:**
```json
{
  "status": "deleted",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "mission_deleted": true,
  "nodes_deleted": 256,
  "edges_deleted": 512,
  "logs_deleted": 1024
}
```

#### POST `/api/v1/missions/{mission_id}/cancel`
Annuler une mission en cours.

**Response 200:**
```json
{
  "status": "cancelled",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Phases

#### POST `/api/v1/missions/{mission_id}/phases/{phase}`
Déclencher manuellement une phase.

**Path Parameters:**
| Parameter | Type | Values |
|-----------|------|--------|
| `mission_id` | string | UUID de la mission |
| `phase` | enum | `OSINT`, `SAFETY_NET`, `ACTIVE_RECON`, `ENDPOINT_INTEL`, `VERIFICATION`, `REPORTING` |

**Response 200:**
```json
{
  "status": "triggered",
  "phase": "OSINT",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Data Management

#### DELETE `/api/v1/data/clear`
Supprimer TOUTES les données (dangereux).

**Query Parameters:**
| Parameter | Type | Required | Value |
|-----------|------|----------|-------|
| `confirm` | string | Yes | `YES` |

**Response 200:**
```json
{
  "status": "cleared",
  "missions_deleted": 5,
  "nodes_deleted": 1024,
  "edges_deleted": 2048,
  "logs_deleted": 4096
}
```

---

### Real-time Logs

#### GET `/api/v1/sse/logs/{mission_id}`
Server-Sent Events pour les logs de mission.

**Event Format:**
```
event: log
data: {"level": "INFO", "phase": "passive_recon", "message": "Subfinder found 48 subdomains", "timestamp": "2025-12-15T18:00:00Z"}

event: agent_started
data: {"run_id": "agent-pathfinder-xxx", "agent_id": "pathfinder", "task": "Subdomain enumeration", "phase": "OSINT"}

event: tool_called
data: {"call_id": "tool-subfinder-xxx", "tool_name": "subfinder", "agent_id": "pathfinder", "arguments": {"domain": "example.com"}}

event: tool_finished
data: {"call_id": "tool-subfinder-xxx", "tool_name": "subfinder", "result": {"count": 48}, "status": "success", "duration": 60000}

event: agent_finished
data: {"run_id": "agent-pathfinder-xxx", "agent_id": "pathfinder", "result": "Completed", "status": "success", "duration": 120000}
```

---

## Modèle de Données

### Mission

```python
class Mission(BaseModel):
    id: str                          # UUID
    target_domain: str               # Domaine cible
    mode: MissionMode                # STEALTH | AGGRESSIVE | BALANCED
    status: MissionStatus            # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    current_phase: Optional[PhaseType]
    created_at: datetime
    updated_at: datetime
    progress: Dict[str, Any]         # Métriques et résultats
```

### MissionStatus

```python
class MissionStatus(str, Enum):
    PENDING = "PENDING"       # En attente de démarrage
    RUNNING = "RUNNING"       # En cours d'exécution
    COMPLETED = "COMPLETED"   # Terminée avec succès
    FAILED = "FAILED"         # Échec
    CANCELLED = "CANCELLED"   # Annulée
```

### PhaseType

```python
class PhaseType(str, Enum):
    OSINT = "OSINT"                     # Phase 1: Reconnaissance passive
    SAFETY_NET = "SAFETY_NET"           # Gate check + fallback
    ACTIVE_RECON = "ACTIVE_RECON"       # Phase 3: Probing HTTP
    ENDPOINT_INTEL = "ENDPOINT_INTEL"   # Phase 23: Enrichissement
    VERIFICATION = "VERIFICATION"       # Phase 24-25: Validation
    REPORTING = "REPORTING"             # Génération de rapports
```

---

## Configuration

### Variables d'Environnement

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL PostgreSQL | `postgresql://gotham:gotham@postgres:5432/gotham` |
| `KAFKA_BOOTSTRAP_SERVERS` | Serveurs Kafka | `kafka:9092` |
| `GRAPH_SERVICE_URL` | URL Graph Service | `http://graph-service:8001` |
| `BFF_GATEWAY_URL` | URL BFF Gateway | `http://bff-gateway:8080` |
| `OLLAMA_BASE_URL` | URL Ollama | `http://ollama:11434` |
| `MODEL_NAME` | Modèle LLM principal | `qwen2.5:14b` |
| `OLLAMA_CODER_MODEL` | Modèle pour code | `qwen2.5-coder:7b` |
| `CREWAI_ENABLED` | Activer CrewAI | `true` |

### Fichiers de Configuration

```
services/recon-orchestrator/
├── config/
│   ├── agents.yaml      # Définition des agents CrewAI
│   ├── tasks.yaml       # Définition des tâches
│   └── budget.yaml      # Seuils et limites
```

---

## Kafka Events

### Topics Produits

| Topic | Events |
|-------|--------|
| `logs.recon` | LOG, AGENT_STARTED, AGENT_FINISHED, TOOL_CALLED, TOOL_FINISHED |
| `mission.state` | MISSION_CREATED, PHASE_STARTED, PHASE_COMPLETED, MISSION_COMPLETED, MISSION_FAILED |

### Format des Events

```json
{
  "event_type": "AGENT_STARTED",
  "mission_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1702666849.123,
  "iso_timestamp": "2025-12-15T18:00:49Z",
  "payload": {
    "agent_id": "pathfinder",
    "agent_name": "pathfinder",
    "task": "Subdomain enumeration",
    "phase": "OSINT",
    "model": "crewai",
    "start_time": "2025-12-15T18:00:00.000Z"
  }
}
```

---

## Intégration CrewAI

### Agents Disponibles

| Agent | Rôle | Outils |
|-------|------|--------|
| `pathfinder` | Lead Reconnaissance Orchestrator | subfinder, dns_resolver |
| `watchtower` | Senior Intelligence Analyst | dns_intel, asn_lookup |
| `tech_fingerprinter` | StackTrace - Tech Detection | httpx |
| `js_intel` | DeepScript - JS Mining | js_miner |
| `page_analyzer` | DeepDive - Page Analysis | page_analyzer |
| `coder_agent` | Adaptive Code Intelligence | python_executor |
| `reflector_agent` | Result Validation & Enrichment | python_script_executor |

### Flow d'Exécution

```python
# Exemple simplifié du flow CrewAI
def run_passive_phase(target_domain: str):
    crew = Crew(
        agents=[pathfinder, watchtower, tech_fingerprinter, js_intel],
        tasks=[
            subdomain_discovery_task,
            dns_analysis_task,
            tech_fingerprint_task,
            js_mining_task
        ],
        process=Process.sequential,
        verbose=True
    )

    results = crew.kickoff(inputs={"target_domain": target_domain})
    return results
```

---

## Reflection Loop (v3.2)

Le cycle de réflexion s'exécute après chaque appel d'outil pour valider et enrichir les résultats.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    REFLECTION LOOP                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Tool Call        ResultAnalyzer       ScriptGenerator          │
│   (subfinder)  →   (analyze)        →   (generate)               │
│       │                │                     │                   │
│       ▼                ▼                     ▼                   │
│   ┌────────┐     ┌──────────┐         ┌──────────┐              │
│   │ Result │ ──▶ │ Findings │ ──────▶ │ Scripts  │              │
│   └────────┘     └──────────┘         └──────────┘              │
│                        │                     │                   │
│                        ▼                     ▼                   │
│                  ┌──────────┐         ┌──────────┐              │
│                  │  Issues  │         │ Execute  │              │
│                  │  Found   │         │ Scripts  │              │
│                  └──────────┘         └──────────┘              │
│                                              │                   │
│                                              ▼                   │
│                                       ┌──────────┐              │
│                                       │ Enrich   │              │
│                                       │ Graph    │              │
│                                       └──────────┘              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Intégration dans crew_runner.py

```python
class CrewMissionRunner:
    async def run_reflection(self, tool_name: str, result: Any, context: Dict = None):
        """Run reflection after each tool call."""
        if not REFLECTION_AVAILABLE:
            return {"skipped": True}

        reflection_result = await reflect_and_enrich(
            tool_name=tool_name,
            result=result,
            mission_id=self.mission_id,
            context=context,
            script_executor=self.script_executor,
            graph_service_url="http://graph-service:8001"
        )

        self.reflection_stats["reflections_run"] += 1
        return reflection_result

    async def run_passive_phase(self):
        # Step 1: Subfinder
        self.subdomains = await self.run_subfinder_direct()
        await self.run_reflection("subfinder", {"subdomains": self.subdomains})

        # Step 2: Wayback
        wayback_data = await self.run_wayback_scan(self.subdomains)
        await self.run_reflection("wayback", {"urls": wayback_data})

        # Step 3: DNS
        self.dns_records = await self.run_dns_resolution(self.subdomains)
        await self.run_reflection("dns_resolver", {"records": self.dns_records})
```

### Métriques de Réflexion

Les métriques sont incluses dans le résultat de mission:

```json
{
  "mission_id": "abc-123",
  "status": "completed",
  "reflection_stats": {
    "reflections_run": 3,
    "scripts_executed": 1,
    "enrichments_added": 5,
    "issues_found": 6
  }
}
```

### Scripts Disponibles

| Template | Déclencheur | Action |
|----------|-------------|--------|
| `dns_bruteforce` | Subfinder < 5 résultats | Bruteforce DNS supplémentaire |
| `tech_fingerprint` | HTTPX sans tech detection | Fingerprinting avancé |
| `config_checker` | Wayback endpoints sensibles | Vérification des configs exposées |
| `port_check` | Service HTTP actif | Scan de ports additionnels |
| `header_analysis` | Response headers intéressants | Analyse approfondie |
| `certificate_check` | Service HTTPS | Analyse du certificat SSL/TLS |

---

## Healthcheck

Le service expose un healthcheck Docker:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Dépendances

### Services Requis
- PostgreSQL (database)
- Kafka (events)
- Graph Service (storage)

### Services Optionnels
- Ollama (LLM)
- Phase Services (8002-8006)

---

## Logs

Les logs sont structurés en JSON avec les champs:

```json
{
  "timestamp": "2025-12-15T18:00:00.000Z",
  "level": "INFO",
  "service": "recon-orchestrator",
  "run_id": "uuid",
  "mission_id": "uuid",
  "phase": "OSINT",
  "component": "crewai",
  "message": "Starting passive reconnaissance",
  "metadata": {}
}
```
