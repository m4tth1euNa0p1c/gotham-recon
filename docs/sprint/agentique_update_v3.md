Voici une **tasklist d’amélioration complète**, avec **instructions**, **tests**, et **mise à jour docs** une fois validé — pensée pour une **review POC** (focus : fiabilité, temps réel, traçabilité, zéro “FAILED fantôme”).

---

# Objectif “POC Review Ready”

1. **UI temps réel fiable** (tasks + graph + logs, sans trous ni doublons)
2. **Orchestrateur = source of truth** (agents réellement visibles, pas de bypass)
3. **Éviter les FAILED après succès** (progress/metrics JSON-safe + tolérance aux erreurs post-run)
4. **Docs v3 complètes** (contrats events, erreurs, modes, exécution tools)

---

# P0 — Must-have (priorité maximale)

## P0.1 Standardiser le contrat d’events (Kafka + SSE/WS)

**Action**

* Définir un **Event Envelope** unique (obligatoire partout) :

  * `event_id` (ULID/UUID), `event_type`, `ts`, `mission_id`
  * `trace_id`, `span_id`, `phase`, `task_id`, `tool_call_id` (quand applicable)
  * `producer`, `payload` (JSON-safe uniquement)

**Acceptance**

* Chaque message sur `mission.state`, `logs.recon`, `graph.events` contient `event_id` + `mission_id` + `event_type` + `ts`.
* `task.started/completed` viennent **uniquement** de l’orchestrateur.

**Tests**

* **Unit**: validation schema (pydantic/jsonschema) pour chaque event.
* **Integration**: lancer une mission → vérifier via consumer que 100% des events ont les champs obligatoires.

---

## P0.2 Idempotence & anti-doublons (Kafka replay + UI)

**Action**

* Ajouter une stratégie de déduplication :

  * côté **Graph Service** : upsert **idempotent** sur `node.id`/`edge.id` déterministes
  * côté **BFF/UI** : mémoriser les `event_id` reçus (cache LRU par mission) + ignorer doublons
* Forcer **IDs déterministes** pour assets ET edges critiques (`edge.id` stable)

**Acceptance**

* Rejouer le même flux Kafka ⇒ **pas de doublons** nodes/edges, et UI stable.

**Tests**

* **Integration**: rejouer N fois un `graph.batch.upsert` identique ⇒ compter nodes/edges constants.
* **UI test**: injecter events doublonnés ⇒ le store n’augmente pas.

---

## P0.3 Fix “FAILED fantôme” (progress JSON-safe + tolérance post-completion)

**Action**

1. Implémenter `make_json_safe(obj)` **récursif** (dict/list/tuple/obj) :

   * convertit objets non sérialisables en string / dict minimal (`{"type": "...", "repr": "..."}`)
2. Appliquer systématiquement **avant** :

   * persistance `mission["progress"]`
   * publish Kafka (payload)
3. Changer la logique d’état :

   * si mission déjà `COMPLETED`, un échec de persistance “progress” **ne doit pas** repasser en `FAILED`
   * log + event `mission.warning` + `error_code=POST_COMMIT_PERSIST_FAIL`

**Acceptance**

* Une mission qui a terminé OK ne peut plus devenir FAILED juste à cause d’une sauvegarde progress.

**Tests**

* **Unit**: `make_json_safe` sur objets CrewAI/complexes imbriqués.
* **Integration**: simuler exception DB au moment update progress après completion ⇒ mission reste COMPLETED.

---

## P0.4 Batch upsert graphe atomique

**Action**

* `graph.batch.upsert(nodes, edges)` doit être **transactionnel** (SQLite) :

  * BEGIN; upsert nodes; upsert edges; COMMIT
  * rollback sur erreur
* Ordre : nodes → edges (garantit edges valides)

**Acceptance**

* Jamais d’état “edges orphelins” visible par l’UI après batch.

**Tests**

* **Integration**: provoquer erreur sur edge (from/to manquant) ⇒ rien n’est écrit.

---

## P0.5 UI “Snapshot + Delta” (modèle officiel temps réel)

**Action**

* Définir règle UI :

  1. **Snapshot** initial via GraphQL/REST (missions + graph minimal)
  2. **Delta** via SSE/WS : events appliqués en temps réel
  3. Reconnexion : envoyer `Last-Event-ID` → serveur renvoie backlog (ou fallback : re-snapshot)

**Acceptance**

* UI affiche la mission complète même si l’utilisateur refresh en plein run.

**Tests**

* **E2E**: démarrer mission → refresh page → UI se resynchronise et reprend en live.

---

# P1 — Fortement recommandé (solidifie le POC)

## P1.1 Failure taxonomy (lisible en review)

**Action**

* Introduire `error_code`, `stage`, `retryable`, `recoverable` dans `task.failed`/`mission.failed`
* Stages standard : `ORCH | AGENT | TOOL | PARSER | DB | KAFKA | GRAPH | UI`

**Tests**

* **Unit**: mapping exception → error_code.
* **Integration**: tool timeout ⇒ `error_code=TOOL_TIMEOUT`, stage TOOL.

---

## P1.2 Execution Map : quels tools via scanner-proxy

**Action**

* Documenter un tableau : `tool → exécuté où → container → timeout → retries → logs`
* Ajouter dans events `tool.started` : champ `executor=orchestrator|scanner-proxy`

**Tests**

* **Integration**: lancer un tool via proxy ⇒ event `tool.started` doit indiquer scanner-proxy.

---

## P1.3 Policies globales (timeout/retry/concurrency)

**Action**

* Définir dans config :

  * timeout par tool + timeout phase + timeout mission
  * retries par tool (max + backoff)
  * concurrency caps par mission/tool (ex: httpx threads vs global limit)

**Tests**

* **Integration**: forcer lenteur ⇒ timeout déclenche event standard + statut correct.

---

# P2 — Bonus (si tu as du temps)

* Outbox pattern (DB → publish Kafka garanti)
* Subscriptions GraphQL pour `missionEvents` et `graphDelta` (plus clean que SSE bricolé)
* Observabilité : OpenTelemetry traces (trace_id/span_id bout-en-bout)

---

# Plan de tests complet (à exécuter avant la review)

## A) Unit tests

* `test_make_json_safe_recursive()`
* `test_event_schema_validation_per_type()`
* `test_deterministic_node_edge_ids()`
* `test_failure_taxonomy_mapping()`

## B) Integration tests (docker-compose)

Scénarios :

1. **Happy path** : mission AGGRESSIVE → COMPLETED, events complets, graph cohérent
2. **Replay** : rejouer events graph → pas de doublons
3. **DB fail post-completion** : mission reste COMPLETED + warning event
4. **Tool timeout** : task failed correctement (stage/tool/error_code)

## C) End-to-end (UI)

* Création mission via UI → timeline tasks se remplit live
* Graph explorer : nodes/edges apparaissent sans clignotement
* Refresh/reconnect : rattrapage snapshot+delta OK

---

# Mise à jour Docs (à faire “une fois validé”)

Créer/mettre à jour dans `docs/v3/` :

1. `events_contract.md`

* Event envelope, event types, champs obligatoires, exemples, ordering, replay

2. `ui_realtime_state_model.md`

* snapshot+delta, reconnexion, last_event_id, dédup UI

3. `failure_taxonomy.md`

* error_code list, stages, exemples

4. `modes_matrix.md`

* STEALTH/BALANCED/AGGRESSIVE : tools activés, intensité, timeouts

5. `execution_map_scanner_proxy.md`

* mapping tool → executor + config

6. `graph_write_guarantees.md`

* atomicité batch, ids déterministes, règles d’upsert/merge

**Acceptance docs**

* Chaque point P0/P1 a une section “contract” + “example” + “test coverage”.

---

# Checklist “Review” (ce que tu peux montrer en démo)

* ✅ Une mission en live avec UI qui affiche : phases + tasks + logs + graph
* ✅ Un replay Kafka ne duplique rien
* ✅ Un échec de persistance progress n’entraîne plus FAILED après COMPLETED
* ✅ Docs : contrats events + erreurs + modes + execution map

Si tu me donnes rapidement les chemins de repo (ou l’arborescence services + noms de topics + endpoints SSE/WS), je peux te sortir une **checklist de commandes exactes** (docker compose + scripts de test + assertions) adaptée à TON layout de projet, sans réécrire ton architecture.
