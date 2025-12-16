# Quick Start Guide

> **Démarrer avec Recon Gotham en 5 minutes**

---

## Prérequis

```bash
# Vérifier les installations
docker --version          # >= 24.0
docker compose version    # >= 2.20
curl --version           # Pour les tests API
```

---

## Installation

### 1. Cloner le Repository

```bash
git clone https://github.com/gotham/recon-gotham.git
cd recon-gotham
```

### 2. Configuration

```bash
# Copier le fichier d'environnement
cp .env.example .env

# Optionnel: Personnaliser les ports/configurations
# nano .env
```

### 3. Démarrer les Services

```bash
# Lancer l'infrastructure complète
docker compose up -d

# Vérifier le statut (attendre ~30s pour le démarrage)
docker compose ps
```

### 4. Vérifier l'Installation

```bash
# Health check des services
curl http://localhost:8000/health  # Orchestrator ✓
curl http://localhost:8001/health  # Graph Service ✓
curl http://localhost:8080/health  # BFF Gateway ✓
```

---

## Lancer Votre Première Mission

### Option 1: Via l'Interface Web (UI)

1. Ouvrir http://localhost:3000
2. Cliquer sur "New Mission"
3. Entrer le domaine cible: `example.com`
4. Sélectionner le mode: `AGGRESSIVE`
5. Cliquer sur "Start Mission"
6. Suivre la progression en temps réel

### Option 2: Via l'API REST

```bash
# Créer une mission
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{
    "target_domain": "example.com",
    "mode": "AGGRESSIVE"
  }'

# Réponse:
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "target_domain": "example.com",
#   "status": "PENDING"
# }
```

### Option 3: Via GraphQL

```bash
curl -X POST http://localhost:8080/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { startMission(input: { targetDomain: \"example.com\", mode: AGGRESSIVE }) { id status } }"
  }'
```

---

## Suivre la Progression

### Via l'UI

Naviguer vers `/mission/{id}/workflow` pour voir:
- Pipeline des agents en temps réel
- Graphe d'assets se construisant
- Logs de la mission

### Via l'API

```bash
# Statut de la mission
curl http://localhost:8000/api/v1/missions/{mission_id}

# Statistiques du graphe
curl http://localhost:8001/api/v1/missions/{mission_id}/stats

# Logs en streaming (SSE)
curl http://localhost:8000/api/v1/sse/logs/{mission_id}
```

### Via GraphQL

```graphql
# Dans le GraphQL Playground: http://localhost:8080/graphql

query {
  mission(id: "550e8400-...") {
    id
    targetDomain
    status
    progress
  }
  graphStats(missionId: "550e8400-...") {
    totalNodes
    totalEdges
    nodesByType
  }
}
```

---

## Résultats

### Accéder aux Assets Découverts

```bash
# Liste des sous-domaines
curl "http://localhost:8001/api/v1/nodes?mission_id={id}&type=SUBDOMAIN"

# Liste des services HTTP
curl "http://localhost:8001/api/v1/nodes?mission_id={id}&type=HTTP_SERVICE"

# Liste des endpoints
curl "http://localhost:8001/api/v1/nodes?mission_id={id}&type=ENDPOINT"
```

### Exporter le Graphe

```bash
# Export JSON complet
curl http://localhost:8001/api/v1/missions/{mission_id}/export > graph.json

# Taille du fichier
ls -lh graph.json
```

### Voir les Hypothèses de Sécurité

```bash
# Via l'UI: /mission/{id}/vulnerabilities

# Via API
curl "http://localhost:8001/api/v1/nodes?mission_id={id}&type=HYPOTHESIS"
```

---

## Modes de Reconnaissance

### AGGRESSIVE (Défaut)

```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain": "example.com", "mode": "AGGRESSIVE"}'
```

- Toutes les phases activées
- Probing HTTP complet
- Wayback Machine
- JS Mining
- Analyse de sécurité

### STEALTH

```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain": "example.com", "mode": "STEALTH"}'
```

- Découverte passive uniquement
- Pas de probing HTTP actif
- Moins de bruit

### BALANCED

```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{"target_domain": "example.com", "mode": "BALANCED"}'
```

- Compromis entre couverture et discrétion

---

## Options Avancées

### Injection de Seeds

```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{
    "target_domain": "example.com",
    "mode": "AGGRESSIVE",
    "seed_subdomains": [
      "www.example.com",
      "api.example.com",
      "admin.example.com"
    ]
  }'
```

### Options Personnalisées

```bash
curl -X POST http://localhost:8000/api/v1/missions \
  -H "Content-Type: application/json" \
  -d '{
    "target_domain": "example.com",
    "mode": "AGGRESSIVE",
    "options": {
      "skip_wayback": false,
      "max_endpoints": 500,
      "timeout_seconds": 300
    }
  }'
```

---

## Annuler une Mission

```bash
# Annuler une mission en cours
curl -X POST http://localhost:8000/api/v1/missions/{mission_id}/cancel

# Supprimer une mission et ses données
curl -X DELETE http://localhost:8000/api/v1/missions/{mission_id}
```

---

## Dépannage Rapide

### Services ne démarrent pas

```bash
# Vérifier les logs
docker compose logs -f

# Redémarrer les services
docker compose down && docker compose up -d
```

### Mission bloquée

```bash
# Vérifier les logs de l'orchestrateur
docker compose logs orchestrator

# Vérifier l'état de Kafka
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```

### Erreur de connexion

```bash
# Vérifier que tous les services sont UP
docker compose ps

# Tester la connectivité
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8080/health
```

---

## URLs Utiles

| Service | URL | Description |
|---------|-----|-------------|
| UI | http://localhost:3000 | Interface utilisateur |
| GraphQL Playground | http://localhost:8080/graphql | Tester les requêtes |
| Orchestrator Docs | http://localhost:8000/docs | OpenAPI Swagger |
| Graph Service Docs | http://localhost:8001/docs | OpenAPI Swagger |

---

## Prochaines Étapes

1. **Explorer l'UI**: Naviguer dans les différentes vues
2. **Comprendre le graphe**: Étudier les relations entre assets
3. **Analyser les hypothèses**: Examiner les findings de sécurité
4. **Personnaliser**: Adapter les configurations pour vos besoins
5. **Lire la doc complète**: [Architecture](../architecture/overview.md)
