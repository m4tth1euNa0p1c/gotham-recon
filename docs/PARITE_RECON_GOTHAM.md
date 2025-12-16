# Parité `recon_gotham` (ancien) → Gotham (microservices + UI)

Objectif : répliquer **exactement** le comportement de `recon_gotham/` (prompts, logique, IDs, artefacts `output/` + `knowledge/`) dans l’architecture “nouveau Gotham” (`services/*` + `gotham-ui/`), puis valider la parité sur une mission de référence (`colombes.fr`).

---

## 1) Source de vérité (golden)

Traitez `recon_gotham/` comme **référence canonique**.

**Artefacts de référence disponibles localement :**
- `recon_gotham/output/colombes.fr_asset_graph.json`
- `recon_gotham/output/colombes.fr_summary.md`
- `recon_gotham/output/colombes.fr_20251215_181818_bd0a9354_metrics.json`
- `recon_gotham/knowledge/colombes.fr_summary.md`

**Chiffres “golden” (colombes.fr) :**
- Nodes : **386**
- Edges : **333**
- Types (nodes) :
  - `SUBDOMAIN`: **53**
  - `HTTP_SERVICE`: **11**
  - `ENDPOINT`: **104**
  - `PARAMETER`: **134**
  - `HYPOTHESIS`: **67**
  - `VULNERABILITY`: **12**
  - `ATTACK_PATH`: **5**

> Ces chiffres doivent être atteints (ou expliqués) dans la DB/UI du nouveau Gotham pour la mission `colombes.fr` (à tolérance 0 si vous visez “exactement identique”).

---

## 2) Constat (écarts actuels bloquants)

### 2.1 Schémas d’IDs incohérents entre services

Le nouveau Gotham génère des IDs différents selon les services, ce qui casse :
- la déduplication,
- le chaînage subdomain → http_service → endpoint,
- le scoring (endpoint intel),
- l’export “asset_graph.json” identique.

Exemples observés :
- `services/osint-runner/main.py` : endpoints Wayback en `endpoint:{FULL_URL}`
- `services/active-recon/main.py` : HTTP services en `id = {URL}` (sans préfixe), endpoints parfois `endpoint:{origin}{path}`
- `services/recon-orchestrator/core/graph_client.py` : endpoints en `endpoint:{target_domain}{path}` (collision inter-subdomains)
- `recon_gotham/src/recon_gotham/core/asset_graph.py` (référence) : endpoints en `endpoint:{http:<base_url>}{/path}`

### 2.2 Passive recon différente du moteur `recon_gotham`

Dans `recon_gotham/src/recon_gotham/main.py`, la phase passive est :
- **CrewAI séquentiel** (Pathfinder → Watchtower → DNS → ASN) + outputs JSON stricts (YAML),
- puis **bypass Subfinder direct** + **Wayback** + **gate check** (apex fallback).

Dans `services/recon-orchestrator/core/crew_runner.py`, la “passive” actuelle est majoritairement :
- **tool-only** (Subfinder/Wayback/DNS) avec des **caps** (`[:10]`, `[:20]`, `[:30]`) qui empêchent d’atteindre la couverture de l’ancien.

### 2.3 Types manquants côté `graph-service`

`recon_gotham` utilise des types comme `JS_FILE`, `SECRET`, `BRAND`, `SAAS_APP`, `REPOSITORY`, `LEAK`…  
Mais `services/graph-service/main.py` n’expose pas (encore) tous ces `NodeType`, alors que certains edges existent déjà (`LOADS_JS`, `LEAKS_SECRET`, etc.).

### 2.4 Doublons d’edges → crash Cytoscape

Erreur typique UI :
`Uncaught Error: Can not create second element with ID ...`

Origine la plus fréquente dans ce repo :
- `graph-service` **n’empêche pas** les doublons : `edges_store.append(edge_data)` sans contrainte d’unicité.
- `gotham-ui` peut charger un snapshot contenant des doublons, puis Cytoscape tente d’ajouter 2 fois le même edge ID.

---

## 3) Définition stricte de la parité

### 3.1 Prompts (parité “byte-for-byte”)

Vous devez utiliser **exactement** les prompts historiques :
- `recon_gotham/src/recon_gotham/config/agents.yaml`
- `recon_gotham/src/recon_gotham/config/tasks.yaml`

Règle : **pas de prompts codés en dur** dans les “builders” du nouveau orchestrator (`agent_factory.py`, `task_factory.py`) si l’objectif est la parité stricte.

Recommandation :
- Créer un “prompt pack” versionné (hash SHA-256 du contenu YAML normalisé) et :
  - l’enregistrer dans la mission (`missions.options.prompt_pack_hash`)
  - persister les YAML bruts (table artifacts, ou nœuds `LLM_REASONING` dédiés)

### 3.2 IDs & normalisation (doivent matcher `AssetGraph`)

Adoptez le même schéma d’IDs que `recon_gotham/src/recon_gotham/core/asset_graph.py`.

**IDs (référence)**
- `DOMAIN`: `{target_domain}` (ex: `colombes.fr`)
- `SUBDOMAIN`: `{subdomain}` (ex: `www.colombes.fr`)
- `HTTP_SERVICE`: `http:{base_url}` (ex: `http:https://www.colombes.fr`)
- `ENDPOINT`: `endpoint:{http_service_id}{path}` (ex: `endpoint:http:https://www.colombes.fr/login`)
- `PARAMETER`: `param:{endpoint_id}:{name}`
- `HYPOTHESIS`: `hypothesis:{endpoint_id}:{ATTACK_TYPE}`
- `VULNERABILITY`: conserver la convention historique (ex: `vuln:endpoint:<endpoint_id>:<TYPE>` ou `vuln:<hypothesis_id>`) selon votre source de vuln
- `ATTACK_PATH`: `attack_path:{hash}`
- `JS_FILE`: `js:{url}`
- `SECRET`: `secret:{stable_hash_or_prefix}`
- `DNS_RECORD`: `dns:{TYPE}:{value}` (si vous les matérialisez)
- `IP_ADDRESS`: `ip:{ip}`
- `ASN`: `asn:{asn}`

**Normalisation (obligatoire)**
- Subdomain : lowercasing, strip scheme/port/path, strict scope `endswith(target_domain)`
- Endpoint path :
  - strip query/fragment
  - force leading `/`
  - strip trailing `/` (sauf `/`)
  - ignorer `/.external/` (artefacts Wayback)
- Endpoint origin :
  - `origin` doit être une URL base (scheme+host(+port))
  - le couple (`origin`, `path`) doit permettre de reconstruire `endpoint_id`

### 3.3 Relations/edges

Alignez les relations sur `recon_gotham` (et supportez les alias) :
- `HAS_SUBDOMAIN` : DOMAIN → SUBDOMAIN
- `EXPOSES_HTTP` : SUBDOMAIN → HTTP_SERVICE
- `EXPOSES_ENDPOINT` : HTTP_SERVICE → ENDPOINT
- `HAS_PARAM` (alias `HAS_PARAMETER`) : ENDPOINT → PARAMETER
- `HAS_HYPOTHESIS` : ENDPOINT → HYPOTHESIS
- `AFFECTS_ENDPOINT` / `HAS_VULNERABILITY` : VULNERABILITY ↔ ENDPOINT (selon votre modèle)
- `TARGETS` : ATTACK_PATH → target

---

## 4) Stratégie de portage (recommandée)

### Option A (plus fiable) : “shared core” = réutiliser `recon_gotham` comme librairie

But : éviter une ré-implémentation partielle qui dérive.

1. Extraire `recon_gotham/src/recon_gotham` en package Python partageable (`services/shared/recon_core/` par ex).
2. Dans le pipeline microservices (ou dans `recon-orchestrator`), exécuter **la même orchestration** que `recon_gotham/main.py`.
3. Ajouter un adaptateur “publisher” qui, à chaque mutation de l’AssetGraph, appelle `graph-service` :
   - `POST /api/v1/nodes`
   - `POST /api/v1/edges`
4. En fin de mission, exporter **exactement** :
   - `*_asset_graph.json`
   - `*_summary.md`
   - `*_metrics.json`
   - et persister ces artefacts en DB (voir §6).

### Option B (progressive) : reproduire phase par phase dans les services existants

Plus long et plus risqué : exige une discipline stricte sur les IDs, la normalisation, et l’output.

---

## 5) Plan d’implémentation (écarts → actions)

### 5.1 `graph-service` (indispensable)

1. **Namespacing mission** :
   - aujourd’hui, `nodes_store` est indexé uniquement par `node.id` → collision inter-missions possible.
   - corriger : stocker en mémoire par `(mission_id, node_id)` ou inclure `mission_id` dans la clé interne.

2. **Support NodeType complet** :
   - ajouter les types présents dans `recon_gotham/core/asset_graph.py` (au minimum `JS_FILE`, `SECRET`, `BRAND`, `SAAS_APP`, `REPOSITORY`, `LEAK`).

3. **Déduplication edges** :
   - contrainte d’unicité logique `(mission_id, from_node, relation, to_node)`
   - ignorer un insert si déjà présent (ou retourner 200 “exists”).

### 5.2 `osint-runner` (parité passive)

1. Reproduire la **séquence** `recon_gotham` :
   - Subfinder direct bypass
   - Watchtower (LLM) : tags/priority/category/reason (no hallucinations)
   - DNS enrichment + injection (A/AAAA/MX/TXT…) avec edges (`HAS_RECORD`, `RESOLVES_TO`)
   - ASN enrichment (si implémenté)
   - Wayback : endpoints normalisés + chaînage `SUBDOMAIN → HTTP_SERVICE → ENDPOINT`
   - gate check + apex fallback + probes (optionnel)

2. Corriger l’ID endpoint Wayback :
   - ne pas utiliser `endpoint:{FULL_URL}`
   - utiliser `endpoint:http:{base_url}{path}` et créer l’HTTP_SERVICE si absent.

### 5.3 `active-recon` (parité active)

1. HTTP_SERVICE id : adopter `http:{url}` (et non `id=url`)
2. Créer systématiquement :
   - `EXPOSES_HTTP` (SUBDOMAIN → HTTP_SERVICE)
   - `EXPOSES_ENDPOINT` (HTTP_SERVICE → ENDPOINT)
3. Endpoints HTML/JS :
   - stocker `path` normalisé, `origin` base_url, `source` stable (`HTML_CRAWL`, `JS`, etc.)
4. Si vous publiez `JS_FILE` / `SECRET`, vous devez d’abord étendre `graph-service` (NodeType).

### 5.4 `endpoint-intel` (parité Phase 23B)

1. Hypothèses et paramètres doivent être générés à partir de `origin` + `path` corrects.
2. Utiliser `HAS_PARAM` (ou écrire les deux alias) si vous voulez matcher l’export `recon_gotham`.

### 5.5 `verification` + `planner` + `reporter`

Objectif : produire les mêmes nœuds/edges et le même contenu de rapports que `recon_gotham` :
- `ATTACK_PATH` identiques (hash stable)
- `VULNERABILITY` avec propriétés (type, confidence, status, endpoint_id, etc.)
- `reports/<domain>_red_team_report.md` (ou un artefact équivalent) + `*_summary.md`

---

## 6) Stockage des artefacts (`output/` + `knowledge/`) en DB et exposition API

Pour la parité, vous devez persister et exposer au moins :
- `asset_graph.json` (format identique au CLI)
- `summary.md` (format identique)
- `metrics.json` (format identique)
- logs structurés (optionnel)
- prompt pack (agents/tasks YAML) + hash

Recommandation : ajouter une table `mission_artifacts` (ou équivalent) :
- `mission_id`
- `artifact_type` (ex: `asset_graph_json`, `summary_md`, `metrics_json`, `prompt_pack`)
- `content` (TEXT/BLOB)
- `created_at`

Puis exposer via BFF/UI :
- `GET /api/v1/missions/{mission_id}/artifacts`
- `GET /api/v1/missions/{mission_id}/artifacts/{artifact_type}`

UI : afficher `summary.md` (ou struct équivalente) dans `gotham-ui/src/components/assets/AIReportDrawer.tsx` et permettre surlignage des nœuds mentionnés.

---

## 7) Procédure de validation de parité (colombes.fr)

### 7.1 Export “golden”

Utiliser :
- `recon_gotham/output/colombes.fr_asset_graph.json`
- `recon_gotham/output/colombes.fr_summary.md`
- `recon_gotham/output/colombes.fr_20251215_181818_bd0a9354_metrics.json`

### 7.2 Exécuter une mission “nouveau Gotham”

1. Lancer la mission `colombes.fr` depuis l’UI ou via l’orchestrator.
2. Récupérer `mission_id`.
3. Exporter le graphe depuis `graph-service` (REST) :
   - `GET /api/v1/missions/{mission_id}/export`
   - `GET /api/v1/missions/{mission_id}/stats`

### 7.3 Comparer

Comparer au minimum :
- `total_nodes`, `total_edges`
- distribution `nodes_by_type`
- échantillons d’IDs : endpoints, params, hypotheses, vulns
- présence des edges clés : `EXPOSES_HTTP`, `EXPOSES_ENDPOINT`, `HAS_PARAM`, `HAS_HYPOTHESIS`

Critère “OK” (parité stricte) :
- mêmes counts,
- mêmes IDs,
- mêmes propriétés minimales (origin/path/source/category/risk/…),
- mêmes artefacts `summary.md` et `metrics.json`.

---

## 8) Debug : vérifier que les LLM sont réellement utilisés

Dans `recon_gotham`, le LLM est requis pour les crews (phases passive/active). Le pipeline continue quand même via bypass si le crew échoue.

Dans le nouveau Gotham :
- Si vous êtes en mode “services” (osint-runner/active-recon/endpoint-intel), le LLM peut être absent (heuristiques only) sauf si vous ajoutez Watchtower/planning via CrewAI.
- Si vous êtes en mode `USE_CREWAI=true` dans `recon-orchestrator`, vérifiez :
  - `/api/v1/llm/status`
  - logs “LLM_CALL” et durées de phases

---

## 9) Grafana : visualiser Gotham

État actuel : `infra/prometheus/prometheus.yml` scrappe `/health` (pas encore `/metrics`).

Pour une observabilité “complète” :
1. Ajouter `/metrics` (Prometheus) sur chaque service FastAPI (ex: `prometheus-fastapi-instrumentator`).
2. Exposer des métriques métier :
   - missions : count par status, durée, erreurs
   - graph : nodes/edges par mission, croissance (events/s)
   - tools : durées par tool, taux d’échec
   - LLM : tokens, latence, erreurs
3. Créer des dashboards Grafana :
   - Mission Overview (RUNNING/FAILED/COMPLETED)
   - Graph Growth (nodes/edges over time)
   - Tool Performance (p95 durations)
   - LLM Usage (tokens/min)

---

## 10) Annexe : erreur Cytoscape “second element with ID”

Cette erreur signifie que l’UI tente d’ajouter deux fois un nœud/edge avec le même `data.id`.

Causes typiques dans ce repo :
- edges dupliquées en DB (pas de contrainte dans `graph-service`)
- snapshot UI non dédupliqué au chargement initial

Correctifs recommandés :
- côté `graph-service` : refuser les doublons `(mission_id, from, rel, to)`
- côté `gotham-ui` : dédupliquer `snapshot.edges` dans `useGraphStore.fetchGraph()` avant de set le state

