  ---
  Analyse du Workflow Agentic-Recon - Données et Patterns

  Modèle de Données (Knowledge Graph)

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        ASSET GRAPH (Central Store)                       │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  NODE TYPES:                                                            │
  │  ├── DOMAIN → SUBDOMAIN → HTTP_SERVICE → ENDPOINT → PARAMETER          │
  │  │                                       └───────→ HYPOTHESIS           │
  │  │                                       └───────→ VULNERABILITY        │
  │  ├── IP_ADDRESS → ASN                                                   │
  │  ├── DNS_RECORD                                                         │
  │  ├── ATTACK_PATH ──targets──→ [target_node]                            │
  │  └── ORG → SAAS_APP, BRAND, REPOSITORY, LEAK                           │
  │                                                                         │
  │  EDGE TYPES: HAS_SUBDOMAIN, RESOLVES_TO, SERVES, EXPOSES_HTTP,         │
  │              EXPOSES_ENDPOINT, HAS_PARAM, HAS_HYPOTHESIS, TARGETS       │
  └─────────────────────────────────────────────────────────────────────────┘

  Flux de Données par Phase

  | Phase | Pipeline              | Input       | Output                  | Enrichments                                 |
  |-------|-----------------------|-------------|-------------------------|---------------------------------------------|
  | 1     | OsintPipeline         | domain      | subdomains, DNS, IPs    | source, priority, tag                       |
  | 2     | SafetyNetPipeline     | graph_stats | gate_decision           | should_continue, message                    |
  | 3     | ReconPipeline         | subdomains  | HTTP_SERVICE, endpoints | status_code, technologies, title            |
  | 4     | EndpointIntelPipeline | endpoints   | enriched_endpoints      | category, risk_score, params, hypotheses    |
  | 5     | VerificationPipeline  | candidates  | vulnerabilities         | stack_info, test_signals, theoretical_vulns |
  | 6     | ReportingService      | graph       | reports                 | summary.md, graph.json, metrics.json        |

  ---
  Prompt Instruction Complet - Architecture Cible

  # MISSION: Conception Architecture Microservices pour Plateforme de Reconnaissance Offensive

  ## CONTEXTE
  Tu dois concevoir une architecture distribuée pour une plateforme de reconnaissance automatisée
  qui orchestre des agents spécialisés, collecte des données multi-sources, et produit des rapports
  d'attaque. L'architecture doit supporter:
  - Ingestion de données async (subdomains, DNS, HTTP, endpoints)
  - Knowledge Graph central (noeuds: 12 types, edges: 10 relations)
  - Pipeline d'enrichissement multi-phase (6 phases, ~50KB de logique)
  - Scoring de risque temps réel (likelihood × impact = 0-100)
  - Validation contrôlée avec backoff/circuit-breaker

  ## SECTION 1: Vue Cible Front → BFF → Gateway → Mesh → Services

  ### Prompt
  Produis une architecture en séquence complète:
  1. **Front (Dashboard React/Vue)** → Visualisation du graph, contrôle de mission
  2. **BFF/GraphQL** → Agrégation des queries graph, persisted queries pour nodes/edges
  3. **API Gateway** → Rate-limit, auth JWT/OIDC, routing vers services
  4. **Service Mesh** → mTLS inter-services, retries, circuit-breaker
  5. **Microservices Backend**:
     - `recon-orchestrator` (CQRS write): Pilotage missions, état graph
     - `graph-query-service` (CQRS read): Lecture graph, search
     - `pipeline-runner` (async): Exécution phases 1-6
     - `scanner-proxy` (gRPC): Interface Subfinder/HTTPX/Nuclei
     - `report-builder` (batch): Génération rapports

  ### Livrables Attendus
  - [ ] Diagramme Mermaid sequence (Front → BFF → Gateway → Mesh → Services)
  - [ ] Liste des flux critiques avec latency budget (max 2-3s E2E)
  - [ ] Points d'observation (traces/metrics/logs) à chaque hop

  ### Ask de Test
  - Chaque hop a-t-il auth (OIDC/JWT)?
  - TLS partout (mTLS mesh)?
  - Point d'observation indiqué (OpenTelemetry span)?

  ---

  ## SECTION 2: Découpage Domaines et Microservices

  ### Prompt
  Liste les domaines métiers et 5-8 microservices. Pour chaque:
  - Responsabilité unique (SRP)
  - API externe (OpenAPI 3.1 ou GraphQL schema)
  - Events émis/consommés (topic Kafka/NATS)
  - Idempotence (clé unique) et versioning (v1, v2)

  ### Mapping au Workflow Existant
  | Service | Module Existant | Responsabilité |
  |---------|-----------------|----------------|
  | `recon-orchestrator` | orchestrator.py, main.py | Démarrage mission, coordination phases |
  | `graph-service` | asset_graph.py | CRUD graph, scope filtering |
  | `osint-runner` | osint_pipeline.py | Phase 1 passive (Subfinder, DNS) |
  | `active-recon` | recon_pipeline.py | Phase 3 active (HTTPX, crawl) |
  | `endpoint-intel` | endpoint_intel_pipeline.py | Phase 4 enrichissement (heuristics) |
  | `verification` | verification_pipeline.py | Phase 5 validation (tests contrôlés) |
  | `planner` | planner.py | Scoring paths, suggestion actions |
  | `reporter` | reporting_service.py | Génération .md/.json |

  ### Livrables Attendus
  - [ ] Tableau services avec contrats/responsabilités
  - [ ] Schema d'events (NodeCreated, EndpointEnriched, MissionCompleted)
  - [ ] Stratégie versioning API

  ### Ask de Test
  - Aucun service n'est à la fois read ET write (CQRS)?
  - Chaque API est versionnée?
  - Idempotency token sur les writes?

  ---

  ## SECTION 3: Contrat BFF/GraphQL

  ### Prompt
  Définis le contrat BFF/GraphQL pour la consommation du graph:

  ```graphql
  type Query {
    # Graph Queries
    mission(id: ID!): Mission
    subdomains(missionId: ID!, filter: SubdomainFilter): [Subdomain!]!
    endpoints(filter: EndpointFilter, pagination: Pagination): EndpointConnection!
    attackPaths(missionId: ID!, top: Int = 5): [AttackPath!]!

    # Search
    searchNodes(query: String!, types: [NodeType!]): [Node!]!
  }

  type Mutation {
    startMission(input: MissionInput!): Mission!
    cancelMission(id: ID!): Boolean!
    triggerPhase(missionId: ID!, phase: PhaseType!): PipelineResult!
  }

  type Subscription {
    missionProgress(id: ID!): MissionEvent!
    nodeUpdates(missionId: ID!): NodeUpdate!
  }

  Livrables Attendus

  - Schema GraphQL complet (types, inputs, enums)
  - Plan DataLoader (batch subdomain→http_services, endpoint→params)
  - Persisted queries exemples (top10_risky_endpoints, attack_plan)
  - Cache policies (TTL/ETag par type: PUBLIC 5m, per-user 1m)

  Ask de Test

  - Anti N+1 (dataloaders pour relations 1:N)?
  - Cache scope défini (public vs per-user)?
  - Persisted queries pour queries fréquentes?

  ---
  SECTION 4: Gateway + Mesh Policies

  Prompt

  Spécifie les policies Gateway + Service Mesh:

  # Istio VirtualService Example
  apiVersion: networking.istio.io/v1beta1
  kind: VirtualService
  metadata:
    name: recon-gateway
  spec:
    hosts:
    - api.recon.local
    http:
    - match:
      - uri:
          prefix: /graphql
      route:
      - destination:
          host: bff-service
          port:
            number: 8080
      timeout: 3s
      retries:
        attempts: 2
        perTryTimeout: 1s
        retryOn: 5xx,reset,connect-failure

  ---
  # DestinationRule - Circuit Breaker
  apiVersion: networking.istio.io/v1beta1
  kind: DestinationRule
  metadata:
    name: graph-service-cb
  spec:
    host: graph-service
    trafficPolicy:
      connectionPool:
        http:
          h2UpgradePolicy: UPGRADE
          http1MaxPendingRequests: 100
          http2MaxRequests: 1000
      outlierDetection:
        consecutive5xxErrors: 5
        interval: 30s
        baseEjectionTime: 30s
        maxEjectionPercent: 50

  Livrables Attendus

  - Rate-limit config (100 req/s global, 10 req/s par user)
  - JWT validation policy (issuer, audience, claims mapping)
  - mTLS strict mode
  - Timeout budget: 3s total, 1s per-retry

  Ask de Test

  - Budget timeout unique (2-3s)?
  - Backoff pour retries (exponential)?
  - Circuit-breaker sur 5xx ET timeouts?

  ---
  SECTION 5: Transport gRPC Service-to-Service

  Prompt

  Contrat gRPC pour les appels low-latency entre services:

  syntax = "proto3";
  package recon.scanner;

  service ScannerProxy {
    // Subdomain enumeration
    rpc RunSubfinder(SubfinderRequest) returns (stream SubdomainResult);

    // HTTP probing
    rpc ProbeHttp(ProbeRequest) returns (ProbeResponse);

    // Nuclei scan (idempotent)
    rpc RunNucleiScan(NucleiRequest) returns (stream ScanFinding);
  }

  message SubfinderRequest {
    string domain = 1;
    int32 timeout_seconds = 2;
    string idempotency_key = 3;  // Required for retry safety
  }

  message ProbeRequest {
    repeated string urls = 1;
    int32 concurrency = 2;
    google.protobuf.Duration deadline = 3;  // Client deadline
  }

  message NucleiRequest {
    string target_url = 1;
    repeated string template_ids = 2;
    string idempotency_key = 3;
    ScanMode mode = 4;

    enum ScanMode {
      STEALTH = 0;
      AGGRESSIVE = 1;
    }
  }

  Livrables Attendus

  - Proto files (scanner.proto, graph.proto)
  - Deadlines guidelines (30s subfinder, 5s probe, 60s nuclei)
  - Idempotency tokens sur toutes les méthodes d'écriture

  Ask de Test

  - Idempotency key sur writes?
  - Deadline explicite dans chaque request?
  - Streaming pour opérations longues?

  ---
  SECTION 6: Accès Données (CQRS, Cache, Replicas)

  Prompt

  Définis l'architecture data:

  | Path        | Store              | Pattern        | Latency Target |
  |-------------|--------------------|----------------|----------------|
  | Graph Write | PostgreSQL Primary | CQRS Command   | <100ms         |
  | Graph Read  | PostgreSQL Replica | CQRS Query     | <50ms          |
  | Hot Cache   | Redis Cluster      | Cache-Aside    | <10ms          |
  | Search      | Elasticsearch      | Index          | <100ms         |
  | Events      | Kafka              | Event Sourcing | <50ms          |

  Modèle de Données PostgreSQL

  -- Nodes table (JSON properties for flexibility)
  CREATE TABLE nodes (
    id VARCHAR(255) PRIMARY KEY,
    mission_id UUID NOT NULL,
    type VARCHAR(50) NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
  );

  -- Edges table
  CREATE TABLE edges (
    id SERIAL PRIMARY KEY,
    mission_id UUID NOT NULL,
    from_node VARCHAR(255) REFERENCES nodes(id),
    to_node VARCHAR(255) REFERENCES nodes(id),
    relation VARCHAR(50) NOT NULL,
    UNIQUE(mission_id, from_node, to_node, relation)
  );

  -- Indexes for graph traversal
  CREATE INDEX idx_nodes_mission_type ON nodes(mission_id, type);
  CREATE INDEX idx_edges_from ON edges(from_node);
  CREATE INDEX idx_edges_to ON edges(to_node);

  Cache Invalidation

  | Event            | Invalidation Action                 |
  |------------------|-------------------------------------|
  | NodeCreated      | Purge nodes:mission:{id}:*          |
  | EndpointEnriched | Purge endpoints:{id}, Update TTL 5m |
  | MissionCompleted | Full invalidation mission scope     |

  Livrables Attendus

  - Schema PostgreSQL avec indexes
  - TTL cache par type (nodes: 5m, metrics: 1m, reports: 1h)
  - Règles d'invalidation event-driven

  Ask de Test

  - Aucune écriture via replicas?
  - Event → cache purge automatique?
  - TTL explicite pour chaque type?

  ---
  SECTION 7: Messaging et Events (Kafka)

  Prompt

  Liste des topics et schemas:

  | Topic             | Schema (Avro) | Producers      | Consumers             | DLQ | Retention |
  |-------------------|---------------|----------------|-----------------------|-----|-----------|
  | mission.started   | MissionEvent  | orchestrator   | all                   | ✓   | 7d        |
  | node.created      | NodeEvent     | graph-service  | intel, reporter       | ✓   | 3d        |
  | endpoint.enriched | EndpointEvent | endpoint-intel | verification, planner | ✓   | 3d        |
  | scan.completed    | ScanEvent     | scanner-proxy  | active-recon          | ✓   | 1d        |
  | mission.completed | MissionEvent  | orchestrator   | reporter              | ✓   | 7d        |

  Schema Avro Exemple

  {
    "type": "record",
    "name": "NodeEvent",
    "namespace": "recon.events",
    "fields": [
      {"name": "event_id", "type": "string"},
      {"name": "event_type", "type": {"type": "enum", "name": "EventType", "symbols": ["CREATED", "UPDATED", "DELETED"]}},
      {"name": "mission_id", "type": "string"},
      {"name": "node_id", "type": "string"},
      {"name": "node_type", "type": "string"},
      {"name": "properties", "type": {"type": "map", "values": "string"}},
      {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"}
    ]
  }

  Livrables Attendus

  - Table topics avec schemas versionnés
  - DLQ pour chaque topic
  - Retry policy (3 attempts, exponential backoff)
  - SLA latence (p99 < 500ms)

  Ask de Test

  - DLQ pour chaque topic?
  - TTL message défini?
  - Schema versionné (v1, v2)?

  ---
  SECTION 8: Optimisation Front

  Prompt

  Plan de performance frontend:

  | Technique         | Implementation                | Impact           |
  |-------------------|-------------------------------|------------------|
  | Persisted Queries | Hash des queries GraphQL      | -50% payload     |
  | Batching          | DataLoader côté BFF           | -80% round-trips |
  | HTTP/2            | TLS 1.3 + ALPN                | Multiplexing     |
  | Compression       | brotli (br) > gzip            | -30% size        |
  | CDN               | Static assets + GraphQL cache | -100ms TTFB      |
  | Code Splitting    | React.lazy() per route        | -40% initial JS  |
  | Images            | WebP/AVIF + srcset            | -60% images      |

  Headers Cache

  # Static assets
  Cache-Control: public, max-age=31536000, immutable
  ETag: "abc123"

  # GraphQL responses (per-user)
  Cache-Control: private, max-age=60
  Vary: Authorization

  # Graph data (public)
  Cache-Control: public, max-age=300
  ETag: "graph-v1234"

  Livrables Attendus

  - Checklist front (bundle < 200KB gzip, TTFB < 500ms)
  - Persisted queries mapping
  - CDN config (origins, cache rules)

  Ask de Test

  - Persisted queries activées?
  - Cache-Control/ETag sur toutes ressources?
  - Bundle size < 200KB gzip?

  ---
  SECTION 9: Performance Backend

  Prompt

  Optimisations runtime:

  # Connection Pool (per service)
  database:
    pool:
      min: 5
      max: 20
      acquire_timeout: 10s
      idle_timeout: 300s
    prepared_statements: true

  # Redis Pool
  redis:
    pool:
      min: 2
      max: 10
    timeout: 2s

  # HTTP Client
  http_client:
    timeout: 10s
    max_connections: 100
    max_connections_per_host: 10
    keepalive: true

  Checklist Runtime

  - Pooling DB dimensionné (min/max)
  - Prepared statements activés
  - Timeout par hop (2s service, 10s external)
  - Back-pressure (queue max size, reject policy)
  - Bulk operations (batch inserts nodes)
  - N+1 éliminés (dataloader pattern)
  - Quotas par client (rate-limit header)

  Ask de Test

  - Timeout par hop défini?
  - Pool DB dimensionné?
  - Prepared statements activés?

  ---
  SECTION 10: Observabilité

  Prompt

  Plan d'observabilité complet:

  | Service       | SLI                 | SLO   | Error Budget |
  |---------------|---------------------|-------|--------------|
  | orchestrator  | latency p99 < 500ms | 99.5% | 0.5%         |
  | graph-service | latency p99 < 100ms | 99.9% | 0.1%         |
  | scanner-proxy | success rate        | 95%   | 5%           |
  | bff           | error rate < 1%     | 99%   | 1%           |

  OpenTelemetry Config

  # Trace sampling
  sampling:
    parent_based:
      root:
        type: probabilistic
        sampling_ratio: 0.1  # 10% in prod

  # Metrics
  metrics:
    - name: recon_mission_duration_seconds
      type: histogram
      labels: [mission_id, mode, status]
    - name: recon_nodes_total
      type: counter
      labels: [mission_id, node_type]
    - name: recon_scan_errors_total
      type: counter
      labels: [scanner, error_type]

  # Logs (structured JSON)
  log_format: |
    {
      "timestamp": "%timestamp%",
      "level": "%level%",
      "service": "%service%",
      "trace_id": "%trace_id%",
      "span_id": "%span_id%",
      "message": "%message%",
      "context": %context%
    }

  Livrables Attendus

  - Tableau SLI/SLO par service
  - Plan sampling traces (10% prod, 100% errors)
  - Format logs JSON structuré
  - Alertes sur error budget

  Ask de Test

  - Au moins 2 SLI (latence, erreur) par service?
  - Error budget défini?
  - Trace sampling configuré?

  ---
  SECTION 11: Sécurité et CI/CD

  Prompt

  Cadre sécurité et pipeline:

  Security Checklist

  - mTLS mesh (Istio strict mode)
  - JWT validation (RS256, exp check, audience)
  - RBAC: roles (viewer, operator, admin)
  - Input validation (JSON Schema sur GraphQL)
  - Secrets en Vault (DB creds, API keys)
  - WAF (OWASP rules, rate-limit)

  CI/CD Pipeline

  stages:
    - lint
    - test
    - sast
    - build
    - dast
    - deploy-staging
    - contract-test
    - canary
    - deploy-prod

  gates:
    sast:
      tool: semgrep
      fail_on: high,critical
    dast:
      tool: zap
      fail_on: high
    canary:
      duration: 15m
      error_threshold: 1%
      auto_rollback: true

  Livrables Attendus

  - Checklist sécurité
  - Pipeline CI/CD avec gates
  - Canary config (duration, threshold, rollback)

  Ask de Test

  - SAST ET DAST dans pipeline?
  - Gate canary avec rollback automatique?
  - Secrets pas en plaintext?

  ---
  ROADMAP IMPLEMENTATION

  Sprint 1 (Foundation)
  ├── Modéliser domaines et services (Section 2)
  ├── Schema PostgreSQL + migrations
  └── Proto files gRPC

  Sprint 2 (Core Services)
  ├── graph-service (CQRS)
  ├── orchestrator (workflow)
  └── Kafka topics + schemas

  Sprint 3 (Gateway Layer)
  ├── Gateway + Mesh policies (Section 4)
  ├── BFF/GraphQL (Section 3)
  └── Auth JWT/OIDC

  Sprint 4 (Data Layer)
  ├── Redis cache + invalidation
  ├── Elasticsearch indexing
  └── Replicas setup

  Sprint 5 (Observability)
  ├── OpenTelemetry integration
  ├── SLI/SLO dashboards
  └── Alerting rules

  Sprint 6 (Frontend + CI/CD)
  ├── Dashboard React
  ├── Persisted queries
  └── Full pipeline CI/CD

  ---
  VALIDATION FINALE

  Avant de valider l'architecture:

  1. Chaque service a un owner et une API documentée
  2. Tous les flux ont un timeout budget < 3s
  3. mTLS activé entre tous les services
  4. Cache invalidation event-driven
  5. SLI/SLO définis avec error budget
  6. Pipeline CI/CD avec SAST/DAST et canary
  7. Pas de secrets en plaintext
  8. Persisted queries pour GraphQL
  9. DataLoaders pour éliminer N+1
  10. Idempotency keys sur toutes les écritures

  ---

  Ce prompt complet:
  1. **Mappe** directement les modules existants (`asset_graph.py`, `planner.py`, etc.) vers les microservices cibles
  2. **Conserve** le modèle de données (NodeTypes, EdgeTypes, risk scoring)
  3. **Formalise** les patterns existants (pipelines, phases, enrichissement)
  4. **Ajoute** les couches manquantes (Gateway, Mesh, Cache, Observability)
  5. **Fournit** des Ask de Test pour chaque section

● Agent "Explore recon-gotham architecture" completed.

● Task Output(non-blocking) a66ad1d
  ⎿  Read output (ctrl+o to expand)

● L'analyse est complète. Voici ce que j'ai livré:

  Résumé de la Livraison

  1. Analyse du Workflow Existant

  - 12 Types de Noeuds: DOMAIN, SUBDOMAIN, HTTP_SERVICE, ENDPOINT, PARAMETER, HYPOTHESIS, VULNERABILITY, ATTACK_PATH, IP_ADDRESS, DNS_RECORD, ASN, ORG/BRAND/SAAS_APP/LEAK
  - 10 Types de Relations: HAS_SUBDOMAIN, RESOLVES_TO, SERVES, EXPOSES_HTTP, EXPOSES_ENDPOINT, HAS_PARAM, HAS_HYPOTHESIS, HAS_VULNERABILITY, TARGETS
  - 6 Phases Pipeline: OSINT → Safety Net → Active Recon → Endpoint Intel → Verification → Reporting
  - Risk Scoring: likelihood (0-10) × impact (0-10) = risk (0-100)

  2. Prompt Complet Structuré

  | Section            | Contenu                                 | Ask de Test                     |
  |--------------------|-----------------------------------------|---------------------------------|
  | 1. Vue Cible       | Front→BFF→Gateway→Mesh→Services         | Auth/TLS/Observabilité par hop  |
  | 2. Microservices   | 8 services mappés aux modules existants | CQRS, versioning, idempotence   |
  | 3. BFF/GraphQL     | Schema complet + DataLoaders + Cache    | Anti N+1, persisted queries     |
  | 4. Gateway/Mesh    | Policies Istio YAML                     | Timeout budget, circuit-breaker |
  | 5. gRPC            | Proto files scanner.proto               | Deadlines, idempotency keys     |
  | 6. Data            | PostgreSQL + Redis + ES + Kafka         | Invalidation event-driven       |
  | 7. Messaging       | Topics Kafka + schemas Avro             | DLQ, retry, versioning          |
  | 8. Front Perf      | CDN, code-splitting, compression        | <200KB gzip, TTFB <500ms        |
  | 9. Backend Perf    | Pooling, prepared statements            | Timeout par hop                 |
  | 10. Observabilité  | SLI/SLO/Error budget par service        | OpenTelemetry traces            |
  | 11. Sécurité/CI/CD | SAST/DAST, canary, mTLS                 | Rollback automatique            |

  3. Mapping Modules → Microservices

  asset_graph.py      → graph-service (CQRS)
  orchestrator.py     → recon-orchestrator
  osint_pipeline.py   → osint-runner
  recon_pipeline.py   → active-recon
  endpoint_intel.py   → endpoint-intel
  verification.py     → verification
  planner.py          → planner
  reporting_service   → reporter

  Le prompt est prêt à être utilisé pour guider la conception de l'architecture cible avec tous les éléments de validation (Ask de Test) intégrés.