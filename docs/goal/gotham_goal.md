Voici une version **améliorée et complétée** de ton cahier des charges ReconRTF, intégrant tes apprentissages actuels (Recon-Gotham V3.0) + les meilleures pratiques red‑team / black‑hat contrôlées :

***

# 🚀 Cahier des Charges — ReconRTF V4.0

### *Reconnaissance Contextuelle Agentique, Graphée & Opérationnelle*

***

## 1. 🎯 Vision et Philosophie Étendue

### **Mantra Principal : "Recon is Context, Exploitation is Science, Operations is Art."**

ReconRTF n'est **pas** un wrapper autour de Subfinder ou HTTPX.

C'est un **système cognitif d'opérations de sécurité autonomes**, construit comme un **ensemble d'agents autonomes spécialisés**, capables d':
- **interpréter** le contexte offensif d'une cible,
- **raisonner** en termes de chemins d'attaque complets (MITRE ATT&CK),
- **prioriser** comme un vrai analyste Red Team expérimenté,
- **opérer** de façon contrôlée avec audit trail et reproducibilité.

### Objectifs :

➡️ **Comprendre l'architecture de l'adversaire** (infra, stack, dépendances, risques métier).  
➡️ **Identifier les vecteurs d'attaque les plus rentables** (chemins critiques, pivots, chaînes).  
➡️ **Générer des scénarios exploitables** (TTP, POCs, playbooks).  
➡️ **Optimiser le temps humain** (décisions automatisées, hiérarchisation, reporting).  
➡️ **Rester opérationnel et légal** (opsec, audit trail, budget contrôlé, scope strict).

***

## 2. 🧠 Architecture Générale (Agentic Workflow V4)

ReconRTF repose sur **quatre blocs hiérarchisés** :

```
┌─────────────────────────────────────────────────────────┐
│         MISSION CONTROLLER (Orchestration)              │
│   (Décisions strategiques, allocation d'agents)        │
└────────────┬──────────────────────┬────────────────────┘
             │                      │
       ┌─────▼─────┐        ┌──────▼──────┐
       │ RECON     │        │ OPERATIONS  │
       │ PIPELINE  │        │ PIPELINE    │
       └─────┬─────┘        └──────┬──────┘
             │                      │
       ┌─────▼────────────────────────▼──────┐
       │    ASSET GRAPH (Base de connaissances) │
       │    + TTP Graph + Exploit Registry     │
       └───────────────────────────────────────┘
             │
       ┌─────▼────────────────────────────────┐
       │   WORKERS (Agents spécialisés)       │
       │   + Tools (outils externes)          │
       │   + LLM (local + optional cloud)     │
       └───────────────────────────────────────┘
```

### 2.1 Mission Controller (Orchestrateur Central V2)

**Responsabilités :**
- Prend les décisions de haut niveau (scope, budget, TTP autorisés).
- Gère l'ordre d'appel des pipelines (passive → active → validation → exploitation).
- Interprète les résultats et alimente le graphe d'actifs + TTP graph.
- Déclenche les agents actifs **uniquement sur les cibles pertinentes et autorisées**.
- Maintient un **engagement profile** (pro audit vs red team black‑box).
- Gère les fallbacks et retry logic (dont code_smith en cas d'outil défaillant).

**Entrée :** Domaine / Organisation cible + profil d'engagement (Profile enum)  
**Sortie :** AssetGraph priorisé + TTP graph + liste d'actions exploitables + playbooks

### 2.2 Recon Pipeline (Existant + Améliorations)

Phases 1–25 comme actuellement, **mais** :
- Ajouter un gate "OPSEC Check" après Phase 23 (vérifie que les tests prévus respectent le budget/scope/profil).
- Brancher code_smith comme fallback systématique si un outil échoue (avec logging + audit).
- Enrichir le planner pour générer des **TTP‑aware attack paths** (liens MITRE ATT&CK).

### 2.3 Operations Pipeline (NOUVEAU)

Phases 26–30 : transition recon → exploitation / mouvement

**Phase 26 — Exploitation Orchestration**
- Sélectionner les cibles critiques du Planner.
- Générer des playbooks d'exploitation (qui ne lancent rien sans validation).
- Produire des POCs templates (Burp scripts, curl, Python).

**Phase 27 — Post‑Exploitation & Pivot**
- Modéliser les "pivot points" (VPN, bastions, comptes critiques) découverts en recon.
- Suggérer des chemins de mouvement (mouvement latéral, escalade priv).
- Évaluer la criticité métier des ressources (données, services, infra).

**Phase 28 — Coverage & Completeness**
- Vérifier que la recon couvre tous les chemins d'attaque probables.
- Identifier les zones "grises" (endpoints non testés, techos mal connues, segments isolés).

**Phase 29 — Proof & Remediation**
- Produire les artefacts de preuve (captures, logs, dumps anonymisés si besoin).
- Proposer des mesures de remédiation priorisées.

**Phase 30 — Reporting & Handover**
- Générer des rapports multi‑formats (management, technique, playbook).
- Créer un "runbook" pour reproduire les chemins d'attaque (audit trail).

***

## 3. 🤖 Agents Spécialisés (Mapping ReconRTF → V4)

***

## 🟢 **Phase 1 — Découverte Intelligente**

### 🔹 **Agent 1 — The Profiler**

**Objectif :** Subdomain Enumeration + Intelligence Sémantique

**Outils :** Subfinder (Docker), Amass (passif), CT logs (public), Certificate API.

**Comportement agentique :**
- Analyse sémantique des noms de sous-domaines (NLP via Qwen local ou patterns regex).
- Détection d'environnements parallèles (dev ↔ prod, staging, UAT, internal).
- Détection patterns CI/CD (jenkins, gitlab, argocd, github actions endpoints).
- Détection d'orga tierces (CDN, services de mail, hébergement, SaaS).
- **Score d'intérêt (1–10) par sous-domaine** + catégorie (OFFICIAL, INTERNAL, DEV, LEGACY, EXTERNAL_SAAS).
- **Mapping vers MITRE ATT&CK** : découverte = Reconnaissance/Active Scanning (T1595).

**Output :**
```json
{
  "subdomains": [
    {
      "name": "dev-api.example.com",
      "category": "INTERNAL_DEV",
      "score": 9,
      "environment": "development",
      "inference": "Found via subdomain enumeration + CT logs",
      "mitre_ttp": "T1595.003 (Search Open Websites/Domains)"
    }
  ]
}
```

***

### 🔹 **Agent 1b — The Infrastructure Mapper** (NOUVEAU)

**Objectif :** Enrichissement infra (ASN, netblocks, hosting, hébergement physique).

**Outils :** WHOIS, MaxMind, BGP data, Shodan API (read-only).

**Comportement :**
- Pivot ASN/Netblocks (toutes les IPs du groupe).
- Détection hébergement (AWS, GCP, OVH, providers, datacenters).
- Enrichissement géolocalisation + juridiction (pour opsec/compliance).
- Détection shared hosting / VPS risqués (IP partagées).

**Output :** Graphe ASN/IP, flags sur hébergement "exposé" (ex: start-up VM publiques).

***

## 🟡 **Phase 2 — Empreinte Technologique**

### 🔹 **Agent 2 — The Tech Fingerprinter**

**Outils :** HTTPX, Wappalyzer CLI, Nuclei templates de détection.

**Logique :**
- Stack côté serveur (Apache/Nginx/IIS, version si possible).
- Framework (Django, Rails, Spring, .NET, Laravel, etc.).
- Côté client (React, Vue, Angular, jQuery, versions).
- Détection WAF/CDN (Cloudflare, Akamai, AWS Shield, F5).
- **Détection headers de sécurité manquants** (CSP, HSTS, X-Frame-Options, etc.).

**Décisions dynamiques & TTP :**
- Site statique → Scan S3 + mauvaises configs (S3 Bucket Enumeration, T1526).
- WordPress → Déclencher tests WP spécifiques (T1833 External Remote Services).
- Backend dynamique → Activer Fuzzer ciblé (T1595.003).
- SPA (React/Vue) → Déclencher JS Miner agressif (T1596.004 Search Victim-Owned Websites).
- **CDN/WAF detectés** → Ajuster fingerprint WAF (T1518.1 Software Discovery).

**Output :** Fiches technos + détection WAF + flags sécurité manquants.

***

## 🔴 **Phase 3 — Analyse JavaScript Profonde**

### 🔹 **Agent 3 — The JS Miner** (Amélioré)

**Outils :** Katana, SubJS, TruffleHog, regexes custom, AST parsing.

**Compétences :**
- Téléchargement et déduplication des JS (dont minifiés).
- Extraction secrets crédibles (AWS keys, Firebase, API keys, tokens).
- **Détection secrets stockés vs. injectés en runtime** (déduit la surface d'attaque).
- Reconstruction endpoints cachés via parsing (routes implicites).
- Détection APIs internes (`/internal/`, `/v1/admin/`, `/beta`, endpoints non-documentés).
- Détection hardcoded tokens / JWT (avec validation format).
- **Détection client-side validation** (vuln OWASP A04 : Insecure Design).
- Détection appels CORS / fetch vers tiers (data exfil potential, T1041).
- **Injection des résultats dans l'AssetGraph** avec provenance et confiance.

**TTP Mapping :**
- Secrets trouvés = T1552.007 (Sensitive Data in Code Repositories).
- Endpoints cachés = T1595.003 (Search Open Websites/Domains).
- Token hardcoded = T1552.001 (Credentials In Files).

**Output :**
```json
{
  "hidden_endpoints": [
    {
      "url": "/api/v1/admin/users",
      "source": "minified JS, line 2304",
      "confidence": 0.95,
      "mitre_ttp": "T1595.003"
    }
  ],
  "secrets": [
    {
      "type": "AWS_KEY",
      "pattern": "AKIA...",
      "evidence": "Hardcoded in React component",
      "severity": "CRITICAL",
      "mitre_ttp": "T1552.007"
    }
  ]
}
```

***

## 🟣 **Phase 4 — Fuzzing Ciblé & Interaction**

### 🔹 **Agent 4 — The Simulated Attacker** (Amélioré)

**Outils :** FFUF, python-requests, proxy Burp (optionnel), code_smith fallback.

**Comportement :**
- **Test d'erreurs serveur** (stack traces, verbose errors → T1592.004 Client Configurations).
- **Test d'auth bypass** (403 bypass headers, CORS misconfiguration → T1550 Use Alternate Authentication Material).
- **Tests de comportements anormaux** (rate limits, timing, patterns).
- **Fuzzing intelligent** :
  - Parameters (id, sid, token, key, etc.) avec payloads sans destruction.
  - Paths (admin, api, internal, backup, etc.) avec wordlists maison.
  - Methods (PUT, DELETE, PATCH, OPTIONS, TRACE).
  - Headers (X-Forwarded-For, X-Original-URL, Authorization bypass).
- **OPSEC aware** : respect du budget (rate limit, timeout), pas de DOS aveugle.
- **Fallback code_smith** : si FFUF échoue sur target critique, générer script custom Python + valider avant exec.

**TTP Mapping :**
- Auth bypass = T1550.004 (Use Alternate Authentication Material).
- 403 bypass = T1562.008 (Modify Cloud Compute Infrastructure).
- Fuzzing = T1595.003 (Search Open Websites/Domains).

**Output :** `attack_findings.json` + flags sur endpoints vulnérables.

***

## 🔵 **Phase 5 — OSINT & Archives + Threat Intel**

### 🔹 **Agent 5 — The Historian** (Amélioré)

**Outils :** WaybackUrls, Shodan API (read), GitHub Search API, DNS history.

**Objectifs :**
- **Diff endpoints actuels vs. historiques** (anciennes versions souvent vulnérables).
- **Détection endpoints supprimés** (orphans, broken links → potential accès).
- **Détection credentials dans repos publics** (avec TruffleHog, regex custom).
- **Enrichissement IPs** (ports SSH/FTP/DB ouverts via Shodan read-only).
- **Détection d'acquisitions** (domaines rachetés, anciennes infras toujours online).
- **Détection de branding/marketing** (CDNs, providers, partenaires cités publiquement).

**TTP Mapping :**
- Wayback = T1598.003 (Spearphishing with Credential Exposure).
- Git leaks = T1552.007 (Sensitive Data in Code Repositories).
- Shodan read = T1592.004 (Client Configurations).

**Output :** `historic_diffs.json` + corrélations graphe.

***

## 🟠 **Phase 5b — Threat Intelligence Mapping** (NOUVEAU)

### 🔹 **Agent 5b — The Threat Modeler**

**Objectif :** Lier chaque découverte à un scénario MITRE ATT&CK / TIBER‑EU.

**Outils :** MITRE CTI repo local, chaînes d'inférence.

**Comportement :**
- Chaque nœud du graphe = potentiels TTP.
- Chaque relation = potentiel chaînage attaque.
- Génération de "adversary profiles" basés sur détections (ex: SPA + S3 + Lambda → serverless attacker pattern).
- Suggestion de "Tactic Flow" (reconnaissance → initial access → priv esc → exfil).

**Output :** TTP graph + Adversary profiles + Attack chains documentées.

***

## 4. 🌐 Le Cœur : Asset Graph + TTP Graph

### 4.1 AssetGraph (Existant, Enrichi)

**Nœuds :** SUBDOMAIN, HTTP_SERVICE, ENDPOINT, PARAMETER, IP_ADDRESS, DNS_RECORD, VULNERABILITY, ATTACK_PATH, SECRET, TECHNOLOGY, HOSTING_PROVIDER, ASN.

**Relations :** RESOLVES_TO, HAS_DNS, SERVES, EXPOSES, HAS_PARAMETER, HAS_VULNERABILITY, HAS_HYPOTHESIS, CONTAINS_SECRET, TARGETS, PIVOT_TO, DEPENDS_ON.

### 4.2 TTP Graph (NOUVEAU)

**Nœuds :** MITRE_TACTIC, MITRE_TECHNIQUE, ADVERSARY_PROFILE, ATTACK_CHAIN.

**Relations :** 
- MAPS_TO : ENDPOINT → MITRE_TECHNIQUE.
- CHAINS_TO : TECHNIQUE → TECHNIQUE (progression d'attaque).
- EXECUTED_BY : ATTACK_CHAIN → ADVERSARY_PROFILE.

**Exemple :**
```
ENDPOINT (/admin/upload) 
  ├─ MAPS_TO T1567 (Exfiltration Over Web Service)
  ├─ MAPS_TO T1570 (Lateral Tool Transfer)
  └─ CHAINS_TO [T1190 → T1548 → T1567]  # RCE → Priv Esc → Exfil
```

### 4.3 Exploit Registry (NOUVEAU)

**Stockage local (JSON/Neo4j)** de :
- Payloads testés et validés.
- POCs générés (Burp scripts, curl one-liners, Python exploit scripts).
- Bypass techniques (WAF, auth, rate limits).
- Lien vers CVEs exploitables (via Asset Graph + CVE database local).

***

## 5. 📤 Output Final (Steps & Opérations)

### 5.1 Rapport Priorisé + Playbooks

**Format :** JSON + Markdown + PDF.

**Contenu :**

```
# 🎯 Executive Summary
- Surface d'attaque : N sous-domaines, M services, K endpoints.
- Top 5 vecteurs d'attaque identifiés (avec TTP mapping).
- Criticité métier estimée (basée sur techno, données exposées, pivots).

# 🔴 HIGH PRIORITY Findings

[HIGH] dev-api.example.com expose une stacktrace Django + endpoint /upload.
  - Technique: T1190 (Exploit Public-Facing Application) → RCE potential.
  - POC: [script généré + horodaté]
  - Playbook: 
    1. Proxy upload via Burp.
    2. Test file type restrictions.
    3. Accès shell / code execution.
  - Remediation: Input validation + upload directory sandboxing.

# 🟡 MEDIUM Findings

[MEDIUM] admin.example.com derrière Cloudflare, mais /api/v1/internal en archive.
  - Technique: T1598.003 (Spearphishing with Credential Exposure) via Wayback.
  - Status: Accessible? (à vérifier avec test actif).
  - Playbook: Probing API endpoint + authentication mechanisms.

# 🟢 LOW Findings

[LOW] Ancien bucket S3 détecté (permissions lecture).
  - Technique: T1526 (Cloud Service Discovery).
  - Données: Non‑critique (old backups).
  - Playbook: Enumerate bucket + identify sensitive data.

# 📊 Attack Chains Identified

- Chain 1: Phishing (T1598) → Creds (T1552) → Initial Access (T1195) → Priv Esc (T1548) → Exfil (T1041).
- Chain 2: Pub-facing RCE (T1190) → Lateral Movement (T1570) → Data Exfil (T1041).

# 🔧 Remediation Roadmap

Priority | Finding | Effort | Impact
---------|---------|--------|--------
1 | RCE /upload | 2h | Critical
2 | Auth bypass 403 | 4h | High
3 | S3 misconfiguration | 1h | Low
```

### 5.2 Artefacts Burp Suite + Tools

- Sitemap Burp (XML import).
- Projet Burp préconfiguré (scope, profiles, checks).
- POCs générés (Burp macros, Intruder templates, Extension scripts).
- Export pour Metasploit (si applicable).

### 5.3 Playbooks d'Exploitation

**Format :** Runbook structuré (étapes, commandes, checks, fallbacks).

```yaml
Playbook: RCE via /upload endpoint
Target: dev-api.example.com
Technique: T1190 + T1567
Prerequisites:
  - Network access to endpoint
  - Knowledge of allowed file types
Steps:
  1. Enumerate file extensions: ffuf -u http://target/upload/test.FUZZ
  2. Test MIME type bypass: Content-Type: application/json
  3. Upload shell: curl -X POST -F "file=@shell.php" http://target/upload
  4. Access shell: curl http://target/uploads/shell.php
  5. RCE: curl http://target/uploads/shell.php?cmd=id
Evidence: [captured screenshots, response logs, timestamps]
Fallback: If standard upload fails, use code_smith to generate bypass script
```

### 5.4 Workspace Interactif (NOUVEAU)

**TUI / Simple Web UI :**
- Visualisation graphe (filtres : techno, risque, TTP).
- Boutons pour lancer modules sur cibles (recon active, exploit script).
- Sync avec repo privé (versioning des payloads/modules).
- Dashboard KPI (surface d'attaque, tendances, couverte).

***

## 6. 🛠️ Stack Technique V4

### **Backend Orchestration**
- **Python 3.12+** → orchestration, agents, logique métier.
- **CrewAI** → gestion agents + tasks.
- **Pydantic** → modèles typés + validation.
- **Neo4j** (optionnel) → stockage graphe (actuellement JSON local).

### **Infra & Tools**
- **Docker** → Subfinder, outils isolés.
- **Subprocess + async** → parallélisation légère (FFUF, Nuclei).
- **Ollama** (local) → Qwen 7B pour NLP, code generation.

### **Optionnel Cloud**
- **GPT-4.1-mini** (API) → analyses lourdes (si budget).
- **Shodan / GitHub API** → OSINT read-only.

### **Observabilité**
- **Structlog** → JSON logs.
- **Prometheus client** → métriques.
- **SQLite / JSON files** → metrics locales.

### **Front**
- **TUI (textual ou rich)** : minimal mais utilisable.
- **FastAPI** (optionnel) : exposition locale pour UI web légère.

***

## 7. 🗺️ Roadmap V4 (8 semaines)

### **🟩 Semaines 1–2 : Architecture & Modèles**
- Refactor `OrchestratorService` (extraire de main.py).
- Formaliser DTO Pydantic (EndpointDTO, HypothesisDTO, TTPMapDTO).
- Brancher **code_smith fallback** (instanciation + logique détection d'échec).
- Ajouter **TTP Graph skeleton**.

### **🟨 Semaines 3–4 : Agents & Pipelines**
- Affiner Profiler + ajouter Infrastructure Mapper.
- Renforcer JS Miner (secrets, détection client-side validation).
- Brancher Threat Modeler (mapping MITRE).
- Implémenter Phase 26–27 (Exploitation Orchestration, Pivot).

### **🟧 Semaines 5–6 : Observabilité & OPSEC**
- Logger structuré complet (run_id propagé).
- Profile d'engagement (pro audit vs. black-box).
- Budget.yaml complet (opsec checks).
- Audit trail des actions (toutes les décisions loggées).

### **🟥 Semaines 7–8 : Exploitation & Reporting**
- Exploitation orchestration (playbooks, POCs autogénérés).
- Export Burp + generateurs de scripts.
- Playbook templates (RCE, Auth bypass, lateral movement).
- TUI / Web UI minimal.

***

## 8. 🎯 Profils d'Engagement (Opsec & Légal)

### **Profile 1 : Pro Audit**
- IP officielles, bannières légales ("Security Assessment").
- Contact SOC clair (nom, mail, téléphone).
- Budget agressif (rate limits normaux).
- Tous les tests activés, sans retenue.

### **Profile 2 : Red Team Black-Box**
- Rotation IP (VPN, VPS proxy).
- DNS customs (pas FAI).
- Budget très contrôlé (rate limits bas, pas de bruit).
- TTP limit (pas de destruction, pas de DoS).
- Mode "stealth" par défaut.

### **Profile 3 : Perso / Sandbox**
- Tests sur domaines perso ou labs.
- Budget illimité.
- Tous les tests, même destructifs (mode lab).

***

## 9. 🔐 Sécurité Interne & Audit Trail

- **Validation d'entrée** : domaines via regex, scope via whitelist.
- **Secrets management** : .env local, pas de hardcode.
- **Sandboxing code_smith** : AST checks, timeout, no os/subprocess/exec/eval.
- **Audit trail complet** : chaque décision loggée (agent, target, action, résultat, timestamp).
- **Reproductibilité** : seed file optionnel, dump complet du graphe, métriques par phase.

***

## 10. 💡 Cas d'Usage Type

### **Scenario : Audit Pentest Colombes.fr (Profil Pro)**

```bash
python run_mission.py colombes.fr \
  --mode aggressive \
  --profile "pro_audit" \
  --output-format "full" \
  --export-burp \
  --generate-playbooks
```

**Output attendu :**

1. **AssetGraph JSON** : 60 subdomains, 25 services, 150 endpoints, enrichis.
2. **TTP Graph** : 12 techniques MITRE mappées, 4 chaînes d'attaque identifiées.
3. **Rapport Markdown** : Top 10 findings priorisés + playbooks d'exploitation.
4. **Burp Project XML** : Scope pré-configuré, Intruder templates.
5. **POCs générés** : 3 exploits (RCE, auth bypass, lateral movement) avec runbooks.
6. **Audit Trail** : logs complets (JSON), metrics par phase, evidence hashes.
7. **Playbooks** : 5 runbooks détaillés (étapes, commandes, checks).
8. **Workspace** : TUI avec graphe interactif, boutons pour lancer tests supplémentaires.

***

## 11. ✅ Checklist Implémentation

- [ ] Refactor OrchestratorService (extraction main.py).
- [ ] DTO Pydantic complets + validation.
- [ ] Code_smith branché (fallback outil échoué).
- [ ] TTP Graph skeleton + mapping MITRE.
- [ ] Profils d'engagement (enum + logique).
- [ ] Budget.yaml complet (OPSEC checks).
- [ ] Logger structuré + run_id propagé.
- [ ] Exploitation orchestration (Phase 26–27).
- [ ] Playbook autogénération.
- [ ] Export Burp XML.
- [ ] TUI / Web UI.
- [ ] Tests complets + documentation.

***

## 12. 📌 Key Differentiators vs. Tools Existants

| Aspect | Standard Tools | ReconRTF V4 |
|--------|---|---|
| **Recon** | Listes plates (subdomains, endpoints) | Graphe riche + contexte + TTP |
| **Orchestration** | Workflows fixes | Agents autonomes + décisions dynamiques |
| **Exploitation** | Manuel ou templates statiques | Playbooks autogénérés + POCs testés |
| **Opsec** | Configuration globale | Profils d'engagement + audit trail complet |
| **Reproductibilité** | Pas facile | Seed files + logs structurés + runbooks |
| **Audit** | Logs bruts | JSON structurés + hashes + evidence |

***

*Version 4.0 — Décembre 2025*