# Recon-Gotham - Documentation Technique Complète

Ce document répond à toutes les questions techniques pour la préparation d'un PowerPoint sur l'architecture, l'orchestration, le pipeline de reconnaissance, et les aspects temps réel de Recon-Gotham.

---

## 0) Questions "Collecte Rapide" (Cadrage)

### 0.1 En 1 phrase : Quel problème résout Recon-Gotham ?

**Recon-Gotham automatise la cartographie exhaustive de la surface d'attaque d'un domaine web en orchestrant des agents IA spécialisés (CrewAI) qui exécutent des outils de reconnaissance passive/active, produisant un graphe d'assets exploitable pour les équipes Red Team.**

### 0.2 Quelle est la frontière exacte ?

| In Scope | Out of Scope |
|----------|--------------|
| Reconnaissance passive (OSINT, DNS, CT logs) | Exploitation active de vulnérabilités |
| Reconnaissance active (HTTP probing, fingerprinting) | Attaques destructives (DoS, defacement) |
| Découverte d'endpoints et de secrets | Exfiltration de données |
| Hypothèses d'attaque (théoriques) | Élévation de privilèges |
| Validation "safe" de vulnérabilités | Persistance / C2 |

### 0.3 Quels sont les modes ?

| Mode | Description | Rate Limits | Actions Autorisées |
|------|-------------|-------------|-------------------|
| **STEALTH** | Reconnaissance passive uniquement | 1 req/s | GET only, pas de fuzzing |
| **BALANCED** | Mix passif + actif modéré | 5 req/s | GET, POST avec payloads safe |
| **AGGRESSIVE** | Reconnaissance complète | 10+ req/s | Tous scans, fuzzing, nuclei |

Configuration dans `config/budget.yaml` :
```yaml
profiles:
  stealth:
    max_rps: 1
    nuclei_templates: ["safe", "info-only"]
    ffuf_enabled: false
  aggressive:
    max_rps: 10
    nuclei_templates: ["all"]
    ffuf_enabled: true
```

### 0.4 Artefacts finaux attendus

1. **`<domain>_asset_graph.json`** - Graphe complet des assets (noeuds + edges)
2. **`<domain>_summary.md`** - Rapport Markdown avec findings
3. **`<domain>_metrics.json`** - Métriques d'exécution par phase
4. **Graph temps réel** - Visualisable dans l'UI Gotham (http://localhost:3000)
5. **Attack Paths** - Top N chemins d'attaque scorés

### 0.5 "Killer Feature" unique

**L'orchestration agentique multi-agents avec graphe de connaissance temps réel.**

Contrairement aux scanners traditionnels qui produisent des listes, Recon-Gotham :
- Construit un **Asset Graph** relationnel (domaine → subdomain → service → endpoint → param → vuln)
- Utilise des **agents LLM spécialisés** qui raisonnent sur le contexte
- Produit des **hypothèses d'attaque** priorisées avec scores de risque
- Offre une **visualisation temps réel** des découvertes via SSE/WebSocket

### 0.6 Chemin nominal (Happy Path)

```
1. POST /api/v1/missions {target_domain, mode}
   └─→ Mission créée (PENDING → RUNNING)

2. Phase OSINT (Passive)
   ├─→ Agent Pathfinder: Subfinder enumeration
   ├─→ Agent Watchtower: Analysis & prioritization
   ├─→ Agent DNS: Resolution & infrastructure
   └─→ Agent ASN: IP → Organization mapping

3. Phase Active Recon
   ├─→ Agent StackTrace: HTTP fingerprinting (httpx)
   ├─→ Agent DeepScript: JS mining (endpoints, secrets)
   └─→ Agent Endpoint Analyst: Crawl + wayback

4. Phase Endpoint Intelligence
   ├─→ Categorization (API, ADMIN, AUTH, LEGACY)
   ├─→ Risk scoring (0-100)
   └─→ Hypothesis generation

5. Phase Verification (optional)
   ├─→ VulnTriage: Prioritize theoretical vulns
   ├─→ StackPolicy: Map tech → check modules
   └─→ EvidenceCurator: Validate & store proof

6. Phase Reporting
   ├─→ Attack paths generated
   ├─→ Graph exported to JSON
   └─→ Markdown summary written

7. Mission COMPLETED
```

### 0.7 Les 3 pires incidents rencontrés

| Incident | Cause | Solution |
|----------|-------|----------|
| **Mission FAILED "phantom"** | Payload non-sérialisable JSON (bytes, circular refs) | `make_json_safe()` recursive dans events.py |
| **Hallucinations LLM** | Agents inventant des subdomains | Constraints strictes dans prompts + validation scope |
| **Explosion combinatoire** | Trop de subdomains → trop de scans | Limits dans budget.yaml + prioritization |

### 0.8 Coût principal et Risque principal

**Coût principal :**
- Réseau (requêtes DNS, HTTP probing)
- LLM tokens (appels GPT/Ollama pour chaque agent)
- CPU si beaucoup de parsing JS

**Risque principal :**
- Détection par WAF/IDS (mitigé par rate limiting)
- Faux positifs dans les hypothèses (mitigé par confidence scores)

### 0.9 KPI de succès

| Métrique | Description |
|----------|-------------|
| `subdomains_discovered` | Nombre de sous-domaines trouvés |
| `endpoints_extracted` | Endpoints uniques (crawl + JS + wayback) |
| `hypotheses_generated` | Vulnérabilités théoriques identifiées |
| `confirmed_vulns` | Vulnérabilités validées |
| `mission_duration` | Temps total de la mission |
| `coverage_score` | % du domaine exploré |

### 0.10 Démo en 2 minutes

1. **Lancer une mission** : `curl -X POST http://localhost:8000/api/v1/missions -d '{"target_domain":"example.com","mode":"aggressive"}'`
2. **Ouvrir l'UI** : http://localhost:3000 → Mission en cours
3. **Montrer le graphe temps réel** : Nodes apparaissant (SUBDOMAIN → HTTP_SERVICE → ENDPOINT)
4. **Montrer les attack paths** : Top 5 chemins avec scores
5. **Export** : Télécharger le JSON graph final

---

## 1) Vision Produit & Contraintes

### 1.1 Règles/contraintes d'exécution

```yaml
# ROE (Rules of Engagement) dans budget.yaml
roe:
  allowed_methods: [GET, HEAD, OPTIONS]  # STEALTH
  forbidden_methods: [DELETE, PUT]       # Toujours interdit
  max_concurrent_requests: 10
  rate_limit_per_second: 5
  respect_robots_txt: true
  no_auth_bypass_attempts: true          # Mode STEALTH uniquement
```

### 1.2 Garantie "read-only" par défaut

- Mode **STEALTH** : Uniquement GET/HEAD, pas de POST
- **Aucune écriture** sur la cible (pas de formulaires soumis)
- Templates Nuclei filtrés : exclure `intrusive`, `dos`, `exploit`
- Validation côté orchestrateur avant chaque tool call

### 1.3 Kill switches

| Switch | Implémentation | Fichier |
|--------|----------------|---------|
| Mission timeout global | `mission_timeout: 3600` | budget.yaml |
| Phase timeout | `phase_timeout: 600` | budget.yaml |
| Tool timeout | `timeout` param par tool | tools/*.py |
| Cancel mission | `POST /missions/{id}/cancel` | orchestrator/main.py |
| Max nodes | `max_graph_nodes: 10000` | budget.yaml |

### 1.4 Gestion de la portée (Scope)

```python
# Dans graph_client.py / asset_graph.py
def is_in_scope(hostname: str, target_domain: str) -> bool:
    """Vérifie si hostname appartient au scope"""
    return hostname.endswith(f".{target_domain}") or hostname == target_domain

# Rejection automatique des hallucinations
if not is_in_scope(subdomain, self.target_domain):
    emit_log(mission_id, "WARNING", f"Out of scope rejected: {subdomain}")
    return False
```

### 1.5 Données sensibles (secrets)

- **Détection** : Regex pour API keys, tokens, passwords dans JS
- **Masquage** : Les 4 premiers + 4 derniers chars visibles : `sk-proj-****...****moMA`
- **Stockage** : Hash SHA256 de l'evidence, pas la valeur brute
- **Redaction** : `secret_redaction()` avant écriture dans graph

### 1.6 Séparation passif vs actif

| Phase | Type | Description |
|-------|------|-------------|
| OSINT | Passif | Subfinder, CT logs, WHOIS (aucune requête vers la cible) |
| DNS Resolution | Passif | Requêtes DNS uniquement |
| HTTP Probing | Actif | Connexions TCP vers la cible |
| Crawling | Actif | Téléchargement de pages |
| Nuclei/Ffuf | Actif | Payloads envoyés |

### 1.7 Protection anti-agression

```python
# Rate limiting via asyncio.Semaphore
semaphore = asyncio.Semaphore(config["max_concurrent_requests"])

# Rate limit par seconde
rate_limiter = RateLimiter(max_per_second=config["rate_limit_per_second"])

# Templates Nuclei safe only en mode STEALTH
if mode == "STEALTH":
    nuclei_templates = ["-t", "exposures/", "-severity", "info,low"]
```

### 1.8 Modèle de Risk Scoring

```python
# Dans endpoint_heuristics.py
def compute_risk_score(endpoint: dict) -> int:
    """
    Score 0-100 basé sur:
    - likelihood (0-10) × impact (0-10)
    - Category bonus: ADMIN +20, AUTH +15, API +10
    - Tech stack: PHP/ASP +10 (legacy)
    - Parameters: id/user/admin dans params +10
    """
    base = endpoint["likelihood_score"] * endpoint["impact_score"]
    category_bonus = CATEGORY_WEIGHTS.get(endpoint["category"], 0)
    return min(100, base + category_bonus)
```

---

## 2) Cartographie C4 de l'Architecture

### 2.1 Diagramme C4 Niveau 1 (Contexte)

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│   User /    │────▶│           GOTHAM RECON PLATFORM              │
│   Red Team  │◀────│                                              │
└─────────────┘     │  ┌────────┐  ┌─────────────┐  ┌───────────┐ │
                    │  │ UI     │  │ BFF Gateway │  │ Services  │ │
                    │  │ React  │─▶│ GraphQL/SSE │─▶│ Backend   │ │
                    │  └────────┘  └─────────────┘  └───────────┘ │
                    └──────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              ┌──────────┐       ┌──────────┐       ┌──────────┐
              │ Target   │       │ OSINT    │       │ Ollama/  │
              │ Domain   │       │ Sources  │       │ OpenAI   │
              └──────────┘       └──────────┘       └──────────┘
```

### 2.2 C4 Niveau 2 (Services)

| Service | Port | Responsabilité |
|---------|------|----------------|
| **gotham-ui** | 3000 | Interface React (TypeScript) |
| **bff-gateway** | 8080 | API GraphQL, SSE streaming, aggregation |
| **recon-orchestrator** | 8000 | Orchestration missions, CrewAI agents |
| **graph-service** | 8001 | CQRS graph storage, WebSocket events |
| **osint-runner** | 8002 | Exécution tools OSINT (subfinder, etc.) |
| **active-recon** | 8003 | HTTP probing, crawling |
| **endpoint-intel** | 8004 | Enrichissement, risk scoring |
| **verification** | 8005 | Validation vulns, evidence |
| **planner** | 8007 | Attack paths, next actions |
| **scanner-proxy** | 50051 | gRPC proxy vers tools binaires |

### 2.3 Flux principaux

```
┌──────────────┐  HTTP/GraphQL   ┌──────────────┐
│   UI React   │───────────────▶│ BFF Gateway  │
└──────────────┘                 └──────┬───────┘
       ▲                                │
       │ SSE events                     │ HTTP
       │                                ▼
┌──────┴───────┐  Kafka Events  ┌──────────────┐
│    Kafka     │◀───────────────│ Orchestrator │
│ graph.events │                └──────┬───────┘
│ logs.recon   │                       │
└──────────────┘                       │ HTTP
       │                               ▼
       │                        ┌──────────────┐
       │                        │ Graph Service│◀─── SQLite DB
       │                        └──────────────┘
       │
       └────────────────────────▶ BFF (consumes)
```

### 2.4 Source of Truth

- **Graph-Service SQLite** : Données persistantes (nodes, edges)
- **In-memory cache** : Performance reads (sync at startup)
- **Kafka** : Event sourcing pour replay et SSE

### 2.5 Stateless vs Stateful

| Composant | Type | Raison |
|-----------|------|--------|
| BFF Gateway | Stateless | Proxy GraphQL, peut scale horizontalement |
| Recon Orchestrator | Stateful | Mission state en mémoire (peut être externalisé) |
| Graph Service | Stateful | SQLite database |
| Kafka | Stateful | Event log persistant |
| Redis | Stateful | Cache pour planner |

### 2.6 Dépendances externes

| Dépendance | Usage | Installation |
|------------|-------|--------------|
| **Docker** | Exécution containers tools | Required |
| **Subfinder** | Subdomain enumeration | Docker image ou binaire |
| **HTTPX** | HTTP probing | Docker image ou binaire |
| **Nuclei** | Vulnerability scanning | Docker image |
| **FFUF** | Fuzzing | Docker image |
| **Ollama** | LLM local | Optionnel (fallback OpenAI) |
| **Kafka** | Event streaming | Docker compose |
| **PostgreSQL** | (Futur) graph storage | Docker compose |

### 2.7 Chemin d'un event

```
1. Tool exécuté (subfinder)
2. Result parsed par Agent CrewAI
3. GraphClient.add_subdomain() appelé
4. → HTTP POST vers graph-service /api/v1/nodes
5. → graph-service publie sur Kafka topic "graph.events"
6. → BFF Gateway consomme Kafka
7. → BFF envoie SSE à l'UI
8. → UI React met à jour le graphe visuel
```

### 2.8 Déduplication / Idempotence

```python
# Dans graph-service/main.py
def generate_edge_id(from_node: str, to_node: str, relation: str, mission_id: str) -> str:
    """ID déterministe pour idempotent upserts"""
    raw = f"{mission_id}:{from_node}:{to_node}:{relation}"
    return f"edge-{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

# Dans bff-gateway/main.py
def is_event_duplicate(run_id: str, event_id: str) -> bool:
    """Dedup par event_id avec LRU eviction"""
    if event_id in seen_event_ids_set[run_id]:
        return True  # Duplicate
    seen_event_ids_set[run_id].add(event_id)
    return False
```

### 2.9 Parsing normalisé

```python
# Dans graph_client.py
def parse_crew_result(result: Any) -> List[str]:
    """
    Parse CrewAI result vers items normalisés:
    1. Try JSON array extraction via regex
    2. Extract domain patterns
    3. Extract path patterns
    4. Deduplicate
    """
```

### 2.10 Points de couplage fragiles

| Point | Risque | Mitigation |
|-------|--------|------------|
| Kafka disponibilité | Events perdus | Retry + ring buffer |
| LLM latence | Timeouts | Fallback local Ollama |
| Graph-service single instance | SPOF | Future: clustering |
| Docker socket access | Sécurité | Container isolation |

---

## 3) Orchestrateur : Responsabilités & Algorithme

### 3.1 Entrée de l'orchestrateur

**Fichier principal** : `services/recon-orchestrator/main.py`

```python
@app.post("/api/v1/missions")
async def create_mission(request: MissionCreateRequest):
    """Point d'entrée pour lancer une mission"""
    mission = Mission(
        id=str(uuid.uuid4()),
        target_domain=request.target_domain,
        mode=request.mode,
        status="PENDING"
    )
    # Lance run_mission en background
    asyncio.create_task(run_mission(mission))
```

### 3.2 Structure d'un objet Mission

```python
class Mission(BaseModel):
    id: str                          # UUID
    target_domain: str               # "example.com"
    mode: str                        # "stealth" | "balanced" | "aggressive"
    status: str                      # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    current_phase: Optional[str]     # "OSINT" | "ACTIVE_RECON" | ...
    created_at: datetime
    updated_at: datetime
    progress: dict = {
        "phases_completed": 0,
        "phases_total": 6,
        "current_phase_progress": 0.0,
        "subdomains_found": 0,
        "endpoints_found": 0,
        "hypotheses_generated": 0
    }
    metrics: dict = {
        "phase_durations": {},
        "tool_calls": 0,
        "llm_calls": 0,
        "tokens_used": 0
    }
```

### 3.3 Ordre des phases

**Séquentiel strict avec conditions** :

```
Phase 1: OSINT (Passive)
    ├─ Subfinder enumeration
    ├─ Intelligence analysis
    ├─ DNS resolution
    └─ ASN mapping

Phase 2: ACTIVE_RECON (si endpoints trouvés)
    ├─ HTTP fingerprinting
    ├─ JS mining
    └─ Endpoint discovery

Phase 3: ENDPOINT_INTEL
    ├─ Categorization
    ├─ Risk scoring
    └─ Hypothesis generation

Phase 4: VERIFICATION (si mode != STEALTH)
    ├─ VulnTriage
    ├─ StackPolicy
    └─ EvidenceCurator

Phase 5: REPORTING
    └─ Attack paths + exports
```

### 3.4 Phases parallélisables

| Phase | Parallélisme |
|-------|--------------|
| DNS + ASN | Peuvent tourner en parallèle après OSINT |
| HTTP probing multiple hosts | Concurrent via semaphore |
| JS mining multiple URLs | Concurrent avec rate limit |
| Nuclei checks | Parallel per template |

### 3.5 Modèle de concurrence

```python
# asyncio + ThreadPoolExecutor pour I/O bound
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

async def run_tool_async(tool, args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, tool._run, *args)

# Semaphore pour rate limiting
semaphore = asyncio.Semaphore(config["max_concurrent"])
async with semaphore:
    result = await run_tool_async(httpx_tool, subdomains)
```

### 3.6 Comment l'orchestrateur lance un outil

```python
# Option 1: Binaire local
subprocess.run(["subfinder", "-d", domain], timeout=60)

# Option 2: Docker container
subprocess.run(["docker", "run", "--rm", "projectdiscovery/subfinder", "-d", domain])

# Option 3: Service HTTP (osint-runner)
async with httpx.AsyncClient() as client:
    response = await client.post("http://osint-runner:8002/api/v1/subfinder", json={"domain": domain})
```

### 3.7 Gestion des timeouts

```python
# Timeout par tool
class SubfinderTool:
    def _run(self, domain: str, timeout: int = 60):
        try:
            proc = subprocess.run(cmd, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"error": "timeout", "domain": domain}

# Timeout par phase (dans orchestrator)
async def run_phase_with_timeout(phase_func, phase_timeout=600):
    try:
        return await asyncio.wait_for(phase_func(), timeout=phase_timeout)
    except asyncio.TimeoutError:
        emit_error(mission_id, ErrorCode.TOOL_TIMEOUT, f"Phase timeout: {phase_timeout}s")

# Timeout global mission
mission_timeout = config.get("mission_timeout", 3600)
```

### 3.8 Gestion des retries

```python
# Retry avec backoff exponentiel
async def retry_with_backoff(func, max_retries=3, base_delay=1):
    for attempt in range(max_retries):
        try:
            return await func()
        except RetryableError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(delay)
```

### 3.9 Erreurs partielles

```python
# Mission continue malgré échec d'un tool
try:
    subfinder_result = await run_subfinder(domain)
except ToolError as e:
    emit_error(mission_id, ErrorCode.TOOL_EXECUTION_FAILED, str(e))
    subfinder_result = {"subdomains": [], "error": str(e)}  # Continue avec liste vide

# Phase échoue mais mission continue
phase_results[phase] = {
    "status": "partial",
    "error": str(e),
    "partial_data": collected_data
}
```

### 3.10 Statuts de mission et transitions

```
PENDING ─────┬─────▶ RUNNING ─────┬─────▶ COMPLETED
             │                    │
             │                    └─────▶ FAILED
             │
             └─────▶ CANCELLED

Transitions valides:
- PENDING → RUNNING (mission démarre)
- RUNNING → COMPLETED (toutes phases OK)
- RUNNING → FAILED (erreur fatale)
- PENDING|RUNNING → CANCELLED (user cancel)
```

### 3.11 Audit trail

```python
# Dans events.py
def emit_agent_started(mission_id, agent_id, task_description, phase):
    """Persiste AGENT_RUN node dans graph + Kafka event"""
    run_id = f"agent-{agent_id}-{timestamp}"
    _create_workflow_node_sync(mission_id, "AGENT_RUN", run_id, {
        "agent_id": agent_id,
        "task": task_description,
        "phase": phase,
        "start_time": iso_timestamp,
        "status": "running"
    })

def emit_tool_called(mission_id, tool_name, agent_id, input_summary):
    """Persiste TOOL_CALL node"""
    _create_workflow_node_sync(mission_id, "TOOL_CALL", call_id, {
        "tool_name": tool_name,
        "args": {"input": input_summary[:200]},
        "status": "running"
    })
```

### 3.12 Planner (next actions)

```python
# Dans agent_factory.py
def build_planner(target_domain, tools):
    return Agent(
        role="Reconnaissance Planner Brain (Code Name: Overwatch)",
        goal=f"Select the most profitable attack paths from the AssetGraph of {target_domain}",
        backstory="You only reason on the validated Graph provided by your field agents."
    )

# Output du planner
{
    "attack_paths": [
        {
            "target": "dev-api.example.com",
            "score": 85,
            "reason": "Exposed dev API with auth bypass potential",
            "next_actions": ["nuclei_scan", "ffuf_api_fuzz"]
        }
    ]
}
```

### 3.13 UI temps réel

- **SSE (Server-Sent Events)** : `/api/v1/sse/events/{run_id}`
- **WebSocket** : `ws://graph-service:8001/ws/graph/{mission_id}`
- **GraphQL Subscriptions** : `subscription { graphEvents(runId: "...") }`

### 3.14 Protection explosion combinatoire

```yaml
# Dans budget.yaml
limits:
  max_subdomains_per_phase: 500
  max_endpoints_per_service: 1000
  max_hypotheses_per_endpoint: 3
  max_graph_nodes: 10000

# Dans orchestrator
if len(subdomains) > config["max_subdomains_per_phase"]:
    subdomains = prioritize_and_limit(subdomains, limit=500)
    emit_log(mission_id, "WARNING", f"Subdomains limited to {len(subdomains)}")
```

---

## 4) Agents CrewAI : Rôles, Contrats, Mémoire

### 4.1 Liste des agents

| Agent ID | Nom de Code | Responsabilité | Input | Output |
|----------|-------------|----------------|-------|--------|
| `pathfinder` | Pathfinder | Subdomain enumeration | domain | JSON array of subdomains |
| `intelligence_analyst` | Watchtower | Analysis & prioritization | subdomains | JSON with tags, priority |
| `dns_analyst` | - | DNS resolution | subdomains | DNS records |
| `asn_analyst` | - | ASN/IP mapping | IPs | ASN info |
| `tech_fingerprinter` | StackTrace | HTTP fingerprinting | high-priority subdomains | HTTP data + tech |
| `js_miner` | DeepScript | JS endpoint extraction | URLs | endpoints, secrets |
| `endpoint_analyst` | All-Seeing Eye | Crawl + wayback | services | endpoints |
| `endpoint_intel` | RiskAware | Risk scoring | endpoints | enriched endpoints |
| `planner` | Overwatch | Attack planning | graph | attack paths |
| `vuln_triage` | Triage | Vuln prioritization | vulns | ranked targets |
| `stack_policy` | StackMap | Tech → check mapping | targets | module assignments |
| `evidence_curator` | Curator | Evidence validation | check results | confirmed/rejected |

### 4.2 Contract JSON strict

```python
# Dans task_factory.py
expected_output="""STRICT JSON array:
[
  {
    "subdomain": "api-dev.domain.com",
    "tag": "DEV_API",
    "priority": 9,
    "reason": "Exposed development API",
    "category": "APP_BACKEND",
    "next_action": "nuclei_scan"
  }
]"""
```

**Champs obligatoires par agent** :
- Pathfinder: `subdomain: str`
- Watchtower: `subdomain, tag, priority, reason`
- Endpoint Intel: `endpoint_id, category, risk_score, hypotheses[]`

### 4.3 Comment un agent consomme le contexte

```python
# CrewAI Task avec context
def build_analysis_task(watchtower, target_domain, enumeration_task):
    return Task(
        description=f"Analyze enumeration results for {target_domain}...",
        agent=watchtower,
        context=[enumeration_task],  # Reçoit output de la tâche précédente
        expected_output="STRICT JSON array..."
    )
```

### 4.4 Agents "raisonnement" vs "tool runner"

| Type | Agents |
|------|--------|
| **Tool Runner** | pathfinder (subfinder), tech_fingerprinter (httpx), js_miner |
| **Raisonnement** | watchtower, endpoint_intel, planner, evidence_curator |
| **Hybrid** | endpoint_analyst (crawl tool + analysis) |

### 4.5 Mémoire

- **Pas de mémoire persistante inter-mission** actuellement
- **Context intra-mission** via CrewAI Task context
- **Graph comme mémoire externe** : tous les findings persistent dans graph-service

### 4.6 Anti-hallucination

```python
# Constraints dans backstory
backstory="""
CRITICAL CONSTRAINTS:
1. You MUST NOT invent new endpoints or domains.
2. You ONLY enrich the endpoints you are given.
3. You stay strictly within the target domain scope.
4. Your output MUST be valid JSON only, no preamble.
"""

# Validation post-output
def validate_agent_output(output, target_domain):
    for item in parse_json(output):
        if not is_in_scope(item.get("subdomain"), target_domain):
            raise HallucinationError(f"Out of scope: {item}")
```

### 4.7 Exemple Subdomain Agent output

```json
{
  "domain": "example.com",
  "count": 15,
  "subdomains": [
    "api.example.com",
    "dev.example.com",
    "staging.example.com",
    "admin.example.com"
  ],
  "options": {
    "recursive": false,
    "all_sources": true,
    "smart_filter": false
  }
}
```

### 4.8 Exemple Web Discovery Agent fusion

```
Input: Fingerprint results avec URLs

Process:
1. Crawl HTML de chaque URL → liens, forms
2. Parse robots.txt → disallowed paths
3. Query Wayback Machine → historical URLs
4. JS mining → endpoints in code

Output:
{
  "service_url": "https://api.example.com",
  "endpoints": [
    {"path": "/api/v1/users", "source": "crawl"},
    {"path": "/admin/dashboard", "source": "robots"},
    {"path": "/api/internal/debug", "source": "wayback"},
    {"path": "/graphql", "source": "js"}
  ]
}
```

### 4.9 Gestion des conflits

- **Dedup par ID** : Nodes avec même ID = upsert (merge properties)
- **Confidence score** : Si conflit, garder la source avec meilleur score
- **Audit** : Track `discovered_by` edge pour traçabilité

### 4.10 Scoring / Prioritization

```python
# Categories et leurs poids
CATEGORY_WEIGHTS = {
    "ADMIN": 20,
    "AUTH": 15,
    "API": 10,
    "LEGACY": 10,
    "PUBLIC": 0,
    "STATIC": -10,
    "HEALTHCHECK": -20
}

# Priority basée sur patterns
HIGH_PRIORITY_KEYWORDS = ['admin', 'api', 'dev', 'test', 'staging', 'internal', 'vpn', 'auth', 'login']
```

### 4.11 Prompts system critiques

```python
# Pathfinder - Anti-hallucination
"""
CRITICAL:
- If no subdomains found, return [].
- DO NOT INVENT subdomains.
- Return ONLY the JSON array from the tool.
"""

# Endpoint Intel - Scope restriction
"""
CRITICAL CONSTRAINTS:
1. You MUST NOT invent new endpoints or domains.
2. You ONLY enrich the endpoints you are given.
3. Maximum 3 hypotheses per endpoint.
4. Scores must be: likelihood 0-10, impact 0-10, risk 0-100.
"""
```

### 4.12 Évaluation qualité outputs

```python
# Tests unitaires pour parsers
def test_parse_subfinder_output():
    result = parse_crew_result(mock_subfinder_output)
    assert all(is_valid_domain(d) for d in result)
    assert len(result) == expected_count

# Integration tests
def test_pathfinder_agent_no_hallucination():
    result = run_pathfinder("example.com")
    for subdomain in result["subdomains"]:
        assert subdomain.endswith("example.com")
```

---

## 5) Pipeline Recon par Phase

### 5.1 OSINT Passif

**Sources utilisées** :
- Subfinder (agrégation multi-sources: crt.sh, SecurityTrails, etc.)
- Certificate Transparency logs
- DNS passif (historique)
- (Future) WHOIS, Shodan

**Outputs seed** :
```json
{
  "subdomains": ["api.example.com", "dev.example.com"],
  "dns_records": [{"type": "A", "value": "1.2.3.4"}],
  "asn_info": {"asn": "AS12345", "org": "Example Inc"}
}
```

**KPI** : subdomains_found, dns_records, coverage_sources

### 5.2 Subdomains & DNS

**Stratégies** :
1. Agrégation multi-sources (Subfinder `-all`)
2. DNS brute (optionnel en mode AGGRESSIVE)
3. Permutations (dev-, staging-, api-)

**Wordlists** : Montées en volume Docker depuis `/data/wordlists/`

**Résolution DNS** :
```python
resolvers = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
retry_count = 3
cache_ttl = 300
```

**Marquage statut** : `alive` (résout), `dead` (NXDOMAIN), `flaky` (timeout intermittent)

### 5.3 Network & Port Scanning

**Autorisations par mode** :
| Mode | Ports | Scans |
|------|-------|-------|
| STEALTH | 80, 443 only | TCP connect |
| BALANCED | Top 100 | TCP SYN |
| AGGRESSIVE | Top 1000 | Full scan |

**Parsing** :
```python
# httpx JSON output → Service model
{
    "host": "api.example.com",
    "url": "https://api.example.com",
    "status_code": 200,
    "technologies": ["nginx", "PHP"],
    "ip": "1.2.3.4"
}
```

### 5.4 Web Content Discovery

**HTTP Probe** : httpx avec `-sc -title -tech-detect -ip`

**Crawl rules** :
- Scope: même domaine uniquement
- Depth: max 3 levels
- Respect robots.txt en mode STEALTH
- Types: HTML, JS, JSON uniquement

**Brute dirs** :
- Rate limit: 5 req/s
- Stop conditions: 50 consecutive 404
- Max time: 300s par service

**Dedup** : Normalisation URL (trailing slash, query sort)

### 5.5 JavaScript & API Analysis

**Collection JS** :
1. Crawl HTML → `<script src="...">`
2. HTTP response → inline scripts
3. Asset lists → *.js files

**Extraction endpoints** :
```python
patterns = [
    r'["\']/(api|v[0-9]+)/[a-zA-Z0-9/_-]+["\']',  # API paths
    r'fetch\(["\']([^"\']+)["\']',                  # fetch() calls
    r'axios\.(get|post)\(["\']([^"\']+)',          # axios calls
]
```

**Secrets detection** :
```python
SECRET_PATTERNS = {
    "aws_key": r'AKIA[0-9A-Z]{16}',
    "api_key": r'api[_-]?key["\']?\s*[:=]\s*["\']([^"\']+)',
    "jwt": r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',
}
```

### 5.6 Credential Leak Analysis

**Dataset** : Index local de breaches (si disponible)

**Recherche** :
```python
# SQLite FTS ou grep
def search_leaks(domain: str, emails: List[str]):
    query = f"SELECT * FROM leaks WHERE domain LIKE '%{domain}%'"
```

**Sensibilité** : Hash passwords, masquer emails partiellement

### 5.7 Cloud Asset Discovery

**Heuristiques DNS** :
```python
CLOUD_PATTERNS = {
    "AWS": [".s3.amazonaws.com", ".cloudfront.net", ".elb.amazonaws.com"],
    "Azure": [".blob.core.windows.net", ".azurewebsites.net"],
    "GCP": [".storage.googleapis.com", ".appspot.com"],
}
```

**Bucket patterns** : `{company}`, `{company}-prod`, `{company}-backup`

### 5.8 Misconfig & Vuln Checks

**Checks "safe"** :
- Security headers analysis (GET only)
- Server info disclosure
- Config file exposure (.env, .git)
- Default credentials check (known defaults)

**Templates Nuclei** :
```bash
# Mode STEALTH
nuclei -t exposures/ -severity info,low

# Mode AGGRESSIVE
nuclei -t cves/ -t vulnerabilities/ -severity all
```

---

## 6) Tooling & Containerisation

### 6.1 Tools container vs local

| Tool | Exécution | Raison |
|------|-----------|--------|
| Subfinder | Docker | Isolation, pas de dépendances |
| HTTPX | Docker ou binaire | Performance |
| Nuclei | Docker | Templates isolés |
| FFUF | Docker | Wordlists en volume |
| Python scripts | Local | Rapide, pas d'overhead |

### 6.2 docker-compose.yml structure

```yaml
services:
  recon-orchestrator:
    build: ./services/recon-orchestrator
    ports: ["8000:8000"]
    environment:
      - LLM_PROVIDER=openai
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on: [graph-service, kafka]

  graph-service:
    build: ./services/graph-service
    ports: ["8001:8001"]
    volumes:
      - ./data:/data

  scanner-proxy:
    build: ./services/scanner-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data/wordlists:/wordlists:ro
```

### 6.3 Passage de paramètres

```python
# Via arguments CLI
cmd = ["subfinder", "-d", domain, "-timeout", str(timeout)]

# Via stdin (Docker)
proc = subprocess.run(cmd, input=targets_list, capture_output=True)

# Via fichier temporaire
with tempfile.NamedTemporaryFile() as f:
    f.write("\n".join(subdomains))
    cmd = ["httpx", "-l", f.name]
```

### 6.4 Convention paths output

```
/output/
└── {mission_id}/
    ├── subfinder_raw.json
    ├── httpx_results.json
    ├── nuclei_findings.json
    ├── asset_graph.json
    └── summary.md

/data/
├── wordlists/
│   ├── subdomains.txt
│   ├── directories.txt
│   └── parameters.txt
└── templates/
    └── nuclei/
```

### 6.5 Limites Docker

```yaml
services:
  nuclei-runner:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### 6.6 Cleanup

```python
# Après mission
async def cleanup_mission(mission_id: str):
    # Remove temp containers
    subprocess.run(["docker", "rm", "-f", f"scan-{mission_id}"])
    # Clean temp files
    shutil.rmtree(f"/tmp/mission-{mission_id}", ignore_errors=True)
```

---

## 7) Data Model & Asset Graph

### 7.1 Types de noeuds

```python
class NodeType(str, Enum):
    # Asset nodes
    DOMAIN = "DOMAIN"
    SUBDOMAIN = "SUBDOMAIN"
    HTTP_SERVICE = "HTTP_SERVICE"
    ENDPOINT = "ENDPOINT"
    PARAMETER = "PARAMETER"
    HYPOTHESIS = "HYPOTHESIS"
    VULNERABILITY = "VULNERABILITY"
    ATTACK_PATH = "ATTACK_PATH"
    IP_ADDRESS = "IP_ADDRESS"
    DNS_RECORD = "DNS_RECORD"
    ASN = "ASN"
    ORG = "ORG"
    # Workflow nodes
    AGENT_RUN = "AGENT_RUN"
    TOOL_CALL = "TOOL_CALL"
    LLM_REASONING = "LLM_REASONING"
```

### 7.2 Types de relations

```python
class EdgeType(str, Enum):
    # Discovery
    HAS_SUBDOMAIN = "HAS_SUBDOMAIN"       # domain → subdomain
    RESOLVES_TO = "RESOLVES_TO"           # subdomain → IP
    EXPOSES_HTTP = "EXPOSES_HTTP"         # subdomain → HTTP_SERVICE
    EXPOSES_ENDPOINT = "EXPOSES_ENDPOINT" # HTTP_SERVICE → ENDPOINT
    HAS_PARAMETER = "HAS_PARAMETER"       # ENDPOINT → PARAMETER
    # Analysis
    HAS_HYPOTHESIS = "HAS_HYPOTHESIS"     # ENDPOINT → HYPOTHESIS
    HAS_VULNERABILITY = "HAS_VULNERABILITY"
    # Workflow
    TRIGGERS = "TRIGGERS"                 # agent → agent
    USES_TOOL = "USES_TOOL"               # agent → tool_call
    PRODUCES = "PRODUCES"                 # tool_call → asset_node
```

### 7.3 Asset ID stable

```python
def generate_node_id(node_type: str, identifier: str) -> str:
    """ID normalisé et déterministe"""
    normalized = identifier.lower().strip()
    return f"{node_type.lower()}:{normalized}"

# Exemples:
# "subdomain:api.example.com"
# "http_service:https://api.example.com"
# "endpoint:https://api.example.com/api/v1/users"
```

### 7.4 Provenance tracking

```python
# Chaque node a:
properties = {
    "discovered_by": "pathfinder",      # Agent qui l'a trouvé
    "discovered_at": "2024-01-15T...",  # Timestamp
    "source": "subfinder",              # Tool utilisé
    "phase": "OSINT",                   # Phase de découverte
    "confidence": 0.95                  # Score de confiance
}

# Edges de provenance
PRODUCES: tool_call → asset_node
```

### 7.5 Stockage des preuves

```python
# Evidence attachée à VULNERABILITY node
evidence = {
    "hash": "sha256:abc123...",
    "type": "http_response",
    "content_redacted": "Status: 200\nX-Debug: [REDACTED]",
    "timestamp": "2024-01-15T...",
    "tool": "nuclei",
    "template_id": "security-headers-missing"
}
```

### 7.6 Format des champs enrichis

```python
endpoint_properties = {
    "path": "/api/v1/users",
    "method": "GET",
    "category": "API",              # API, ADMIN, AUTH, LEGACY, etc.
    "risk_score": 75,               # 0-100
    "likelihood_score": 8,          # 0-10
    "impact_score": 9,              # 0-10
    "auth_required": False,
    "tech_stack_hint": "Node.js",
    "tags": ["rest", "user-data"],
    "behaviors": ["pagination", "filtering"]
}
```

---

## 8) Eventing & Temps Réel

### 8.1 Mécanisme temps réel

**SSE (Server-Sent Events)** choisi car :
- Unidirectionnel (server → client) suffisant
- Reconnexion automatique native
- Support Last-Event-ID pour replay
- Plus simple que WebSocket pour ce use case

Endpoint : `GET /api/v1/sse/events/{run_id}`

### 8.2 Event Envelope v2

```json
{
  "schema_version": "v2",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "NODE_ADDED",
  "ts": "2024-01-15T10:30:00.000Z",
  "mission_id": "mission-xyz",
  "phase": "OSINT",
  "trace_id": "trc_abc123def456",
  "span_id": "spn_789xyz",
  "task_id": "agent-pathfinder-1234",
  "tool_call_id": "tool-subfinder-5678",
  "producer": "recon-orchestrator",
  "payload": {
    "node": {
      "id": "subdomain:api.example.com",
      "type": "SUBDOMAIN",
      "properties": {"name": "api.example.com"}
    }
  }
}
```

### 8.3 Types d'events

| Event Type | Description |
|------------|-------------|
| `MISSION_STARTED` | Mission lancée |
| `PHASE_STARTED` | Phase démarrée |
| `PHASE_COMPLETED` | Phase terminée |
| `agent_started` | Agent CrewAI démarré |
| `agent_finished` | Agent terminé |
| `tool_called` | Tool invoqué |
| `tool_finished` | Tool terminé |
| `NODE_ADDED` | Node créé dans graph |
| `NODE_UPDATED` | Node modifié |
| `EDGE_ADDED` | Relation créée |
| `ERROR` | Erreur |
| `MISSION_COMPLETED` | Mission terminée |

### 8.4 Ordre garanti

- **Par mission** : Ring buffer préserve l'ordre FIFO
- **Global** : Pas de garantie inter-missions
- **Reconnexion** : Last-Event-ID pour replay dans l'ordre

### 8.5 Reconnexion UI

```javascript
// Dans l'UI React
const eventSource = new EventSource(`/api/v1/sse/events/${missionId}`);

eventSource.onopen = () => console.log("SSE connected");

eventSource.onerror = () => {
  // Auto-reconnect avec Last-Event-ID header
  // Le navigateur gère automatiquement
};

// Replay des events manqués via ring buffer côté serveur
```

### 8.6 Anti-doublon UI

```python
# BFF Gateway - dedup par event_id
def is_event_duplicate(run_id: str, event_id: str) -> bool:
    if event_id in seen_event_ids_set[run_id]:
        return True
    seen_event_ids_set[run_id].add(event_id)
    return False
```

### 8.7 Volumétrie limitée

- **Ring buffer** : 1000 events max par mission
- **Batching** : `NODES_BATCH` pour grouper plusieurs nodes
- **Throttling** : Keepalive toutes les 15s max

### 8.8 Exemples payload

**Tool progress** :
```json
{
  "event_type": "tool_called",
  "payload": {
    "call_id": "tool-subfinder-1705312200000",
    "tool_name": "subfinder_enum",
    "agent_id": "pathfinder",
    "arguments": {"domain": "example.com"},
    "start_time": "2024-01-15T10:30:00.000Z"
  }
}
```

**Graph upsert** :
```json
{
  "event_type": "NODE_ADDED",
  "payload": {
    "node": {
      "id": "subdomain:api.example.com",
      "type": "SUBDOMAIN",
      "properties": {
        "name": "api.example.com",
        "source": "subfinder",
        "discovered_by": "pathfinder"
      }
    }
  }
}
```

### 8.9 Persistance events

- **Kafka** : `graph.events` et `logs.recon` topics
- **SQLite** : Nodes/edges persistés dans graph-service
- **Ring buffer** : In-memory pour replay rapide (1000 events)

---

## 9) Robustesse : Erreurs, Retries, Cohérence

### 9.1 Tool failed vs Mission failed

| Niveau | Impact | Exemple |
|--------|--------|---------|
| Tool failed | Mission continue | Subfinder timeout → utilise résultats partiels |
| Phase failed | Mission continue (dégradée) | OSINT échoue → skip active recon |
| Mission failed | Mission arrêtée | Erreur critique graph-service down |

### 9.2 Échecs récupérables vs fatals

**Récupérables (retry)** :
- Network timeout
- Rate limit (429)
- Temporary service unavailable

**Fatals (no retry)** :
- Invalid target domain
- Graph-service database corruption
- LLM API key invalid

### 9.3 Protection contre faux FAILED

```python
# make_json_safe() dans events.py
def make_json_safe(obj: Any) -> Any:
    """
    Convertit récursivement en JSON-serializable:
    - bytes → string
    - sets → lists
    - datetime → isoformat
    - circular refs → "[circular reference]"
    """
```

### 9.4 Progress JSON-safe

```python
# Toujours sérialiser progress avant stockage
progress = make_json_safe({
    "phases_completed": 3,
    "current_phase_progress": 0.75,
    "stats": {"subdomains": 42}
})
```

### 9.5 Rollback incohérence

```python
# Atomic batch upsert dans graph-service
@app.post("/api/v1/graph/batchUpsert")
async def batch_upsert_graph(request):
    # Prepare data (validate)
    prepared_nodes = validate_nodes(request.nodes)
    prepared_edges = validate_edges(request.edges)

    # DB commit (atomic)
    try:
        await database.batch_upsert(prepared_nodes, prepared_edges)
    except Exception as e:
        # Rollback - don't update in-memory
        raise HTTPException(500, f"Batch failed: {e}")

    # Only update memory after successful DB commit
    for node in prepared_nodes:
        nodes_store[node["id"]] = node
```

### 9.6 Timeouts silencieux

```python
async def run_tool_with_watchdog(tool, args, timeout=60):
    """Détecte tools hung"""
    try:
        result = await asyncio.wait_for(
            run_tool_async(tool, args),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        emit_error(mission_id, ErrorCode.TOOL_TIMEOUT,
                   f"Tool {tool.name} hung for {timeout}s")
        return {"error": "timeout", "partial": True}
```

### 9.7 Outputs vides vs pas de résultats

```python
# Dans SubfinderTool
if len(subdomains) == 0:
    result["status"] = "no_results"
    result["message"] = "Subfinder executed but found no matching subdomains."
# vs
if proc.returncode != 0:
    result["error"] = "subfinder_error"
```

### 9.8 Stratégie alerting

```python
# Error taxonomy dans events.py
class ErrorCode:
    NETWORK_TIMEOUT = "E101"
    TOOL_NOT_FOUND = "E201"
    SERVICE_UNAVAILABLE = "E301"
    DATA_PARSE_ERROR = "E401"
    INTERNAL_ERROR = "E501"

def emit_error(mission_id, error_code, message, stage, retryable, recoverable):
    """Structured error with correlation"""
    emit_event(TOPIC_LOGS, "ERROR", mission_id, {
        "error_code": error_code,
        "message": message,
        "stage": stage,
        "retryable": retryable,
        "recoverable": recoverable,
        "trace_id": get_trace_context()["trace_id"]
    })
```

---

## 10) Performance & Scalabilité

### 10.1 Goulots d'étranglement

| Ressource | Impact | Mitigation |
|-----------|--------|------------|
| **Réseau** | DNS queries, HTTP probes | Caching, rate limiting |
| **LLM API** | Latence 1-5s par appel | Batch prompts, local Ollama |
| **I/O Disque** | Wordlists, outputs | SSD, volumes tmpfs |
| **CPU** | JS parsing, regex | Multi-threading |

### 10.2 Paramètres de charge

```yaml
# budget.yaml
performance:
  max_concurrent_requests: 10
  rate_limit_per_second: 5
  dns_threads: 20
  httpx_threads: 10
  wordlist_chunk_size: 1000
```

### 10.3 Caches

| Cache | TTL | Implémentation |
|-------|-----|----------------|
| DNS cache | 300s | In-memory dict |
| URL dedup | Mission lifetime | Set() |
| Graph nodes | Permanent | In-memory + SQLite |
| LLM responses | Non cachés | - |

### 10.4 Volumétrie typique

| Métrique | Small Target | Medium | Large |
|----------|--------------|--------|-------|
| Subdomains | 10-50 | 100-500 | 1000+ |
| HTTP Services | 5-20 | 50-200 | 500+ |
| Endpoints | 50-200 | 500-2000 | 5000+ |
| Graph nodes | 100-500 | 1000-5000 | 10000+ |
| Mission duration | 5-15 min | 30-60 min | 2-4 hours |

### 10.5 Optimisations faites

- Chunking wordlists pour mémoire constante
- Streaming parsing (NDJSON)
- Batch graph upserts
- Connection pooling HTTP
- Async I/O everywhere

### 10.6 Multi-missions parallèles

```python
# Isolation par mission_id
# Chaque mission a son propre:
# - GraphClient instance
# - Event queues
# - Rate limiter

# Limite globale
MAX_CONCURRENT_MISSIONS = 5
mission_semaphore = asyncio.Semaphore(MAX_CONCURRENT_MISSIONS)
```

### 10.7 Points de contention

| Point | Contention | Solution |
|-------|-----------|----------|
| SQLite writes | Single writer | Future: PostgreSQL |
| Kafka partitions | Par mission_id key | Partition by mission |
| Docker socket | Sequential tool launch | Pool de containers |

---

## 11) Sécurité du Produit

### 11.1 Injection de commandes

```python
# Mauvais (vulnérable)
subprocess.run(f"subfinder -d {domain}", shell=True)

# Bon (safe)
subprocess.run(["subfinder", "-d", domain], shell=False)
```

### 11.2 Isolation exécution

```yaml
# Docker security
services:
  nuclei-runner:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    user: "1000:1000"
```

### 11.3 Protection API

```python
# Future: Auth middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = request.headers.get("Authorization")
    if not verify_token(token):
        raise HTTPException(401, "Unauthorized")
```

### 11.4 Secrets de config

```bash
# .env (pas commité)
OPENAI_API_KEY=sk-...
SHODAN_API_KEY=...

# Docker secrets (production)
docker secret create openai_key ./secrets/openai.txt
```

### 11.5 Secret redaction

```python
def redact_secret(value: str) -> str:
    """Masque les secrets dans les logs"""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"

# Avant log/stockage
secret_display = redact_secret(found_api_key)
```

### 11.6 Confidentialité résultats

- Exports JSON chiffrables
- Pas de logs vers services tiers
- Cleanup automatique après X jours

---

## 12) Qualité, Tests, Reproductibilité

### 12.1 Tests unitaires

```python
# tests/test_asset_graph.py
def test_add_subdomain():
    graph = AssetGraph("example.com")
    graph.add_subdomain("api.example.com", "subfinder")
    assert "subdomain:api.example.com" in graph.nodes

def test_scope_validation():
    graph = AssetGraph("example.com")
    assert graph.is_in_scope("api.example.com") == True
    assert graph.is_in_scope("evil.com") == False
```

### 12.2 Tests d'intégration

```python
# tests/test_mission_e2e.py
async def test_full_mission():
    # Mock external tools
    with patch("tools.subfinder_tool.SubfinderTool") as mock:
        mock.return_value = {"subdomains": ["api.example.com"]}

        mission = await create_mission("example.com", "stealth")
        await run_mission(mission)

        assert mission.status == "COMPLETED"
        assert len(mission.graph.get_nodes("SUBDOMAIN")) >= 1
```

### 12.3 Mocks tools

```python
# tests/mocks/subfinder_mock.py
class MockSubfinderTool:
    def _run(self, domain, **kwargs):
        return json.dumps({
            "domain": domain,
            "count": 2,
            "subdomains": [f"api.{domain}", f"www.{domain}"]
        })
```

### 12.4 Compatibilité versions

```yaml
# requirements.txt pinned
crewai==0.28.8
httpx==0.25.2
aiokafka==0.10.0

# Docker images tagged
projectdiscovery/subfinder:v2.6.3
projectdiscovery/httpx:v1.3.7
projectdiscovery/nuclei:v3.1.0
```

### 12.5 Métriques fiabilité

| Métrique | Target | Actuel |
|----------|--------|--------|
| Mission success rate | >95% | ~90% |
| Retry rate | <10% | ~5% |
| Mean mission time | <30min | ~20min |
| False positive rate | <20% | ~15% |

---

## 13) Matériel pour Slides

### 13.1 Diagrammes à produire

1. **C4 Context** : User → Gotham → Target + LLM + OSINT
2. **C4 Container** : UI, BFF, Orchestrator, Graph, Services
3. **Sequence Mission** : Create → OSINT → Active → Intel → Report
4. **Data Model** : Nodes types + Relations
5. **Event Flow** : Tool → Agent → Graph → Kafka → SSE → UI

### 13.2 Exemple mission run complet

```bash
# Input
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain":"example.com","mode":"aggressive"}'

# Response
{"id":"abc123","status":"PENDING"}

# Logs (streaming)
[10:30:00] MISSION_STARTED: example.com (aggressive)
[10:30:05] PHASE_STARTED: OSINT
[10:30:10] agent_started: pathfinder
[10:30:12] tool_called: subfinder_enum
[10:30:45] tool_finished: subfinder (15 subdomains)
[10:30:50] agent_finished: pathfinder
[10:31:00] agent_started: watchtower
...
[10:45:00] MISSION_COMPLETED
```

### 13.3 Captures UI suggérées

1. Dashboard missions list
2. Mission detail avec timeline
3. Graph visualization (nodes + edges)
4. Findings panel avec risk scores
5. Attack paths ranked

### 13.4 Extraits de code (10-20 lignes)

**Lancement tool + timeout** :
```python
async def run_tool_with_timeout(tool, args, timeout=60):
    emit_tool_called(mission_id, tool.name, agent_id, str(args)[:200])
    start = time.time()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, tool._run, *args),
            timeout=timeout
        )
        duration = time.time() - start
        emit_tool_result(mission_id, tool.name, len(parse_result(result)), duration)
        return result
    except asyncio.TimeoutError:
        emit_error(mission_id, ErrorCode.TOOL_TIMEOUT, f"{tool.name} timeout")
        return {"error": "timeout"}
```

**Upsert graph + event emit** :
```python
async def add_subdomain(self, subdomain: str, source: str) -> bool:
    node_id = f"subdomain:{subdomain}"
    response = await self.client.post(
        f"{GRAPH_SERVICE_URL}/api/v1/nodes",
        json={
            "id": node_id,
            "type": "SUBDOMAIN",
            "mission_id": self.mission_id,
            "properties": {"name": subdomain, "source": source}
        }
    )
    if response.status_code in (200, 201):
        emit_node_added(self.mission_id, "SUBDOMAIN", node_id, {"name": subdomain})
        return True
    return False
```

### 13.5 Schémas JSON

**Mission** :
```json
{
  "id": "uuid",
  "target_domain": "string",
  "mode": "stealth|balanced|aggressive",
  "status": "PENDING|RUNNING|COMPLETED|FAILED",
  "current_phase": "string",
  "created_at": "datetime",
  "progress": {"phases_completed": 0, "total": 6},
  "metrics": {"tool_calls": 0, "llm_calls": 0}
}
```

**EventEnvelope** :
```json
{
  "schema_version": "v2",
  "event_id": "uuid",
  "event_type": "string",
  "ts": "datetime",
  "mission_id": "string",
  "phase": "string",
  "trace_id": "string",
  "producer": "string",
  "payload": {}
}
```

### 13.6 Configs importantes

| Config | Fichier | Valeurs clés |
|--------|---------|--------------|
| LLM Provider | `.env` | `LLM_PROVIDER=openai`, `MODEL_NAME=gpt-4o-mini` |
| Agents | `config/agents.yaml` | Roles, goals, backstories |
| Tasks | `config/tasks.yaml` | Descriptions, expected outputs |
| Limits | `config/budget.yaml` | Timeouts, rate limits, max nodes |

### 13.7 Slide "Limitations connues"

| Limitation | Impact | Roadmap |
|------------|--------|---------|
| SQLite single-writer | Pas de scale horizontal | PostgreSQL migration |
| Pas d'auth UI | Mono-utilisateur | OAuth2/OIDC |
| LLM hallucinations | Faux positifs | Fine-tuning + validation |
| Nuclei payloads intrusifs | Risque détection | Template curation |

### 13.8 Success Stories (exemples)

**Story 1** : Découverte subdomain → service → endpoint critique
```
Subfinder → dev-api.example.com (tag: DEV)
HTTPX → HTTP 200, tech: Express.js
Crawl → /api/v1/debug endpoint exposé
→ Risk score: 85, Category: API, Hypothesis: INFO_DISCLOSURE
```

**Story 2** : JS mining révèle secret
```
DeepScript analyse main.js
→ AWS Access Key détectée (pattern AKIA...)
→ Alerte CRITICAL avec evidence hashée
```

**Story 3** : Attack path chaîné
```
Pathfinder: staging.example.com
StackTrace: Apache 2.4.29 (outdated)
Nuclei: CVE-2021-41773 (Path Traversal)
Planner: Attack path score 92
→ staging → path traversal → /etc/passwd
```

---

*Document généré le 2024-01-15 pour présentation technique Recon-Gotham*
