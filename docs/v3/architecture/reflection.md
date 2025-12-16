# Architecture de Réflexion (P0.6)

> **Module d'auto-amélioration et validation des résultats**
>
> Version: 3.2.0 | Dernière mise à jour: Décembre 2025

---

## Vue d'ensemble

L'architecture de réflexion permet aux agents de valider, enrichir et améliorer automatiquement les résultats des outils de reconnaissance. Elle introduit un cycle de feedback qui détecte les gaps dans les données collectées et génère des scripts d'investigation pour les combler.

```
┌─────────────────────────────────────────────────────────────────┐
│                    REFLECTION ARCHITECTURE                       │
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

---

## Composants

### 1. ResultAnalyzer

Analyse les résultats des outils pour détecter les problèmes et opportunités d'enrichissement.

**Fichier:** `services/recon-orchestrator/core/reflection.py`

```python
class ResultAnalyzer:
    """Analyzes tool results for completeness and enrichment opportunities."""

    def analyze_subfinder(self, result: Dict) -> AnalysisResult:
        """Analyze subfinder results."""
        # Checks: count, diversity, patterns

    def analyze_httpx(self, result: Dict) -> AnalysisResult:
        """Analyze httpx results."""
        # Checks: response codes, tech detection, failures

    def analyze_dns(self, result: Dict) -> AnalysisResult:
        """Analyze DNS resolver results."""
        # Checks: resolution rate, record types

    def analyze_wayback(self, result: Dict) -> AnalysisResult:
        """Analyze wayback results."""
        # Checks: endpoint patterns, sensitive paths
```

**Métriques analysées:**

| Outil | Métrique | Seuil | Action |
|-------|----------|-------|--------|
| Subfinder | Nombre de subdomains | < 5 | dns_bruteforce |
| Subfinder | Diversité des patterns | < 3 | Alerte |
| HTTPX | Taux d'échec | > 50% | retry_with_delay |
| HTTPX | Tech detection | 0 | tech_fingerprint |
| DNS | Taux de résolution | < 80% | Alerte |
| Wayback | Endpoints sensibles | > 0 | config_checker |

---

### 2. ScriptGenerator

Génère des scripts Python d'investigation à partir de templates prédéfinis.

```python
class ScriptGenerator:
    """Generates Python investigation scripts from templates."""

    TEMPLATES = {
        "dns_bruteforce": "...",
        "tech_fingerprint": "...",
        "config_checker": "...",
        "port_check": "...",
        "header_analysis": "...",
        "certificate_check": "...",
    }

    def generate(self, template_name: str, context: Dict) -> str:
        """Generate script from template with context variables."""
```

**Templates disponibles:**

#### dns_bruteforce
```python
# Bruteforce DNS pour découvrir des sous-domaines cachés
import socket
import json

WORDLIST = ["www", "mail", "ftp", "admin", "api", "dev", "staging", ...]
TARGET = "{target_domain}"

results = []
for word in WORDLIST:
    subdomain = f"{word}.{TARGET}"
    try:
        ip = socket.gethostbyname(subdomain)
        results.append({"subdomain": subdomain, "ip": ip})
    except socket.gaierror:
        pass

print(json.dumps({"discovered": results}))
```

#### tech_fingerprint
```python
# Fingerprinting technologique avancé
import urllib.request
import json
import re

URL = "{target_url}"
SIGNATURES = {
    "WordPress": [r"wp-content", r"wp-includes"],
    "Drupal": [r"sites/default", r"drupal.js"],
    "Laravel": [r"laravel_session", r"XSRF-TOKEN"],
    ...
}

# Analyze response headers and body
```

#### config_checker
```python
# Détection de fichiers de configuration exposés
PATHS = [
    "/.env", "/.git/config", "/config.php", "/web.config",
    "/wp-config.php", "/.htaccess", "/robots.txt", "/sitemap.xml",
    ...
]

# Check each path for exposure
```

---

### 3. PythonScriptExecutorTool

Exécute les scripts générés de manière sécurisée avec validation AST.

**Fichier:** `services/recon-orchestrator/tools/python_script_executor_tool.py`

```python
class PythonScriptExecutorTool(BaseTool):
    """Safe execution of generated Python scripts."""

    # Imports autorisés (whitelist)
    ALLOWED_IMPORTS = {
        'json', 'urllib', 'urllib.request', 'urllib.error', 'urllib.parse',
        're', 'socket', 'ssl', 'datetime', 'time', 'hashlib', 'base64',
        'collections', 'itertools', 'functools', 'typing', 'string',
        'math', 'statistics', 'random', 'ipaddress', 'html', 'xml',
    }

    # Appels bloqués (blacklist)
    BLOCKED_CALLS = {'exec', 'eval', 'compile', '__import__'}

    def _validate_safety(self, code: str) -> Optional[str]:
        """AST validation to reject unsafe operations."""

    def _run(self, script_code: str, timeout: int = 30) -> str:
        """Execute script and return JSON results."""
```

**Sécurité:**
- Validation AST avant exécution
- Whitelist d'imports stricte
- Timeout configurable (défaut: 30s)
- Isolation dans un processus séparé
- Aucun accès filesystem (sauf /tmp pour le script)

---

### 4. ReflectionLoop

Orchestration du cycle de réflexion complet.

```python
class ReflectionLoop:
    """Orchestrates the reflection process."""

    def __init__(self, mission_id: str, graph_service_url: str):
        self.analyzer = ResultAnalyzer()
        self.generator = ScriptGenerator()
        self.mission_id = mission_id

    async def reflect(
        self,
        tool_name: str,
        result: Any,
        script_executor: Optional[PythonScriptExecutorTool] = None
    ) -> Dict:
        """
        Run full reflection cycle:
        1. Analyze results
        2. Generate scripts if needed
        3. Execute scripts
        4. Update graph with findings
        """
```

---

## Intégration dans le Pipeline

### crew_runner.py

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

---

## Configuration Agent

### agents.yaml

```yaml
reflector_agent:
  role: "Result Validation & Enrichment Specialist (Code Name: Reflector)"
  goal: >
    Analyze tool results for completeness, accuracy, and enrichment opportunities.
    When results are incomplete or errors occur, trigger investigation scripts
    to fill gaps and validate findings.
  backstory: >
    You are a meticulous quality assurance specialist for reconnaissance data.
    You never accept tool results at face value. You analyze completeness scores,
    identify missing data, validate consistency, and propose investigation scripts
    when automated tools fail or return incomplete data.
```

### tasks.yaml

```yaml
reflection_task:
  description: >
    Analyze tool results for completeness and enrichment opportunities.

    TOOL-SPECIFIC ANALYSIS:
    - Subfinder: Check subdomain count (expect 10-100 for most domains)
    - HTTPX: Check for failed probes, missing tech detection
    - Wayback: Look for interesting historical endpoints (admin, api, config)
    - DNS: Identify unresolved domains, shared IPs patterns

  expected_output: >
    STRICT JSON with validation results and enrichment recommendations.

  agent: reflector_agent
```

---

## Métriques de Réflexion

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

---

## Exemple de Résultat

```json
{
  "tool_name": "subfinder",
  "analysis": {
    "completeness_score": 0.75,
    "issues": [
      {
        "type": "low_count",
        "severity": "warning",
        "message": "Only 5 subdomains found, expected 10-100"
      }
    ],
    "enrichment_opportunities": [
      {
        "type": "dns_bruteforce",
        "reason": "Low subdomain count suggests more may exist"
      }
    ]
  },
  "scripts_generated": ["dns_bruteforce"],
  "scripts_executed": 1,
  "findings": {
    "new_subdomains": ["admin.example.com", "api.example.com"]
  },
  "graph_updates": {
    "nodes_added": 2,
    "edges_added": 4
  }
}
```

---

## Roadmap

### v3.3 (Prévu)
- [ ] LLM-powered script generation (dynamic templates)
- [ ] Cross-tool correlation analysis
- [ ] Automated hypothesis validation
- [ ] Learning from past reflections

### v3.4 (Prévu)
- [ ] Multi-agent reflection consensus
- [ ] Graph pattern detection
- [ ] Anomaly detection in results
