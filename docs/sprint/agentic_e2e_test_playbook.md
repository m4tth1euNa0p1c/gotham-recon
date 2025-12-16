# Playbook E2E – Visualisation temps réel (services + UI)

Objectif : lancer la stack complète (sauf Ollama en local), créer une mission, observer les logs et le graphe en temps réel (WS/SSE/GraphQL) et vérifier la cohérence snapshot vs live.

## 0) Prérequis
- Docker / docker-compose
- Ollama local (par défaut `http://host.docker.internal:11434`) configuré dans `.env`
- Ports libres : 3000 (UI), 8080 (GraphQL), 8000-8007 (services), 9092 (Kafka), 3001 (Grafana), etc.

## 1) Setup & démarrage
```bash
cp .env.example .env
cp gotham-ui/.env.local.example gotham-ui/.env.local

# Démarrer (build si besoin)
docker-compose up -d --build

# Vérifier santé
docker ps
curl -f http://localhost:8000/health    # orchestrator
curl -f http://localhost:8001/health    # graph-service
```

Accès rapides :
- UI : http://localhost:3000
- GraphQL Playground : http://localhost:8080/graphql
- Grafana : http://localhost:3001

## 2) Créer une mission (orchestrator)
```bash
MISSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain":"example.com","mode":"aggressive","seed_subdomains":["www.example.com"]}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "MISSION_ID=$MISSION_ID"
```

## 3) Suivre les logs en temps réel
- WebSocket : `wscat -c ws://localhost:8000/ws/logs/$MISSION_ID`
- SSE : `curl -N http://localhost:8000/api/v1/sse/logs/$MISSION_ID`

## 4) Suivre le graphe en temps réel
- WebSocket graph-service : `wscat -c ws://localhost:8001/ws/graph/$MISSION_ID`
- GraphQL subscription (via playground http://localhost:8080/graphql) :
```graphql
subscription GraphEvents($runId: String!) {
  graphEvents(runId: $runId) { eventType source payload timestamp }
}
```

## 5) Snapshot pour comparaison
Exemple de requête GraphQL (bff-gateway) pour l’état courant :
```bash
curl -s -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ nodes(runId:\"'$MISSION_ID'\", types:[\"ENDPOINT\",\"VULNERABILITY\"]) { id type properties } }"}'
```
Comparer le snapshot (nodes/edges) avec les événements reçus en live.

## 6) Vérifier via UI
- Ouvrir http://localhost:3000
- Activer le toggle LIVE sur le composant AssetGraph (Cytoscape), vérifier les ajouts de nodes/edges en temps réel.
- Panneau console : valider la réception des logs (same mission_id).
- Utiliser PAUSE/RESUME pour stopper/reprendre le stream et vérifier la reprise.

## 7) Contrôles de cohérence
- Live vs snapshot : le nombre de ENDPOINT/HYPOTHESIS/VULNERABILITY doit matcher les events + la requête GraphQL snapshot.
- Metrics/outputs : vérifier les artefacts générés (reports/ ou graph-service, selon implémentation reporter).
- Ollama : si les phases LLM échouent, ajuster `OLLAMA_URL` ou vérifier la reachabilité depuis le conteneur orchestrator.

## 8) Nettoyage
```bash
docker-compose down
# ou, pour garder les volumes : docker-compose down --volumes=false
```
