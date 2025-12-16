# Instructions – Visualisation temps réel & orchestration (Recon Gotham + infra agentique)

## Objectifs
- Faire tourner l’infra backend (BDD, cache, bus, services) en central, Ollama restant local.
- Afficher les logs CrewAI dans l’UI (terminal/console) et projeter le graphe (nodes/edges/paths) en drag & drop, mis à jour en temps réel.
- Reposer sur l’architecture cible décrite dans `agentic_architecture_prompts.md` et l’existant Recon Gotham (phases 1-25).

## Mapping rapide au code actuel
- Orchestrateur: `recon_gotham/src/recon_gotham/main.py` (phases 1-25, AssetGraph en mémoire, exports JSON).
- Pipelines: `pipelines/*` (osint, recon, endpoint_intel, verification) + outils `tools/*`.
- Graph: sérialisé en `output/<dom>_asset_graph.json` et `temp_graph.json`; enrichi Phase 23B, vulnérabilités via Phase 25b.
- Logs/métriques: `ReconLogger` (output/), metrics JSON par run.

## Cible infra (microservices)
- API Gateway + Mesh: mTLS, retries, circuit-breaker, auth JWT/OIDC.
- Services (idéalement conteneurisés):
  - `recon-orchestrator` (write/CQRS): pilote les runs, écrit dans graph store.
  - `pipeline-runner` (async workers): exécute phases/agents, publie événements.
  - `graph-query-service` (read/CQRS): expose GraphQL/REST pour nodes/edges/paths.
  - `scanner-proxy` (gRPC/HTTP): façade vers subfinder/httpx/nuclei/ffuf.
  - `reporting-service`: assemble reports/metrics.
- Data plane: Postgres (state/runs), graph store (Neo4j ou Postgres + table edges), Redis (cache/events), bus (Kafka/NATS) pour streaming des mutations.
- Ollama: reste local, accessible depuis orchestrator (URL locale) via tunnel ou config réseau.

## Plan de réalisation (étapes)
1) **Persistance du graphe**: ajouter un backend (Postgres/Neo4j) pour stocker nodes/edges; exposer un writer dans orchestrator et un reader dans `graph-query-service`.
2) **Stream temps réel**: instrumenter orchestrator/pipeline-runner pour émettre chaque mutation (add node/edge, update risk) sur le bus (NATS/Kafka). Format: JSON {event_type, node/edge payload, run_id, timestamp}.
3) **API lecture/visualisation**: dans `graph-query-service`, ajouter GraphQL avec subscriptions (ou SSE/WebSocket) pour diffuser les événements + queries pour snapshots (filter par run_id/domain/type/risk).
4) **UI drag&drop**: front (React/Vue) avec composant graph (ex: Cytoscape/Dagre) connecté en WebSocket aux événements et capable de repositionner/sauvegarder le layout. Bouton “live” (stream on/off) + “snapshot” (freeze pour inspection).
5) **Logs CrewAI dans l’UI**: exposer un endpoint SSE tail des logs structurés (ReconLogger) ou consommer le même bus; afficher dans un panneau console de l’UI.
6) **Services à lancer (sauf Ollama)**: Postgres, Redis, bus (Kafka/NATS), gateway, mesh sidecar, orchestrator, pipeline-runner, graph-query-service, reporting. Orchestration via docker-compose/k8s; Ollama reste en local (configurer l’URL dans .env pour le run).
7) **Intégration Recon Gotham**: encapsuler `main.py` dans `recon-orchestrator` (mode CLI ou API). Brancher l’écriture des mutations et la lecture/écriture graph store; remplacer export fichier par appels au writer service.

## Flux attendu (visualisation)
- Pipeline produit: subdomains -> http services -> endpoints -> hypotheses -> vulnerabilities.
- Chaque mutation est poussée au bus; l’UI reçoit et met à jour le graphe en temps réel.
- Planner/attack paths matérialisés en nodes/edges `ATTACK_PATH` visibles immédiatement.

## Debug / validation
- Vérifier que chaque run publie des mutations (compter events/run_id sur le bus).
- Comparer compteur live vs counts metrics (endpoints_enriched, hypotheses, vulnerabilities).
- Tester l’UI: activer live stream, valider que l’ajout d’un node (e.g., via seed ou PageAnalyzer) apparaît sans refresh; forcer un snapshot et comparer au graph store.
- Assurer que les services (DB/cache/bus) tournent avant le run; Ollama local reachable.

## Prochaines actions
- Définir le schéma d’événements (JSON) et le contrat GraphQL (queries/subscriptions) pour `graph-query-service`.
- Ajouter un module “event emitter” dans main.py/AssetGraph pour publier add/update.
- Ébaucher docker-compose pour Postgres, Redis, bus, gateway, services; laisser Ollama hors compose (localhost).
- Implémenter l’UI de supervision (console logs + graph live) puis lier aux endpoints SSE/WS.
