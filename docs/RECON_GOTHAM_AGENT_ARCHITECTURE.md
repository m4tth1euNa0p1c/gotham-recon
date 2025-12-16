# Recon Gotham (agent) — Architecture V3.0

Ce document décrit l’architecture du moteur **monolithique** basé sur **CrewAI** (le script `recon_gotham/src/recon_gotham/main.py`) qui exécute une mission de reconnaissance sur un domaine cible et produit un **AssetGraph** (JSON) + rapports.

> Note: l’architecture **microservices/UI** (gotham-ui, bff-gateway, graph-service, Kafka, etc.) est documentée séparément dans `docs/ARCHITECTURE.md`.

---

## Résumé

- Entrée: `python run_mission.py <domaine> --mode stealth|aggressive [--debug] [--seed-file <fichier>]`
- Orchestrateur: `recon_gotham/src/recon_gotham/main.py`
- Données: `AssetGraph` en mémoire exporté en JSON
- Le pipeline continue même si les crews LLM échouent grâce aux **bypass** et aux phases “tools-only”.

---

## Corrections (alignement doc -> code réel)

1. **LLM utilisé uniquement dans les crews CrewAI**: les phases `passive_crew.kickoff()` et `active_crew.kickoff()` nécessitent un LLM; les phases “bypass/tools/pipelines” n’en ont pas besoin.
2. **Planner “offensif” réellement utilisé**: la planification/ranking est faite par `recon_gotham/core/planner.py::find_top_paths` (heuristique), pas par la `planning_task` LLM (définie mais non exécutée).
3. **Schéma des edges**:
   - Dans `AssetGraph`, beaucoup d’edges sont écrites avec la clé `relation` (via `_add_edge`).
   - Certaines phases ajoutent des edges avec la clé `type` (ex: génération d’hypothèses en Phase 23B).
   - Les consommateurs doivent donc lire `edge.get("type") or edge.get("relation")` (ce que fait `core/planner.py`).
4. **Noms des relations corrigés**:
   - Paramètres: `HAS_PARAM` (pas `HAS_PARAMETER`).
   - DNS: `HAS_RECORD` (pas `HAS_DNS`).
   - Vulns: `AFFECTS_*` (ex: `AFFECTS_ENDPOINT`) en plus de `AFFECTS`.
5. **Gate check V3.0**: il n’y a plus d’arrêt dur si 0 subdomains; le code applique un **apex fallback** et continue.
6. **ASN**: la tâche ASN existe (tool), mais l’ingestion ASN est actuellement un `pass` dans `main.py` (résultats non injectés dans le graphe).

---

## Arborescence (agent)

- Entrée CLI:
  - `run_mission.py` — lance `recon_gotham/src/recon_gotham/main.py`
- Orchestrateur:
  - `recon_gotham/src/recon_gotham/main.py`
- Config:
  - `recon_gotham/src/recon_gotham/config/agents.yaml`
  - `recon_gotham/src/recon_gotham/config/tasks.yaml`
  - `recon_gotham/src/recon_gotham/config/budget.yaml`
- Core:
  - `recon_gotham/src/recon_gotham/core/asset_graph.py`
  - `recon_gotham/src/recon_gotham/core/endpoint_heuristics.py`
  - `recon_gotham/src/recon_gotham/core/planner.py`
  - `recon_gotham/src/recon_gotham/core/logging.py`
- Tools (wrappers):
  - `recon_gotham/src/recon_gotham/tools/*.py` (subfinder/httpx/wayback/html crawler/js miner/etc.)
- Pipelines:
  - `recon_gotham/src/recon_gotham/pipelines/verification_pipeline.py`
  - `recon_gotham/src/recon_gotham/pipelines/reporting_service.py` (et autres modules)
- Reporting:
  - `recon_gotham/src/recon_gotham/reporting/report_builder.py` (génère aussi `reports/<domain>_red_team_report.md`)

---

## Flux d’exécution (ordre réel dans `main.py`)

### 0) Boot

- Parse args: `domain`, `--mode`, `--debug`, `--seed-file`
- Initialise `run_id`, `metrics`, logging structuré (`ReconLogger`)
- Charge `agents.yaml`, `tasks.yaml`, `budget.yaml`
- Instancie les tools (Subfinder/Httpx/Wayback/…)
- Instancie les agents CrewAI (avec `llm=ollama/<MODEL_NAME>`)

### 1) Phase 1 — Passive Recon (CrewAI) — LLM requis

Crew séquentielle: `Pathfinder -> Watchtower -> DNS Analyst -> ASN Analyst`

- Task 1: Subfinder (tool)
- Task 2: Watchtower (raisonnement LLM, pas de tool)
- Task 3: DNS Resolver (tool)
- Task 4: ASN Lookup (tool)

> Important: le pipeline ne dépend pas uniquement de ces outputs, car les étapes suivantes ré-injectent en direct les données critiques (bypass).

### 2) Ingestion Passive (bypass & parsing) — sans LLM

- **Direct Subfinder bypass**: appel direct `subfinder_tool._run(...)` puis `graph.ensure_subdomain(..., tag="SUBFINDER_DIRECT")`
- DNS: ingestion via `graph.add_dns_resolution(...)` (si la task a produit du JSON)
- ASN: task appelée mais ingestion non implémentée (placeholder)

### 3) Wayback scan (intégration universelle) — sans LLM

- Collecte tous les `SUBDOMAIN` présents + l’apex
- Appel `wayback_tool._run(domains=subs)`
- Ajoute des `ENDPOINT` en respectant le scope (`host.endswith(target_domain)`)

### 4) Gate check + fallbacks — sans LLM

- Si 0 subdomains: ajout `APEX_FALLBACK` (`target_domain` + `www`) + probes HEAD + création `HTTP_SERVICE`
- Optionnel: injection seed-file (`SEED`) + probe HEAD

### 5) Phase 2 — Active Recon (CrewAI) — LLM requis

Crew séquentielle: `Tech Fingerprinter -> JS Miner -> Endpoint Analyst -> Param Hunter`

- Le contexte de la phase passive est injecté en texte dans `tech_task.description`
- Les tâches attendent des outputs JSON stricts (voir `tasks.yaml`)

### 6) Ingestion Active — sans LLM

- Tech: parse `tech_task.output.raw`, scope checks, `graph.add_subdomain_with_http(...)`
- JS: parse `js_task.output.raw`, `graph.add_js_analysis(...)`
- Endpoints: parse `ep_task.output.raw`, `graph.add_endpoint(...)`
- Params: parse `param_task.output.raw`, `graph.add_parameter(...)` (legacy; ne crée pas de relation)

### 7) Phase 19 — Universal Active Recon (HTTPX direct) — sans LLM

- Liste toutes les `SUBDOMAIN` in-scope
- Appel direct `my_httpx_tool._run(subdomains=targets)`
- Ingestion via `graph.add_subdomain_with_http(...)`

### 8) Phase 21 — Surgical Strikes — sans LLM

1. Endpoint discovery systématique sur les `HTTP_SERVICE` confirmés:
   - HTML crawl via `html_tool._run(url=base_url)` -> ajoute des endpoints
   - JS miner “light” via `js_tool._run(url=base_url)` (ingestion partielle/placeholder)
2. Sélection des cibles “rentables” via `core/planner.py::find_top_paths` (heuristique)
3. Nuclei/Ffuf: appels présents mais actuellement **stub** (placeholders)

### 9) Phase 23A — Validation & Deep Page Analysis — sans LLM

- `EndpointValidator`: tests reachability
- `PageAnalyzer`: extraction formulaires/champs/JS endpoints (sans appel Ollama dans le flow actuel)
- Ajoute des `ENDPOINT` dérivés des `form.action` et patterns JS

### 10) Phase 23B — Endpoint Intelligence Enrichment — sans LLM

- Enrichit les endpoints via `core/endpoint_heuristics.py::enrich_endpoint`
- Met à jour les champs (category/scores/behavior/auth/etc.) via `graph.update_endpoint_metadata(...)`
- Crée des `PARAMETER` via `graph.add_parameter_v2(...)` (avec edge `HAS_PARAM`)
- Génère des `HYPOTHESIS` par heuristique (ajout direct de nodes + edges)

### 11) Phase 25 — Verification Pipeline — sans LLM

`pipelines/verification_pipeline.py`:
- Analyse stack (headers, versions)
- Tests contrôlés si `active_verification_enabled` (lié au mode “aggressive”)
- Matérialise des vulns théoriques à partir d’hypothèses (si présentes)

### 12) Reporting & exports — sans LLM

- `core/planner.py::find_top_paths` -> liste `paths`
- Matérialisation des `ATTACK_PATH` dans le graphe (`graph.add_attack_path`)
- `ReportBuilder.generate_report(...)` -> `reports/<domain>_red_team_report.md`
- `generate_mission_summary(...)` -> `recon_gotham/output/<domain>_summary.md`
- `graph.export_json(...)` -> `recon_gotham/output/<domain>_asset_graph.json`
- `metrics` -> `recon_gotham/output/<domain>_<run_id>_metrics.json`

---

## LLM: où et comment il est utilisé

### CrewAI (agents)

- Configuration dans `main.py`:
  - `MODEL_NAME` (env) -> par défaut `qwen2.5:14b`
  - `llm_config = f"ollama/{MODEL_NAME}"`
  - Chaque `Agent(...)` reçoit `llm=llm_config`

Concrètement, si Ollama est indisponible, les crews peuvent échouer et le pipeline continue via les bypass.

### Tools utilisant Ollama (hors CrewAI)

- `tools/page_analyzer.py` et `tools/security_tester.py` savent appeler:
  - `OLLAMA_BASE_URL` (défaut `http://localhost:11434`)
  - `OLLAMA_CODER_MODEL` (défaut `qwen2.5-coder:7b`)
- Dans le flow actuel de `main.py`, ces appels ne sont pas branchés (ils existent mais ne sont pas invoqués automatiquement).

### Variables d’environnement: point d’attention

`.env.example` contient `OLLAMA_URL` / `OLLAMA_MODEL` (plutôt orienté stack docker/microservices).  
Le moteur agent lit principalement:

- `MODEL_NAME` (CrewAI)
- `OLLAMA_BASE_URL`, `OLLAMA_CODER_MODEL` (tools)

---

## Modèle de données: AssetGraph

### Nœuds (types)

Définis dans `core/asset_graph.py` (`VALID_NODE_TYPES`), notamment:

- `SUBDOMAIN` (id: `www.example.com`)
- `HTTP_SERVICE` (id: `http:https://www.example.com`)
- `ENDPOINT` (id: `endpoint:http:https://www.example.com/search`)
- `PARAMETER` (id: `param:<endpoint_id>:<name>`)
- `VULNERABILITY` (id: `vuln:<tool>:<name>:<affected_node_id>`)
- `HYPOTHESIS` (ids variables selon la phase: `hypo:<hash>` ou `hypothesis:<endpoint_id>:<attack_type>`)
- `ATTACK_PATH` (id: `attack_path:<hash>`)
- Infra: `IP_ADDRESS`, `DNS_RECORD`, `ASN`
- Extensions: `JS_FILE`, `SECRET`, `ORG`, `BRAND`, `SAAS_APP`, `REPOSITORY`, `LEAK`

### Edges (relations)

Relations fréquentes (non exhaustif):

- `EXPOSES_HTTP` (SUBDOMAIN -> HTTP_SERVICE)
- `EXPOSES_ENDPOINT` (HTTP_SERVICE -> ENDPOINT)
- `HAS_PARAM` (ENDPOINT -> PARAMETER)
- `HAS_HYPOTHESIS` (ENDPOINT -> HYPOTHESIS)
- `TARGETS` (ATTACK_PATH -> cible)
- Infra:
  - `RESOLVES_TO` (SUBDOMAIN -> IP_ADDRESS)
  - `BELONGS_TO` (IP_ADDRESS -> ASN)
  - `HAS_RECORD` (SUBDOMAIN -> DNS_RECORD)
- Vulns:
  - `AFFECTS_*` (VULNERABILITY -> nœud affecté; ex `AFFECTS_ENDPOINT`)

### Format edge: `relation` vs `type`

Dans les exports, un edge peut être:

- `{"from": "...", "to": "...", "relation": "EXPOSES_HTTP"}`
- `{"from": "...", "to": "...", "type": "HAS_HYPOTHESIS"}`

Le code de scoring (`core/planner.py`) supporte les deux.

---

## Scope & anti-hallucination

- `AssetGraph.ensure_subdomain(...)` rejette toute entrée hors scope (`hostname.endswith(target_domain)`).
- Plusieurs phases font des “scope checks” avant ingestion (ex: ingestion Tech et HTTPX).
- `AssetGraph.export_json(...)` filtre aussi les nœuds hors scope et supprime les edges qui pointent vers des nœuds filtrés.

---

## Outputs

- `recon_gotham/output/<domain>_asset_graph.json`
- `recon_gotham/output/<domain>_summary.md`
- `recon_gotham/output/<domain>_<run_id>_metrics.json`
- `recon_gotham/output/<domain>_<run_id>_live.log` (JSON lines, encodé UTF-8)
- `reports/<domain>_red_team_report.md` (+ PDF si `pandoc` est installé)

---

## Notes & limites (état actuel)

- ASN: collecte possible, ingestion non implémentée dans `main.py`.
- Nuclei/Ffuf: intégration présente mais stubbée (pas d’exécution effective).
- Incohérences `relation`/`type` dans les edges: tolérées côté planner mais à uniformiser si possible.
- Windows: éviter les emojis dans la sortie console (ou forcer UTF-8) pour prévenir les erreurs `charmap`.
