# Gotham Recon (plateforme Web) — Architecture et workflow

Ce document décrit l’architecture **microservices** (UI + API + services de phases) qui exécute des missions Recon Gotham via le Web, stocke les résultats dans `graph-service`, et les expose à l’UI via `bff-gateway`.

Pour l’architecture du moteur **CLI/agent monolithique**, voir `docs/RECON_GOTHAM_AGENT_ARCHITECTURE.md`.

---

## Vue d’ensemble

Objectif: faire tourner un workflow "comme le CLI", mais orchestré par services, avec des outils réels (Subfinder/HTTPX/Wayback) et une visualisation temps réel.

Flux principal:

1. UI (`gotham-ui`) -> BFF GraphQL (`bff-gateway`)
2. BFF -> `recon-orchestrator` (création + pilotage mission)
3. `recon-orchestrator` -> services de phases (osint-runner, active-recon, endpoint-intel, verification, planner, reporter)
4. Tous les services publient les assets (nodes/edges/logs) dans `graph-service`
5. `graph-service` publie des events Kafka + WebSockets pour l’UI

---

## Diagramme (services)

```
Browser
  -> gotham-ui (Next.js, :3000)
     -> bff-gateway (GraphQL, :8080)
        -> recon-orchestrator (:8000)
           -> osint-runner (:8002)
           -> active-recon (:8003)
           -> endpoint-intel (:8004)
           -> verification (:8005)
           -> planner (:8007)
           -> reporter (:8006)

Tous -> graph-service (:8001) -> SQLite (/data/gotham.db)
graph-service -> Kafka (graph.events, logs.recon) + WebSockets
```

Ports et mapping exacts: voir `docker-compose.yml`.

---

## Rôles des services (résumé)

### `recon-orchestrator` (coordination de mission)

- Fichier: `services/recon-orchestrator/main.py`
- Rôle: cycle de vie mission (create/start/cancel), séquencement des phases, diffusion des logs (Kafka + WS).
- Appelle les services de phase via HTTP et persiste l’état en SQLite (volume `gotham_data`).

### `graph-service` (CQRS nodes/edges + temps réel)

- Fichier: `services/graph-service/main.py`
- DB: `services/graph-service/database/db.py` (SQLite async, `DATABASE_PATH=/data/gotham.db`)
- Rôle:
  - API de mutation: création/MAJ nodes + edges
  - API de lecture: query par mission/type/score, stats, export
  - WebSockets: mises à jour temps réel par `mission_id`
  - Kafka: publication d’events pour UI/observabilité

Endpoints importants:

- `POST /api/v1/nodes` (create)
- `PUT /api/v1/nodes/{node_id}` (update)
- `POST /api/v1/nodes/query` (requêtes filtrées: mission_id, types, risk_score_min, pagination)
- `GET /api/v1/nodes?mission_id=...&type=...` (listing filtrable)

### `osint-runner` (phase passive)

- Fichier: `services/osint-runner/main.py`
- Rôle: découverte passive "réelle" (Subfinder + Wayback + DNS) et publication dans `graph-service`.
- Point clé: exécution Subfinder via Docker CLI et accès au daemon Docker via `/var/run/docker.sock` (voir `docker-compose.yml`).

### `active-recon` (phase active)

- Fichier: `services/active-recon/main.py`
- Rôle: probing HTTP (ProjectDiscovery httpx), crawling/JS mining, Wayback, et publication des résultats.
- Point clé: utilisation explicite du binaire `httpx` ProjectDiscovery via `/usr/local/bin/httpx` (évite le Docker-in-Docker).

### `endpoint-intel` (enrichissement)

- Fichier: `services/endpoint-intel/main.py`
- Rôle: scoring/catégorisation d’endpoints, extraction de paramètres, génération d’hypothèses, puis publication.

### `verification` / `planner` / `reporter`

- `services/verification/main.py`: validation & contrôles (selon mode/paramètres).
- `services/planner/main.py`: ranking et "attack paths" (heuristiques) à partir du graphe.
- `services/reporter/main.py`: agrégation nodes/edges d’une mission et génération de rapports.

---

## Problèmes identifiés et corrections (analyse)

| Service | Problème | Correction (observée dans le code) | Effet attendu |
|---|---|---|---|
| `osint-runner` | Subdomains "devinés" via LLM | Implémentation `SubfinderTool` + `WaybackTool` | Résultats déterministes et traçables |
| `active-recon` | HTTPX via Docker-in-Docker instable | Installation binaire httpx v1.6.9 dans l’image | Probing stable, moins dépendant de Docker |
| `active-recon` | Ambiguïté `httpx` (Python) vs `httpx` (binaire) | Appel explicite `/usr/local/bin/httpx` + ordre Dockerfile | Pas de collision PATH/CLI, exécution reproductible |
| `graph-service` | Lecture nodes sans filtres suffisants | `GET /api/v1/nodes` avec filtres `mission_id`/`type` | UI/BFF peuvent éviter le mélange inter-missions |

Remarque: le montage du socket Docker (`/var/run/docker.sock`) est fonctionnel mais donne des privilèges élevés aux containers (à documenter et limiter si possible).

---

## Pourquoi le Web peut "trouver plus" que le CLI (et comment comparer)

Des écarts CLI vs Web peuvent venir de:

- **Périmètre de lecture**: si l’UI ne filtre pas strictement par `mission_id` et `type`, elle peut compter des nodes d’autres missions (la correction `GET /api/v1/nodes` aide à diagnostiquer/filtrer).
- **Différences d’heuristiques**: `endpoint-intel` peut générer `PARAMETER`/`HYPOTHESIS` même si le CLI ne le fait pas (selon scores/thresholds).
- **Versions/outils**: Subfinder/HTTPX (image/binaire) peuvent être différents entre CLI et services.
- **Paramètres de run**: mode (stealth/aggressive), timeouts, limites, seeds, et rate limits.

Checklist de comparaison "parité":

1. Même `target_domain`, même `mode`
2. Même version Subfinder/HTTPX (ou au moins même source: binaire vs docker image)
3. Même règles de scope (in-scope) et mêmes filtres de lecture par mission
4. Même politique de scoring/thresholds (si comparaison "hypotheses/params")

---

## Outils réels et versions (parité)

- Subfinder:
  - Web (`osint-runner`): `docker run projectdiscovery/subfinder` (tag par défaut si non précisé).
  - CLI: image `gotham/subfinder` construite via `docker/subfinder/Dockerfile` (go install `@latest`).
  - Recommandation: pinner la version (tag Docker ou version Go) pour stabiliser les métriques.
- HTTPX:
  - Web (`active-recon`): binaire ProjectDiscovery installé en dur (v1.6.9) dans `services/active-recon/Dockerfile`.
  - CLI: binaire local si présent, sinon `docker run projectdiscovery/httpx` via `recon_gotham/src/recon_gotham/tools/httpx_tool.py`.
  - Recommandation: aligner la version (binaire ou image) pour comparer "technologies" et couverture.

---

## Mapping CLI -> Web (équivalence de phases)

| CLI (monolithique) | Web (microservices) |
|---|---|
| Phase 1 (Passive Crew) + bypass Subfinder | `osint-runner` (Subfinder + Wayback + DNS) |
| Gate check / apex fallback | `recon-orchestrator` + (optionnel) `safety-net` |
| Phase 19 (HTTPX direct) | `active-recon` (ProjectDiscovery httpx) |
| Phase 23B (heuristics + params + hypotheses) | `endpoint-intel` |
| Phase 25 (verification pipeline) | `verification` |
| Planner heuristique (`find_top_paths`) | `planner` |
| Summary/exports | `reporter` (et `graph-service` pour storage/API) |

---

## Notes d’exploitation

- Le stockage principal (dans cette stack) est SQLite (`gotham_data:/data/gotham.db`). Postgres/Redis/Elasticsearch existent dans `docker-compose.yml` mais l’utilisation dépend des services (certaines parties sont encore "transitionnelles").
- Si Subfinder est exécuté via Docker depuis un container, `docker-ce-cli` + `/var/run/docker.sock` doivent être disponibles (comme dans `docker-compose.yml`).
