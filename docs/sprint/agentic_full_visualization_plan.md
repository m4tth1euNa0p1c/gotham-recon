# Plan détaillé – Visualisation temps réel & orchestration complète

Objectif : faire tourner l’architecture microservices existante, garder Ollama local, et offrir une UI (Cytoscape/Next.js) qui montre logs CrewAI + graphe (nodes/edges/paths) en temps réel via drag & drop.

Références utiles :
- Architecture cible & prompts : `docs/sprint/agentic_architecture_prompts.md`
- État des runs / phase fix : `docs/task.md`
- Services : répertoire `services/` (graph-service, recon-orchestrator, bff-gateway, scanner-proxy, osint-runner, active-recon, endpoint-intel, verification, reporter, planner)
- UI : `gotham-ui/` (Next.js 16, React 19, Cytoscape)
- Orchestration : `docker-compose.yml` (Postgres, Redis, Kafka, Elasticsearch, Prometheus/Grafana, Jaeger, services, UI)

## 1) Lancer l’infra (sauf Ollama)
```
docker-compose up -d
# UI        : http://localhost:3000
# Gateway   : http://localhost:8080/graphql
# Orchestrator WS (logs) : ws://localhost:8000 (selon config)
# Grafana   : http://localhost:3001
```
Ollama reste local : définir l’URL locale dans `.env` ou variables pour les services qui appellent le modèle (ex. recon-orchestrator/pipeline-runner).

## 2) Flux cible (backend → UI)
1. recon-orchestrator reçoit une mission (REST/GraphQL) et déclenche les runners (osint, active-recon, endpoint-intel, verification).
2. Chaque service écrit/maj le graphe via graph-service (CQRS write) **et** publie un événement Kafka `graph.events` (add/update node/edge, attack_path).
3. graph-service persiste (Postgres) et expose lecture/queries.
4. bff-gateway agrège (GraphQL) + subscriptions (WS/SSE) en se branchant à Kafka pour le temps réel.
5. gotham-ui consomme :
   - Subscriptions/WS → affichage live des mutations (Cytoscape, drag&drop).
   - REST/GraphQL → snapshots (nodes/edges/paths).
   - Console logs → via SSE/WS (topic logs ou tail ReconLogger si exposé).

## 3) Schéma d’événements (proposition)
Topic Kafka `graph.events` (clé = `run_id`):
```json
{
  "run_id": "20251212_123456_abcd",
  "event_type": "node_added|node_updated|edge_added|attack_path_added",
  "source": "osint|active_recon|endpoint_intel|verification|planner|orchestrator",
  "payload": {
    "node": {"id": "endpoint:https://...", "type": "ENDPOINT", "properties": {...}},
    "edge": {"from": "...", "to": "...", "type": "HAS_HYPOTHESIS"},
    "attack_path": {...}
  },
  "timestamp": "2025-12-12T12:34:56Z"
}
```
Logs CrewAI/agents (topic `logs.recon`), format JSON structuré (niveau, run_id, phase, message).

## 4) Intégration par service (checklist)
- graph-service (port 8001) : s’assurer de la persistance Postgres, endpoints read/write (nodes, edges, queries). Ajouter consommation Kafka optionnelle si vous voulez rebuild depuis events.
- recon-orchestrator (8000) : expose création de mission, déclenche phases (appel services). Publier événements graph + logs. Passer l’URL Ollama locale en env.
- scanner-proxy (50051/8051) : façade gRPC vers subfinder/httpx/nuclei/ffuf ; utiliser cache Redis pour éviter re-scan.
- osint-runner / active-recon / endpoint-intel / verification : après chaque mutation, appel graph-service (write) + publish event Kafka.
- planner (8007) : calcule attack paths et les matérialise (nodes/edges) + events.
- reporter (8006) : agrège graph + findings, peut écrire dans Elasticsearch; garder export summary/graph/metrics.
- bff-gateway (8080) : GraphQL unifié + subscriptions (WS/SSE) en lisant Kafka (graph.events, logs.recon) et graph-service pour les snapshots. Ajouter persisted queries pour le front.
- gotham-ui (3000) : Next.js + Cytoscape, consommer GraphQL/SSE/WS, panneau console pour logs, bouton “live on/off”, “snapshot” pour figer la vue; drag&drop editable (sauvegarder layout côté UI ou via graph-service).

## 5) Contrats côté UI/BFF (résumé)
- Queries (GraphQL) : `nodes(filter)`, `edges(filter)`, `attackPaths(run_id)`, `metrics(run_id)`.
- Subscriptions : `graphEvents(run_id)`, `logs(run_id)`.
- Filters utiles : `run_id`, `target_domain`, `type`, `risk_score>=`, `category`.

## 6) Monitoring / observabilité
- Traces : Jaeger (OTLP) branché depuis services (FastAPI + httpx instrumentation).
- Metrics : Prometheus scrape services; dashboards Grafana (latence, erreurs, events/s, nodes/edges count).
- Healthchecks : déjà dans docker-compose (curl /health).

## 7) Debug / validation
- Vérifier events Kafka par run_id (compter vs metrics counts).
- Snapshot vs live : requête GraphQL snapshot puis déclencher une mutation (seed/endpoint) et confirmer apparition live dans l’UI sans refresh.
- Logs : console UI doit afficher les messages CrewAI/agents (topic logs.recon ou endpoint SSE).
- Ollama : tester un run où seule la partie LLM est locale; vérifier que les services accèdent bien à l’URL locale définie.

## 8) Prochaines actions possibles
- Documenter le schéma GraphQL complet (queries + subscriptions) et les topics Kafka dans `docs/`.
- Ajouter un “event emitter” dans AssetGraph du monolith (si réutilisé) pour publier en plus du call graph-service.
- Fournir un make/compose profile “dev” (sans Elasticsearch/Grafana/Jaeger) pour itérer plus léger ; profil “full” pour démo.
- Ajouter un endpoint de sauvegarde du layout Cytoscape (persister les positions par run_id).
