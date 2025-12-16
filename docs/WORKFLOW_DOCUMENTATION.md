# Recon Gotham - Documentation Workflow Detaillee

Ce document decrit en detail le workflow d'execution du systeme multi-agent Recon Gotham, basé sur l'analyse de la mission `tahiti-infos.com` en mode AGGRESSIVE.

---

## Table des Matieres

1. [Vue d'Ensemble](#vue-densemble)
2. [Architecture du Systeme](#architecture-du-systeme)
3. [Flux d'Execution Detaille](#flux-dexecution-detaille)
4. [Agents et leurs Roles](#agents-et-leurs-roles)
5. [Tools et leurs Interactions](#tools-et-leurs-interactions)
6. [Decisions de l'Orchestrateur](#decisions-de-lorchestrator)
7. [Structure des Donnees](#structure-des-donnees)
8. [Exemple Concret: Mission tahiti-infos.com](#exemple-concret)

---

## Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RECON GOTHAM WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  INPUT: Domain + Mode (stealth/aggressive)                                  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 1: PASSIVE RECON (CrewAI Sequential)                           │  │
│  │   Pathfinder → Watchtower → DNS Analyst → ASN Analyst                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ BYPASS: Direct Subfinder + Wayback Historical Scan                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ GATE CHECK: Verification du nombre de subdomains                     │  │
│  │   → Si 0: Apex Fallback (target_domain + www)                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 2: ACTIVE RECON (CrewAI Sequential)                            │  │
│  │   Tech Fingerprinter → JS Miner → Endpoint Analyst → Param Hunter    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 19: Universal Active Recon (HTTPX Direct)                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 21: Surgical Strikes                                           │  │
│  │   HTML Crawl + JS Mining + Nuclei/Ffuf (gated)                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 23A: Validation & Deep Page Analysis                           │  │
│  │ PHASE 23B: Endpoint Intelligence Enrichment                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ PHASE 25: Verification Pipeline                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                           ↓                                                 │
│  OUTPUT: AssetGraph JSON + Summary MD + Metrics JSON                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture du Systeme

### Composants Principaux

| Composant | Fichier | Role |
|-----------|---------|------|
| **Orchestrateur** | `main.py` | Coordonne toutes les phases, gere les erreurs et fallbacks |
| **AssetGraph** | `core/asset_graph.py` | Base de donnees centrale (nodes + edges) |
| **Planner** | `core/planner.py` | Analyse le graphe et suggere les actions offensives |
| **Heuristics** | `core/endpoint_heuristics.py` | Scoring et categorisation des endpoints |
| **Tools** | `tools/*.py` | Wrappers pour les outils externes (Subfinder, HTTPX, etc.) |
| **Pipelines** | `pipelines/*.py` | Modules de verification et reporting |

### Modele de Donnees (AssetGraph)

```
NODE TYPES:
├── SUBDOMAIN        (m.tahiti-infos.com)
├── HTTP_SERVICE     (http:https://www.tahiti-infos.com)
├── ENDPOINT         (endpoint:http:https://www.tahiti-infos.com/search)
├── PARAMETER        (param:endpoint:...:id)
├── VULNERABILITY    (vuln:CVE-2024-XXXX)
├── HYPOTHESIS       (hypothesis:endpoint:...:IDOR)
├── ATTACK_PATH      (attack_path:abc123)
├── IP_ADDRESS       (ip:192.168.1.1)
├── DNS_RECORD       (dns:MX:mail.example.com)
└── ASN              (asn:AS12345)

EDGE TYPES (Relations):
├── EXPOSES_HTTP           (SUBDOMAIN → HTTP_SERVICE)
├── EXPOSES_ENDPOINT       (HTTP_SERVICE → ENDPOINT)
├── HAS_PARAMETER          (ENDPOINT → PARAMETER)
├── HAS_HYPOTHESIS         (ENDPOINT → HYPOTHESIS)
├── RESOLVES_TO            (SUBDOMAIN → IP_ADDRESS)
├── BELONGS_TO             (IP_ADDRESS → ASN)
├── AFFECTS                (VULNERABILITY → NODE)
└── TARGETS                (ATTACK_PATH → SUBDOMAIN)
```

---

## Flux d'Execution Detaille

### PHASE 1: PASSIVE RECON (main.py:331-389)

**Objectif**: Decouvrir les sous-domaines et l'infrastructure sans interaction active.

```python
# Crew Configuration
passive_agents = [pathfinder, intelligence_analyst, dns_analyst, asn_analyst]
passive_tasks = [smart_enum, context_analysis, dns_enrich, asn_enrich]
passive_crew = Crew(agents=passive_agents, tasks=passive_tasks, process=Process.sequential)
```

#### Sequence d'Execution:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TASK 1: smart_enumeration_task                                              │
│ Agent: Pathfinder                                                           │
│ Tool: SubfinderTool                                                         │
│ Input: target_domain                                                        │
│ Output: JSON list of subdomains                                             │
│                                                                             │
│ Interaction Type:                                                           │
│   Agent → Tool._run(domain="tahiti-infos.com", all_sources=True)           │
│   Tool → Subprocess: docker run gotham/subfinder -d tahiti-infos.com -oJ   │
│   Tool → Agent: {"domain": "...", "count": 4, "subdomains": [...]}         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ TASK 2: context_analysis_task                                               │
│ Agent: Watchtower (Intelligence Analyst)                                    │
│ Tool: None (LLM reasoning)                                                  │
│ Input: Output from Task 1                                                   │
│ Output: Annotated subdomain list with priority/tag/category                 │
│                                                                             │
│ Interaction Type:                                                           │
│   Agent → LLM: Analyse les subdomains et assigne des priorites             │
│   LLM → Agent: [{"subdomain": "backup.tahiti-infos.com", "priority": 9}]   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ TASK 3: dns_enrichment_task                                                 │
│ Agent: DNS Analyst                                                          │
│ Tool: DnsResolverTool                                                       │
│ Input: List of subdomains                                                   │
│ Output: DNS records (A, AAAA, MX, TXT, etc.)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ TASK 4: asn_enrichment_task                                                 │
│ Agent: ASN Analyst                                                          │
│ Tool: ASNLookupTool                                                         │
│ Input: List of IPs (from DNS)                                              │
│ Output: ASN ownership info                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### BYPASS: Direct Subfinder (main.py:351-371)

**Pourquoi**: Les agents LLM peuvent mal parser le JSON. Le bypass garantit l'ingestion complete.

```python
# Direct tool call (bypasses LLM)
sf_raw = subfinder_tool._run(domain=target_domain, recursive=False, all_sources=True, timeout=60)
sf_data = json.loads(sf_raw)

for sub in sf_data.get("subdomains", []):
    if target_domain in sub:
        graph.ensure_subdomain(sub, tag="SUBFINDER_DIRECT")
```

**Resultat Mission tahiti-infos.com**:
```
- Subfinder direct: 4 subdomains found
  → m.tahiti-infos.com
  → www.tahiti-infos.com
  → backup.tahiti-infos.com
  → sports.tahiti-infos.com
```

### WAYBACK HISTORICAL SCAN (main.py:391-420)

**Objectif**: Decouvrir des endpoints historiques via Wayback Machine.

```python
subs = [n["id"] for n in graph.nodes if n["type"] == "SUBDOMAIN"]
subs.append(target_domain)  # Include apex

wb_res = wayback_tool._run(domains=subs)
for item in wb_data:
    full_url = item.get("path")
    if target_domain in urlparse(full_url).netloc:
        graph.add_endpoint(full_url, "GET", "WAYBACK", full_url, confidence=0.6)
```

### GATE CHECK (main.py:422-453)

**Decision Point**: L'orchestrateur verifie s'il y a assez de donnees pour continuer.

```python
sub_count = len([n for n in graph.nodes if n["type"] == "SUBDOMAIN"])

if sub_count == 0:
    # FALLBACK: Inject apex domain and www
    graph.ensure_subdomain(target_domain, tag="APEX_FALLBACK")
    graph.ensure_subdomain(f"www.{target_domain}", tag="APEX_FALLBACK")

    # Probe with HEAD requests
    for base in [f"https://{target_domain}", f"https://www.{target_domain}"]:
        resp = requests.head(base, timeout=5, verify=False)
        if resp.status_code < 500:
            graph.add_subdomain_with_http({...})
```

### PHASE 2: ACTIVE RECON (main.py:490-570)

**Objectif**: Fingerprinting technique, analyse JS, decouverte d'endpoints.

```python
# Context injection (passive results → active tasks)
passive_summary = context_analysis.output.raw
tech_task.description += f"\n\n[CONTEXT FROM PASSIVE PHASE]\n{passive_summary}"

active_agents = [tech_fingerprinter, js_miner, endpoint_analyst, param_hunter]
active_tasks = [tech_task, js_task, ep_task, param_task]
active_crew = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential)
```

#### Tech Fingerprinter Interaction:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Agent: Tech Fingerprinter (StackTrace)                                      │
│ Tool: HttpxTool                                                             │
│                                                                             │
│ CALL: httpx_probe(subdomains=["m.tahiti-infos.com", "www.tahiti-infos.com"])│
│                                                                             │
│ RESPONSE:                                                                   │
│ {                                                                           │
│   "results": [                                                              │
│     {                                                                       │
│       "host": "www.tahiti-infos.com",                                      │
│       "url": "https://www.tahiti-infos.com",                               │
│       "status_code": 200,                                                   │
│       "technologies": ["Cloudflare", "jQuery:1.8.3", "Google Analytics"],  │
│       "ip": "172.67.68.243",                                               │
│       "title": "TAHITI INFOS, les informations de Tahiti"                  │
│     }                                                                       │
│   ]                                                                         │
│ }                                                                           │
│                                                                             │
│ SCOPE CHECK (Orchestrateur):                                                │
│   if target_domain not in subdomain:                                        │
│       print("[!] Rejected hallucinated subdomain")                          │
│       continue  # Skip out-of-scope data                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### PHASE 19: Universal Active Recon (main.py:572-606)

**Objectif**: Normaliser la couverture HTTP sur tous les subdomains confirmes.

```python
targets = [n["id"] for n in graph.nodes if n["type"] == "SUBDOMAIN" and target_domain in n["id"]]
res_json = my_httpx_tool._run(subdomains=targets, timeout=12)

for res in results_list:
    host = res.get("host")
    if target_domain not in str(host):
        print(f"[!] Rejected out-of-scope Httpx result: {host}")
        continue

    graph.add_subdomain_with_http({
        "subdomain": host,
        "priority": 10,
        "tag": "ACTIVE",
        "http": {...}
    })
```

**Resultat tahiti-infos.com**:
```
HTTP Services Created:
├── http:https://backup.tahiti-infos.com  (200, Cloudflare/LiteSpeed)
├── http:https://m.tahiti-infos.com       (302, Cloudflare/HSTS)
├── http:https://www.tahiti-infos.com     (200, jQuery/Analytics)
└── http:https://sports.tahiti-infos.com  (523, Cloudflare)
```

### PHASE 21: Surgical Strikes (main.py:609-702)

**Objectif**: Decouverte d'endpoints ciblee + scans de vulnerabilites.

```python
# 1. HTML Crawl on all HTTP services
for base_url in scan_urls:
    links_json = html_tool._run(url=base_url)
    for link in links:
        if target_domain in link:
            graph.add_endpoint(link, "GET", "CRAWLER", base_url, 0.9)

# 2. Consult Planner for high-value targets
from recon_gotham.core.planner import find_top_paths
paths = find_top_paths({"nodes": graph.nodes, "edges": graph.edges})

# 3. Nuclei/Ffuf on top targets (gated by risk)
candidates = [f"https://{p['subdomain']}" for p in paths[:5]]
print(f"[!] Surgical Strike Targets: {candidates}")
# nuclei_tool._run(targets=candidates)
# ffuf_tool._run(url=candidates[0])
```

### PHASE 23A: Validation & Deep Analysis (main.py:703-782)

```python
# Step 1: Validate URLs
validator = EndpointValidator(timeout=10, max_workers=5)
for svc in http_services[:15]:
    result = validator.validate_url(url)
    if result["reachable"]:
        reachable_urls.append(url)

# Step 2: Deep Page Analysis
analyzer = PageAnalyzer(timeout=15)
for url in reachable_urls[:5]:
    analysis = analyzer.analyze_url(url)

    # Ingest discovered forms
    for form in analysis["analysis"].get("forms", []):
        graph.add_endpoint(form["action"], form.get("method", "POST"), "PAGE_ANALYZER", ...)

    # Ingest discovered API endpoints from JS
    for api in analysis["analysis"].get("api_endpoints", []):
        graph.add_endpoint(api["endpoint"], "GET", "PAGE_ANALYZER_JS", ...)
```

**Resultat tahiti-infos.com**:
```
Deep analysis found: 6 forms, 0 API endpoints
  → /search (GET) - m.tahiti-infos.com
  → /newsletter (POST) - m.tahiti-infos.com
  → /search (GET) - www.tahiti-infos.com
  → /newsletter (POST) - www.tahiti-infos.com
```

### PHASE 23B: Endpoint Intelligence Enrichment (main.py:784-941)

**Objectif**: Scoring de risque et generation d'hypotheses.

```python
from recon_gotham.core.endpoint_heuristics import enrich_endpoint

for node in endpoint_nodes:
    enrichment = enrich_endpoint(
        endpoint_id=node["id"],
        url=origin,
        path=path,
        method=method,
        source=source,
        extension=extension,
    )

    # Update graph node
    graph.update_endpoint_metadata(
        endpoint_id=endpoint_id,
        category=enrichment.get("category"),      # API, ADMIN, AUTH, LEGACY, etc.
        risk_score=enrichment.get("risk_score"),  # 0-100
        behavior_hint=enrichment.get("behavior_hint"),  # READ_ONLY, STATE_CHANGING, etc.
        ...
    )

    # Generate hypotheses for high-risk endpoints
    if risk_score >= min_risk_threshold:
        if behavior_hint == "ID_BASED_ACCESS":
            graph.nodes.append({
                "id": f"hypothesis:{endpoint_id}:IDOR",
                "type": "HYPOTHESIS",
                "properties": {
                    "attack_type": "IDOR",
                    "title": "Potential Insecure Direct Object Reference",
                    "confidence": 0.6,
                    "priority": 3,
                    "status": "UNTESTED"
                }
            })
```

### PHASE 25: Verification Pipeline (main.py:943-972)

```python
verification = VerificationPipeline(graph, settings, run_id)
verif_result = verification.execute()

# Results:
# - Services analyzed: 4
# - Stack versions detected: 4
# - Tests performed: 0 (gated by risk threshold)
# - Theoretical vulns: 0
```

---

## Agents et leurs Roles

### Tableau des Agents

| Code Name | Role | Tools | Output Type |
|-----------|------|-------|-------------|
| **Pathfinder** | Lead Reconnaissance | SubfinderTool | JSON: subdomains list |
| **Watchtower** | Intelligence Analyst | None (LLM) | JSON: annotated subdomains |
| **DNS Analyst** | DNS Resolution | DnsResolverTool | JSON: DNS records |
| **ASN Analyst** | ASN Mapping | ASNLookupTool | JSON: ASN info |
| **StackTrace** | Tech Fingerprinter | HttpxTool | JSON: HTTP profiles |
| **DeepScript** | JS Intelligence | JsMinerTool | JSON: endpoints/secrets |
| **All-Seeing Eye** | Endpoint Analyst | HtmlCrawlerTool, WaybackTool, RobotsTool | JSON: endpoints |
| **Param Hunter** | Parameter Discovery | None (LLM) | JSON: parameters |
| **Overwatch** | Planner | None (LLM) | JSON: attack plans |

### Anti-Hallucination Rules

Chaque task contient des regles strictes:

```yaml
context_analysis_task:
  description: |
    CRITICAL ANTI-HALLUCINATION RULES:
    1. You MUST NOT invent any subdomain.
    2. If the list is empty, state it explicitly.
    3. DO NOT guess subdomains that "should" exist.
```

---

## Tools et leurs Interactions

### SubfinderTool

```python
class SubfinderTool(BaseTool):
    name = "subfinder_enum"

    def _run(self, domain, recursive=False, all_sources=True, ...):
        # 1. Check binary availability
        if not shutil.which("subfinder"):
            if shutil.which("docker"):
                use_docker = True

        # 2. Build command
        cmd = ["docker", "run", "--rm", "gotham/subfinder", "-d", domain, "-oJ"]

        # 3. Execute
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)

        # 4. Parse JSON-lines output
        for line in proc.stdout.split("\n"):
            obj = json.loads(line)
            subdomains.append(obj.get("host"))

        # 5. Return structured JSON
        return json.dumps({"domain": domain, "count": len(subdomains), "subdomains": subdomains})
```

### HttpxTool

```python
def _run(self, subdomains: List[str], timeout: int = 12):
    # Uses HTTPX binary via Docker or local
    # Returns: status_code, technologies, IP, title, server headers
```

### WaybackTool

```python
def _run(self, domains: List[str]):
    # Queries web.archive.org/cdx/search API
    # Returns historical URLs found for each domain
```

### PageAnalyzer

```python
def analyze_url(self, url: str):
    # 1. Fetch HTML
    # 2. Parse forms (action, method, inputs)
    # 3. Extract inline JS
    # 4. Use Ollama LLM to identify API patterns
    # Returns: forms[], api_endpoints[], technologies
```

---

## Decisions de l'Orchestrateur

### Pattern: Fallback on Failure

```python
try:
    passive_crew.kickoff()
except Exception as e:
    print(f"[-] Passive Crew Failed: {e}")
    # Continue anyway - bypass will handle data collection
```

### Pattern: Scope Validation

```python
# Every ingestion step validates scope
for item in data:
    subdomain = item.get("subdomain", "")
    if not (subdomain.endswith(target_domain) or subdomain == target_domain):
        print(f"[!] Rejected hallucinated subdomain: {subdomain}")
        continue
    graph.add_subdomain_with_http(item)
```

### Pattern: Risk-Gated Actions

```python
# Planner gates offensive tools based on risk score
def suggest_actions(subnode, httpnode, ...):
    max_endpoint_risk = max(ep.get("risk_score", 0) for ep in endpoint_nodes)

    # Only suggest nuclei if risk >= 30 OR high-value category
    if max_endpoint_risk >= 30 or has_high_value_category:
        actions.append("nuclei_scan")

    # Only suggest ffuf if risk >= 40
    if max_endpoint_risk >= 40:
        actions.append("ffuf_api_fuzz")
```

### Pattern: Attack Path Scoring

```python
def score_path(subnode, httpnode, jsnode, ...):
    score = 0
    reasons = []

    # Tag bonuses
    if "BACKUP" in tag or "backup" in sub_name:
        score += 4
        reasons.append("Backup Exposed (+4)")

    # Tech stack bonuses
    if any(tech in technologies for tech in ["Express", "Django", "Laravel"]):
        score += 3
        reasons.append("Backend Stack (+3)")

    # Endpoint category bonuses
    if category in ("ADMIN", "AUTH"):
        score += 4
        reasons.append(f"{category} Endpoint (+4)")

    # Vulnerability bonuses
    for vuln in vuln_nodes:
        if severity == "CRITICAL": score += 7
        if confirmed: score += 3

    return score, reasons
```

---

## Structure des Donnees

### AssetGraph JSON (Exemple tahiti-infos.com)

```json
{
  "nodes": [
    {
      "id": "backup.tahiti-infos.com",
      "type": "SUBDOMAIN",
      "properties": {
        "name": "backup.tahiti-infos.com",
        "priority": 5,
        "tag": "SUBFINDER_DIRECT",
        "category": "RECON"
      }
    },
    {
      "id": "http:https://www.tahiti-infos.com",
      "type": "HTTP_SERVICE",
      "properties": {
        "url": "https://www.tahiti-infos.com",
        "status_code": 200,
        "technologies": ["Cloudflare", "jQuery:1.8.3", "Google Analytics"],
        "ip": "172.67.68.243",
        "title": "TAHITI INFOS, les informations de Tahiti",
        "server": "cloudflare"
      }
    },
    {
      "id": "endpoint:http:https://www.tahiti-infos.com/search",
      "type": "ENDPOINT",
      "properties": {
        "path": "/search",
        "method": "GET",
        "source": "PAGE_ANALYZER",
        "confidence": 0.85,
        "category": "UNKNOWN",
        "risk_score": 0,
        "behavior_hint": "READ_ONLY",
        "id_based_access": false
      }
    },
    {
      "id": "attack_path:03b7e326",
      "type": "ATTACK_PATH",
      "properties": {
        "target": "backup.tahiti-infos.com",
        "score": 9,
        "actions": ["manual_review"],
        "reasons": ["Backup Exposed (+4)"]
      }
    }
  ],
  "edges": [
    {
      "from": "www.tahiti-infos.com",
      "to": "http:https://www.tahiti-infos.com",
      "relation": "EXPOSES_HTTP"
    },
    {
      "from": "http:https://www.tahiti-infos.com",
      "to": "endpoint:http:https://www.tahiti-infos.com/search",
      "relation": "EXPOSES_ENDPOINT"
    },
    {
      "from": "attack_path:03b7e326",
      "to": "backup.tahiti-infos.com",
      "relation": "TARGETS"
    }
  ]
}
```

### Metrics JSON

```json
{
  "run_id": "20251215_121618_f18371ed",
  "target_domain": "tahiti-infos.com",
  "mode": "AGGRESSIVE",
  "start_time": "2025-12-15T12:16:18.825168",
  "phase_durations": {
    "verification": 3.688326
  },
  "counts": {
    "subdomains": 4,
    "http_services": 4,
    "endpoints": 4,
    "endpoints_enriched": 4,
    "parameters": 0,
    "hypotheses": 0,
    "vulnerabilities": 0
  },
  "errors": [],
  "total_duration": 47.462128
}
```

---

## Exemple Concret

### Mission tahiti-infos.com - Timeline

```
T+0s    [INIT] Mission Mode: AGGRESSIVE, Run ID: 20251215_121618_f18371ed
T+1s    [PHASE 1] Starting Passive Phase...
T+2s    [CREW] Pathfinder executes SubfinderTool
T+3s    [ERROR] Ollama connection refused (LLM unavailable)
T+4s    [BYPASS] Direct Subfinder: 4 subdomains found
          → m.tahiti-infos.com
          → www.tahiti-infos.com
          → backup.tahiti-infos.com
          → sports.tahiti-infos.com
T+5s    [WAYBACK] Querying Wayback for 5 hosts...
T+8s    [WAYBACK] Found 0 historical endpoints
T+9s    [GATE] Check: 4 subdomains (OK)
T+10s   [PHASE 2] Starting Active Phase...
T+11s   [ERROR] Active Crew Failed (Ollama unavailable)
T+12s   [PHASE 19] Universal Active Recon...
T+15s   [HTTPX] Probing 4 targets...
          → backup: 200 (Cloudflare/LiteSpeed)
          → m: 302 (Cloudflare/HSTS)
          → www: 200 (jQuery/Analytics)
          → sports: 523 (Origin unreachable)
T+20s   [PHASE 21] Surgical Strikes...
T+25s   [PLANNER] Top targets: backup, m, www, sports
T+30s   [PHASE 23A] Validation & Deep Analysis...
          → 4 reachable, 0 unreachable
          → 6 forms, 0 API endpoints found
T+35s   [PHASE 23B] Endpoint Intelligence...
          → 4 endpoints enriched
          → 0 high-risk (score >= 70)
          → 0 hypotheses generated
T+40s   [PHASE 25] Verification Pipeline...
          → 4 services analyzed
          → 4 stack versions detected
T+47s   [REPORT] Generated:
          → tahiti-infos.com_asset_graph.json
          → tahiti-infos.com_summary.md
          → tahiti-infos.com_metrics.json
T+47s   [DONE] Mission Complete.
```

### Attack Paths Generated

| Target | Score | Reasons | Actions |
|--------|-------|---------|---------|
| backup.tahiti-infos.com | 9 | Backup Exposed (+4) | manual_review |
| m.tahiti-infos.com | 8 | Endpoints Found (+2), State Changing Method (+1) | manual_review |
| www.tahiti-infos.com | 8 | Endpoints Found (+2), State Changing Method (+1) | manual_review |
| sports.tahiti-infos.com | 5 | (base score) | manual_review |

---

## Conclusion

Le workflow Recon Gotham illustre un pattern **multi-agent resilient**:

1. **Redundance**: Bypass direct quand les agents LLM echouent
2. **Scope Enforcement**: Validation systematique du domaine cible
3. **Risk Gating**: Actions offensives conditionnees par le score de risque
4. **Progressive Enrichment**: Chaque phase enrichit le graphe central
5. **Fallback Gracieux**: Gate checks avec alternatives (apex fallback)

Ce design permet au systeme de produire des resultats exploitables meme en mode degrade (sans LLM).
