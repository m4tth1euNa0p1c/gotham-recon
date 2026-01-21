# Documentation Complete du Systeme d'Agents CrewAI

> **Guide technique exhaustif du systeme multi-agents de Recon Gotham**
> Version: 3.2.1 | Decembre 2025

---

## Table des Matieres

1. [Introduction au Systeme d'Agents](#1-introduction-au-systeme-dagents)
2. [Architecture CrewAI](#2-architecture-crewai)
3. [Anatomie d'un Agent](#3-anatomie-dun-agent)
4. [Agents de Phase OSINT](#4-agents-de-phase-osint)
5. [Agents de Phase Active Recon](#5-agents-de-phase-active-recon)
6. [Agents de Phase Intelligence](#6-agents-de-phase-intelligence)
7. [Agents de Deep Verification](#7-agents-de-deep-verification)
8. [Agents Utilitaires](#8-agents-utilitaires)
9. [Systeme de Taches (Tasks)](#9-systeme-de-taches-tasks)
10. [Patterns Anti-Hallucination](#10-patterns-anti-hallucination)
11. [Flux de Donnees Inter-Agents](#11-flux-de-donnees-inter-agents)
12. [Configuration et Personnalisation](#12-configuration-et-personnalisation)

---

## 1. Introduction au Systeme d'Agents

### 1.1 Philosophie de conception

Le systeme d'agents de Recon Gotham repose sur une philosophie fondamentale : **specialisation et collaboration**. Plutot qu'un agent unique omniscient, nous deployon une equipe d'agents specialises qui excellent chacun dans leur domaine.

**Principes directeurs :**

| Principe | Description | Implementation |
|----------|-------------|----------------|
| **Specialisation** | Chaque agent maitrise un domaine precis | 19 agents avec roles distincts |
| **Collaboration** | Les agents partagent leurs decouvertes | Tasks avec contexte chaine |
| **Autonomie** | Chaque agent decide de ses actions | LLM pour le raisonnement |
| **Fiabilite** | Les outils garantissent la precision | Appels directs + validation |
| **Tracabilite** | Chaque decision est explicable | Logs structures, events Kafka |

### 1.2 Approche Hybride : LLM + Outils

```
┌─────────────────────────────────────────────────────────────┐
│                    APPROCHE HYBRIDE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   OUTILS DIRECTS              AGENTS LLM                     │
│   (Fiabilite)                 (Intelligence)                 │
│                                                              │
│   ┌─────────────┐            ┌─────────────┐                │
│   │  Subfinder  │────────────│  Pathfinder │                │
│   │  (donnees)  │   analyse  │  (contexte) │                │
│   └─────────────┘            └─────────────┘                │
│                                                              │
│   Les outils collectent      Les agents interpretent         │
│   les donnees brutes         et contextualisent              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Pourquoi cette approche ?**

Les LLM ont deux faiblesses critiques pour la reconnaissance :
1. **Hallucination** : Ils peuvent inventer des sous-domaines qui n'existent pas
2. **Perte de donnees** : En resumant, ils peuvent omettre des elements importants

Notre solution : les outils collectent les donnees de maniere fiable, les agents les analysent et les contextualisent.

### 1.3 Vue d'ensemble des agents

```
PHASE OSINT                    PHASE ACTIVE                   PHASE INTEL
┌──────────────┐              ┌──────────────┐              ┌──────────────┐
│  Pathfinder  │──────────────│  StackTrace  │──────────────│  RiskAware   │
│  (enumeration)              │  (fingerprint)              │  (scoring)   │
└──────────────┘              └──────────────┘              └──────────────┘
       │                             │                             │
       ▼                             ▼                             ▼
┌──────────────┐              ┌──────────────┐              ┌──────────────┐
│  Watchtower  │              │  DeepScript  │              │  Overwatch   │
│  (analyse)   │              │  (JS mining) │              │  (planning)  │
└──────────────┘              └──────────────┘              └──────────────┘
       │                             │                             │
       ▼                             ▼                             ▼
┌──────────────┐              ┌──────────────┐              ┌──────────────┐
│ DNS Analyst  │              │  All-Seeing  │              │  Reflector   │
│ ASN Analyst  │              │    Eye       │              │  (validation)│
└──────────────┘              └──────────────┘              └──────────────┘

PHASE VERIFICATION
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Triage     │──▶│  StackMap    │──▶│  Validator   │──▶│   Curator    │
│  (priority)  │   │  (mapping)   │   │   (plan)     │   │  (evidence)  │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

---

## 2. Architecture CrewAI

### 2.1 Composants fondamentaux

CrewAI structure le travail en trois concepts :

```python
# Structure CrewAI
Agent   → Qui fait le travail (identite, competences, personnalite)
Task    → Ce qui doit etre fait (instructions, format de sortie)
Crew    → Comment ils travaillent ensemble (processus, delegation)
```

### 2.2 Factory Pattern

Notre implementation utilise le pattern Factory pour creer les agents :

```python
# agent_factory.py:86-119
def build_agent(
    agent_id: str,
    role: str,
    goal: str,
    backstory: str,
    tools: list = None,
    verbose: bool = True,
) -> Agent:
    """Build a single CrewAI agent programmatically"""
    llm = create_ollama_llm()

    return Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        llm=llm,
        tools=tools or [],
        verbose=verbose,
        allow_delegation=False,
        max_iter=15,
    )
```

**Parametres cles :**

| Parametre | Valeur | Justification |
|-----------|--------|---------------|
| `allow_delegation` | `False` | Empeche les agents de deleguer a d'autres (controle strict) |
| `max_iter` | `15` | Limite les boucles infinies de raisonnement |
| `max_rpm` | `10` | Rate limiting pour eviter de surcharger le LLM |
| `verbose` | `True` | Logs detailles pour debug (False en prod pour certains) |

### 2.3 Integration LLM

```python
# llm_client.py (simplifie)
def get_crewai_llm():
    """Retourne un LLM compatible CrewAI"""
    return ChatOpenAI(
        base_url=f"{OLLAMA_BASE_URL}/v1",
        model=MODEL_NAME,  # qwen2.5:14b par defaut
        temperature=0.7,
        api_key="ollama"
    )
```

**Choix du modele :**
- `qwen2.5:14b` : Equilibre performance/vitesse pour la plupart des agents
- `qwen2.5-coder:7b` : Pour les agents generateurs de code (CoderAgent)

---

## 3. Anatomie d'un Agent

### 3.1 Les trois piliers d'un agent

Chaque agent est defini par trois elements qui forment son "prompt systeme" :

```yaml
agent_name:
  role: "Titre professionnel et nom de code"
  goal: "Objectif mesurable et specifique"
  backstory: "Contexte, personnalite et contraintes"
```

### 3.2 Decomposition detaillee

#### ROLE : L'identite professionnelle

```yaml
role: >
  Lead Reconnaissance Orchestrator (Code Name: Pathfinder)
```

**Fonction du role :**
- Definit l'expertise de l'agent
- Influence le vocabulaire utilise
- Etablit la credibilite des reponses
- Le "Code Name" cree une identite memorable pour les logs

**Pattern observe :** Les noms de code (Pathfinder, Watchtower, StackTrace) sont inspires de la terminologie militaire/renseignement pour renforcer l'immersion dans le contexte offensif.

#### GOAL : L'objectif mesurable

```yaml
goal: >
  Map the entire attack surface of {target_domain} and identify
  critical environments (dev, staging, api) to prepare the following attack phases.
```

**Fonction du goal :**
- Definit le succes de la mission
- Guide les decisions de l'agent
- Permet l'auto-evaluation ("Ai-je atteint mon objectif ?")
- Le placeholder `{target_domain}` est remplace dynamiquement

**Criteres d'un bon goal :**
1. **Specifique** : "Map the attack surface" pas "Faire de la reconnaissance"
2. **Mesurable** : "identify critical environments" peut etre verifie
3. **Contextualise** : Reference aux phases suivantes

#### BACKSTORY : La personnalite et les contraintes

```yaml
backstory: >
  You are the elite scout. Your job is not to make noise, but to understand the target.

  Your strategic objectives are:
  1. EXHAUSTIVENESS: Miss no active subdomain using multi-source passive enumeration.
  2. CONTEXT AWARENESS: Do NOT return a raw list. You must say
     "This subdomain looks like a test API environment."
  3. CLEAN OUTPUT: Produce structured (JSON) data perfectly suited for the next agents.
  4. RESILIENCE: If a tool fails, you must report it cleanly without crashing the pipeline.
```

**Fonction du backstory :**
- Etablit la personnalite de l'agent
- Definit les contraintes comportementales
- Specifie les attentes de qualite
- Guide la gestion des erreurs

**Elements critiques du backstory :**

| Element | Exemple | Impact |
|---------|---------|--------|
| Identite | "elite scout" | Renforce la confiance |
| Interdiction | "not to make noise" | Limite les actions risquees |
| Objectifs numerotes | "1. EXHAUSTIVENESS" | Structure les priorites |
| Format de sortie | "structured (JSON)" | Garantit la compatibilite |
| Gestion d'erreur | "report cleanly" | Evite les crashes |

### 3.3 Exemple complet annote

```yaml
pathfinder:
  # ROLE: Definit QUI est l'agent
  # - "Lead" indique la seniorite/autorite
  # - "Orchestrator" suggere coordination sans execution directe
  # - Le nom de code cree une identite memorable
  role: >
    Lead Reconnaissance Orchestrator (Code Name: Pathfinder)

  # GOAL: Definit CE QUE l'agent doit accomplir
  # - "entire attack surface" = exhaustivite
  # - "identify critical environments" = priorisation
  # - Reference aux "following attack phases" = conscience du pipeline
  goal: >
    Map the entire attack surface of {target_domain} and identify
    critical environments (dev, staging, api) to prepare the following attack phases.

  # BACKSTORY: Definit COMMENT l'agent doit se comporter
  # - Analogie militaire ("elite scout") renforce le contexte offensif
  # - "not to make noise" = mode stealth implicite
  # - Objectifs numerotes = priorites claires
  # - "CLEAN OUTPUT" = integration avec les autres agents
  # - "RESILIENCE" = gestion d'erreur explicite
  backstory: >
    You are the elite scout. Your job is not to make noise, but to understand the target.

    Your strategic objectives are:
    1. EXHAUSTIVENESS: Miss no active subdomain using multi-source passive enumeration.
    2. CONTEXT AWARENESS: Do NOT return a raw list. You must say
       "This subdomain looks like a test API environment."
    3. CLEAN OUTPUT: Produce structured (JSON) data perfectly suited for the next agents.
    4. RESILIENCE: If a tool fails, you must report it cleanly without crashing the pipeline.
```

---

## 4. Agents de Phase OSINT

### 4.1 PATHFINDER - L'Eclaireur

**Fichier source :** `agents.yaml:1-17`, `agent_factory.py:123-137`

#### Configuration

```yaml
pathfinder:
  role: Lead Reconnaissance Orchestrator (Code Name: Pathfinder)
  goal: >
    Map the entire attack surface of {target_domain} and identify
    critical environments (dev, staging, api)
  backstory: >
    You are the elite scout. Your job is not to make noise, but to understand the target.
    1. EXHAUSTIVENESS: Miss no active subdomain
    2. CONTEXT AWARENESS: Provide context for each subdomain
    3. CLEAN OUTPUT: Produce structured JSON
    4. RESILIENCE: Report errors cleanly
```

#### Logique metier

**Mission principale :** Premier agent du pipeline, Pathfinder lance la reconnaissance passive et collecte les sous-domaines via Subfinder.

**Outils disponibles :**
- `SubfinderTool` : Enumeration de sous-domaines multi-sources

**Flux de traitement :**
```
1. Recevoir le domaine cible
2. Appeler Subfinder avec mode '-all'
3. Parser les resultats JSON
4. Ajouter du contexte semantique (dev, staging, prod)
5. Retourner la liste enrichie
```

**Pourquoi ce design ?**

Pathfinder est volontairement "muet" (passive recon) car :
1. La phase OSINT ne doit generer aucun trafic direct vers la cible
2. Les sources passives (CT logs, VirusTotal, etc.) sont plus discretes
3. L'exhaustivite prime sur la profondeur a ce stade

#### Exemple d'output

```json
[
  {
    "subdomain": "api-dev.example.com",
    "tag": "DEV_API",
    "priority": 9,
    "reason": "Development API - likely less secured",
    "category": "APP_BACKEND"
  },
  {
    "subdomain": "www.example.com",
    "tag": "PROD_WEB",
    "priority": 3,
    "reason": "Production website - typically hardened",
    "category": "STATIC_ASSET"
  }
]
```

---

### 4.2 WATCHTOWER - L'Analyste

**Fichier source :** `agents.yaml:19-33`, `agent_factory.py:140-152`

#### Configuration

```yaml
intelligence_analyst:
  role: Senior Intelligence Analyst (Code Name: Watchtower)
  goal: >
    Transform raw reconnaissance data into actionable intelligence.
    Identify high-value targets and assign tags based on criticality.
  backstory: >
    You are the brain of the operation. Pathfinder sees everything,
    but you understand everything.
    You analyze naming patterns to infer each server's purpose
    and assess its risk level.
```

#### Logique metier

**Mission principale :** Transformer les donnees brutes de Pathfinder en intelligence actionnable.

**Raisonnement type :**
```
Input: "admin-staging.example.com"

Analyse:
- "admin" → Interface d'administration (HIGH PRIORITY)
- "staging" → Environnement de pre-production (LESS HARDENED)
- Combinaison → Cible de haute valeur, probablement accessible

Output:
- Tag: ADMIN_STAGING
- Priority: 9/10
- Category: AUTH_PORTAL
- Recommendation: httpx_probe + nuclei_scan
```

**Pourquoi ce design ?**

Watchtower separe la collecte de l'analyse car :
1. Un agent specialise en analyse fait de meilleurs jugements
2. La priorisation evite de scanner des milliers de sous-domaines inutiles
3. Le contexte semantique (dev/staging/prod) guide les phases suivantes

#### Patterns de detection

| Pattern | Interpretation | Priority |
|---------|----------------|----------|
| `admin*`, `panel*` | Interface admin | 9-10 |
| `api*`, `gateway*` | API backend | 8-9 |
| `dev*`, `test*` | Environnement dev | 7-8 |
| `staging*`, `uat*` | Pre-production | 7-8 |
| `mail*`, `smtp*` | Serveur mail | 6-7 |
| `www*`, `static*` | Production web | 3-4 |
| `cdn*`, `assets*` | CDN/Assets | 1-2 |

---

### 4.3 DNS_ANALYST - Le Specialiste DNS

**Fichier source :** `agents.yaml:35-40`, `agent_factory.py:155-164`

#### Configuration

```yaml
dns_analyst:
  role: DNS Resolution Specialist
  goal: "Resolve DNS records for all confirmed subdomains and extract actionable infrastructure intelligence."
  backstory: "You specialize in DNS reconnaissance and infrastructure mapping."
  verbose: false  # Mode silencieux pour performance
```

#### Logique metier

**Mission principale :** Resoudre les enregistrements DNS et cartographier l'infrastructure.

**Donnees extraites :**
- Records A/AAAA : IP addresses
- Records MX : Serveurs mail
- Records TXT : SPF, DKIM, verification tokens
- Records CNAME : Aliases et redirections
- Records NS : Serveurs DNS autoritaires

**Pourquoi `verbose: false` ?**

L'agent DNS est configure en mode silencieux car :
1. Il effectue des operations repetitives (resolution de N sous-domaines)
2. Les logs detailles seraient trop volumineux
3. L'output structure suffit pour le suivi

#### Exemple d'output

```json
[
  {
    "subdomain": "api.example.com",
    "ips": ["192.168.1.10", "192.168.1.11"],
    "records": {
      "A": ["192.168.1.10", "192.168.1.11"],
      "CNAME": [],
      "MX": [],
      "TXT": []
    },
    "is_live": true,
    "response_time_ms": 45
  }
]
```

---

### 4.4 ASN_ANALYST - L'Expert Infrastructure

**Fichier source :** `agents.yaml:42-46`

#### Configuration

```yaml
asn_analyst:
  role: ASN Intelligence Analyst
  goal: "Map IPs to ASNs and identify ownership or hosting provider infrastructure."
  backstory: "You correlate IPs with organizations to enrich the attack graph."
```

#### Logique metier

**Mission principale :** Identifier les proprietaires de l'infrastructure et detecter les patterns.

**Intelligence extraite :**
- ASN (Autonomous System Number)
- Proprietaire de l'ASN (Amazon, Cloudflare, OVH...)
- Plage IP associee
- Geolocalisation approximate

**Cas d'usage :**

```
IP: 104.18.32.68

Resultat ASN:
- ASN: AS13335
- Owner: Cloudflare, Inc.
- Implication: Cible derriere CDN, IP reelle masquee

Action recommandee: Chercher IP origin via autres methodes
```

**Pourquoi cet agent ?**

L'ASN analysis revele :
1. Si la cible utilise un CDN (protection DDoS, WAF)
2. Le cloud provider (AWS, GCP, Azure) pour adapter les techniques
3. Les plages IP pour identifier d'autres serveurs du meme proprietaire

---

## 5. Agents de Phase Active Recon

### 5.1 TECH_FINGERPRINTER (StackTrace) - Le Profileur

**Fichier source :** `agents.yaml:49-58`, `agent_factory.py:167-178`

#### Configuration

```yaml
tech_fingerprinter:
  role: Senior Tech Fingerprinter (Code Name: StackTrace)
  goal: >
    Enrich high-priority subdomains with technical information:
    HTTP status, server/client technologies, IP address, potential WAF/CDN.
  backstory: >
    You are the engineer who transforms a simple list of subdomains
    into actionable technical profiles.
    You use httpx in a precise and targeted manner.
    You DO NOT scan everything: only the most critical subdomains
    provided by Watchtower (priority >= 8).
```

#### Logique metier

**Mission principale :** Profiler les services HTTP des cibles prioritaires.

**Critere de filtrage :** `priority >= 8` (defini par Watchtower)

**Pourquoi filtrer ?**

Scanner tous les sous-domaines serait :
1. Lent (N requetes HTTP par sous-domaine)
2. Bruyant (trafic detectable)
3. Peu rentable (80% des sous-domaines sont peu interessants)

Le filtrage concentre les ressources sur les 20% de cibles a haute valeur.

**Donnees extraites par HTTPX :**

| Donnee | Source | Utilisation |
|--------|--------|-------------|
| Status Code | HTTP Response | 200=live, 301=redirect, 403=protected |
| Server Header | HTTP Headers | nginx, Apache, IIS |
| Technologies | Wappalyzer DB | WordPress, React, Laravel |
| Title | HTML `<title>` | Contexte de l'application |
| Content-Length | HTTP Headers | Detect empty/error pages |
| TLS Info | Certificate | Expiration, issuer, SAN |

#### Exemple d'output

```json
[
  {
    "subdomain": "admin.example.com",
    "priority": 9,
    "http": {
      "url": "https://admin.example.com",
      "status_code": 200,
      "title": "Admin Dashboard - Login",
      "technologies": ["PHP", "Laravel", "nginx"],
      "ip": "192.168.1.10",
      "content_length": 4532,
      "server": "nginx/1.18.0"
    }
  }
]
```

---

### 5.2 JS_MINER (DeepScript) - Le Mineur JavaScript

**Fichier source :** `agents.yaml:61-70`, `agent_factory.py:181-191`

#### Configuration

```yaml
js_miner:
  role: JavaScript Intelligence Miner (Code Name: DeepScript)
  goal: >
    Extract hidden endpoints and secrets from JavaScript files
    belonging to high-value subdomains.
  backstory: >
    You are an expert JS security analyst. You look for API keys,
    hardcoded credentials, and internal endpoints in JavaScript files.
    You read JavaScript like a novel and reconstruct internal API
    structures from frontend calls.
```

#### Logique metier

**Mission principale :** Extraire l'intelligence cachee dans le code JavaScript frontend.

**Cibles d'extraction :**

1. **Endpoints API**
```javascript
// Detecte dans le JS
fetch('/api/v1/users')
axios.post('/internal/admin/settings')
$.ajax({url: '/legacy/data'})
```

2. **Secrets et tokens**
```javascript
// Patterns recherches
const API_KEY = "sk_live_xxxxx"
const AWS_SECRET = "AKIA..."
const JWT_SECRET = "my-secret-key"
```

3. **Configuration**
```javascript
// Variables d'environnement exposees
window.CONFIG = {
  apiUrl: "https://internal-api.example.com",
  debug: true,
  featureFlags: {...}
}
```

**Pourquoi cet agent est critique ?**

Les SPAs (Single Page Applications) modernes exposent enormement de logique :
- React/Vue/Angular compilent vers du JS lisible
- Les variables d'environnement de build sont souvent exposees
- Les routes internes sont hardcodees dans le frontend

#### Exemple d'output

```json
[
  {
    "url": "https://app.example.com",
    "js": {
      "js_files": [
        "https://app.example.com/static/js/main.abc123.js",
        "https://app.example.com/static/js/vendor.def456.js"
      ],
      "endpoints": [
        {"path": "/api/v1/users", "method": "GET", "source_js": "main.abc123.js"},
        {"path": "/api/v1/admin/config", "method": "POST", "source_js": "main.abc123.js"},
        {"path": "/internal/debug", "method": "GET", "source_js": "main.abc123.js"}
      ],
      "secrets": [
  "main.abc123.js"}
      ]
    }
  }
]
```

---

### 5.3 ENDPOINT_ANALYST (All-Seeing Eye) - L'Archeologue

**Fichier source :** `agents.yaml:83-92`

#### Configuration

```yaml
endpoint_analyst:
  role: Endpoint Intelligence Analyst (Code Name: All-Seeing Eye)
  goal: >
    Discover every hidden API endpoint, administrative panel, and historical URL.
    You look where others don't: HTML attributes, Robots.txt, and the Wayback Machine.
  backstory: >
    You are an informational archaeologist and spider.
    You crawl the surface (HTML) and dig into the past (Wayback) to find forgotten entry points.
    Your motto: "If it was ever online, I will find it."
```

#### Logique metier

**Mission principale :** Decouvrir tous les endpoints, meme ceux caches ou supprimes.

**Sources exploitees :**

| Source | Technique | Exemple de decouverte |
|--------|-----------|----------------------|
| HTML Crawling | Parse les `<a>`, `<form>`, `<script>` | `/admin/users/delete` |
| Robots.txt | Lit les `Disallow` | `/private/`, `/backup/` |
| Wayback Machine | Archive.org API | `/old-admin/` (supprime depuis) |
| Sitemap.xml | Parse les `<url>` | `/fr/page-secrete` |
| Comments HTML | Regex sur `<!-- -->` | `<!-- TODO: remove /debug -->` |

**Pourquoi le Wayback Machine ?**

Les applications evoluent, mais Internet Archive conserve les anciennes versions :
- Panneaux admin supprimes mais toujours accessibles
- APIs depreciees mais non desactivees
- Fichiers de configuration temporairement exposes

#### Exemple d'output

```json
[
  {"path": "/admin/login", "method": "GET", "source": "HTML_CRAWL", "origin": "app.example.com"},
  {"path": "/api/v1/users", "method": "GET", "source": "JS_ANALYSIS", "origin": "main.js"},
  {"path": "/backup/db.sql", "method": "GET", "source": "WAYBACK", "origin": "archive.org:2019"},
  {"path": "/debug/phpinfo", "method": "GET", "source": "ROBOTS", "origin": "robots.txt:Disallow"}
]
```

---

## 6. Agents de Phase Intelligence

### 6.1 ENDPOINT_INTEL (RiskAware) - L'Evaluateur de Risque

**Fichier source :** `agents.yaml:129-146`, `agent_factory.py:194-213`

#### Configuration

```yaml
endpoint_intel:
  role: Endpoint Risk Intelligence Analyst (Code Name: RiskAware)
  goal: >
    Analyze and enrich discovered endpoints with offensive intelligence:
    Confirm or adjust category (API/ADMIN/AUTH/LEGACY), likelihood/impact/risk scores,
    and propose attack hypotheses for Red Team prioritization.
  backstory: >
    You are an expert in web application security assessment.

    CRITICAL CONSTRAINTS:
    1. You MUST NOT invent new endpoints or domains.
    2. You ONLY enrich the endpoints you are given.
    3. You stay strictly within the target domain scope.
    4. Your output MUST be valid JSON only, no preamble.
    5. Maximum 3 hypotheses per endpoint.
```

#### Logique metier

**Mission principale :** Transformer les endpoints decouverts en cibles priorisees avec hypotheses d'attaque.

**Processus d'enrichissement :**

```
Input: /api/v1/users?id=123

Analyse:
├── Category: API (pattern /api/)
├── Likelihood: 7/10 (parametre id injectable)
├── Impact: 8/10 (donnees utilisateurs)
├── Risk Score: 56/100 (7 × 8)
├── Auth Required: Probably yes (users endpoint)
├── Tech Hint: REST API
└── Hypotheses:
    ├── IDOR: "ID parameter may allow access to other users" (conf: 0.7)
    └── SQLI: "ID parameter may be injectable" (conf: 0.5)
```

**Formule de scoring :**

```
risk_score = likelihood_score × impact_score

Ou:
- likelihood_score (0-10) = Probabilite d'exploitation
- impact_score (0-10) = Gravite si exploite
- risk_score (0-100) = Score final pour priorisation
```

**Categories d'endpoints :**

| Category | Pattern | Risk Base |
|----------|---------|-----------|
| ADMIN | `/admin`, `/dashboard`, `/panel` | HIGH |
| AUTH | `/login`, `/auth`, `/session` | HIGH |
| API | `/api`, `/graphql`, `/rest` | MEDIUM-HIGH |
| LEGACY | `/old`, `/v1` (deprecated), `/backup` | MEDIUM-HIGH |
| PUBLIC | `/`, `/about`, `/contact` | LOW |
| STATIC | `/css`, `/js`, `/images` | VERY LOW |
| HEALTHCHECK | `/health`, `/status`, `/ping` | INFO |

**Types d'attaques (ATTACK_TYPE) :**

```
XXE, SQLI, XSS, IDOR, BOLA, AUTH_BYPASS, RATE_LIMIT,
RCE, SSRF, LFI, RFI, CSRF, OPEN_REDIRECT, INFO_DISCLOSURE
```

#### Exemple d'output

```json
{
  "endpoints": [
    {
      "endpoint_id": "endpoint:https://api.example.com/admin/users",
      "category": "ADMIN",
      "likelihood_score": 8,
      "impact_score": 9,
      "risk_score": 72,
      "auth_required": true,
      "tech_stack_hint": "Node.js/Express",
      "parameters": [
        {"name": "id", "location": "query", "datatype_hint": "integer", "sensitivity": "HIGH", "is_critical": true}
      ],
      "hypotheses": [
        {"title": "IDOR on user ID parameter", "attack_type": "IDOR", "confidence": 0.8, "priority": 5},
        {"title": "Admin access without proper authorization", "attack_type": "AUTH_BYPASS", "confidence": 0.6, "priority": 4}
      ]
    }
  ]
}
```

---

### 6.2 PLANNER (Overwatch) - Le Stratege

**Fichier source :** `agents.yaml:72-81`, `agent_factory.py:216-228`

#### Configuration

```yaml
planner:
  role: Reconnaissance Planner Brain (Code Name: Overwatch)
  goal: >
    Select the most profitable attack paths from the AssetGraph
    and decide which tools and tasks to run next.
  backstory: >
    You are the strategic brain of the operation.
    You DO NOT invent assets or subdomains.
    You only reason on the validated Graph provided by your field agents.
    Your job is to connect the dots:
    A high-priority subdomain + An exposed API + A sensitive JS file = Critical Attack Vector.
```

#### Logique metier

**Mission principale :** Identifier les chemins d'attaque les plus rentables et planifier les actions suivantes.

**Raisonnement strategique :**

```
Donnees disponibles:
├── subdomain: admin.example.com (priority: 9)
├── http_service: https://admin.example.com (status: 200, tech: PHP)
├── endpoint: /admin/users (category: ADMIN, risk: 72)
├── js_intel: API key Stripe trouvee
└── hypothesis: AUTH_BYPASS (confidence: 0.7)

Analyse Overwatch:
"La combinaison d'un panneau admin PHP accessible (souvent vulnerable)
avec une cle Stripe exposee et une hypothese d'auth bypass
constitue un vecteur d'attaque critique."

Plan d'action:
1. nuclei_scan sur /admin/users (templates: cves, exposures)
2. ffuf_api_fuzz sur /admin/* (wordlist: admin-panels)
3. manual_review pour la cle Stripe
```

**Actions possibles :**

| Action | Declencheur | Objectif |
|--------|-------------|----------|
| `nuclei_scan` | Tech stack identifiee | Detecter CVEs et misconfigs |
| `ffuf_api_fuzz` | Endpoint API decouvert | Decouvrir endpoints caches |
| `parameter_mining` | JS complexe trouve | Extraire parametres |
| `smtp_test` | Serveur mail detecte | Tester configs SMTP |
| `dns_audit` | Anomalies DNS | Verifier DMARC/SPF |
| `manual_review` | Secret/infra critique | Analyse humaine requise |

#### Exemple d'output

```json
[
  {
    "subdomain": "admin.example.com",
    "score": 92,
    "reason": "PHP admin panel with Stripe key leak and AUTH_BYPASS hypothesis",
    "attack_vector": "Authentication bypass leading to admin access and payment data exposure",
    "next_actions": ["nuclei_scan", "ffuf_api_fuzz", "manual_review"]
  },
  {
    "subdomain": "api-dev.example.com",
    "score": 78,
    "reason": "Development API with debug endpoints exposed",
    "attack_vector": "Information disclosure via debug endpoints",
    "next_actions": ["nuclei_scan", "parameter_mining"]
  }
]
```

---

### 6.3 REFLECTOR - Le Validateur (P0.6)

**Fichier source :** `agents.yaml:150-170`

#### Configuration

```yaml
reflector_agent:
  role: Result Validation & Enrichment Specialist (Code Name: Reflector)
  goal: >
    Analyze tool results for completeness, accuracy, and enrichment opportunities.
    When results are incomplete or errors occur, trigger investigation scripts
    to fill gaps and validate findings.
  backstory: >
    You are a meticulous quality assurance specialist for reconnaissance data.
    You never accept tool results at face value.

    Your responsibilities:
    1. VALIDATE: Check if tool results are complete and accurate
    2. ENRICH: Identify opportunities to gather more data
    3. INVESTIGATE: Generate Python scripts to probe gaps
    4. RECONCILE: Fix inconsistencies between different data sources
```

#### Logique metier

**Mission principale :** Valider les resultats des outils et combler les lacunes identifiees.

**Processus de reflection :**

```
1. Recevoir les resultats d'un outil (ex: Subfinder)
2. Analyser la completude:
   - Nombre de resultats attendu vs obtenu
   - Patterns manquants (pas de 'mail.*' ? bizarre)
   - Erreurs ou timeouts
3. Identifier les gaps:
   - Sources non interrogees
   - Sous-domaines communs absents
4. Proposer des actions d'enrichissement:
   - Script de bruteforce DNS
   - Retry avec timeout different
   - Source alternative
```

**Metriques de completude par outil :**

| Outil | Attendu (domaine moyen) | Seuil d'alerte |
|-------|------------------------|----------------|
| Subfinder | 20-100 sous-domaines | < 10 |
| HTTPX | 50-80% live | < 30% |
| Wayback | 50-500 URLs | < 20 |
| DNS | 100% resolution | < 90% |

#### Exemple d'output

```json
{
  "valid": true,
  "completeness_score": 0.65,
  "issues": [
    {"type": "low_count", "severity": "warning", "message": "Only 8 subdomains found for a .com domain"},
    {"type": "missing_pattern", "severity": "info", "message": "No 'mail.*' subdomain found"}
  ],
  "enrichment_opportunities": [
    {"type": "dns_bruteforce", "reason": "Low subdomain count suggests passive sources insufficient"},
    {"type": "certificate_transparency", "reason": "Additional CT logs may reveal more subdomains"}
  ],
  "suggested_actions": [
    {
      "action": "generate_script",
      "script_type": "dns_bruteforce",
      "targets": ["example.com"],
      "wordlist": "subdomains-top1million-5000.txt"
    }
  ]
}
```

---

## 7. Agents de Deep Verification

### 7.1 Vue d'ensemble du pipeline de verification

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEEP VERIFICATION PIPELINE                      │
│                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  │   TRIAGE    │───▶│  STACKMAP   │───▶│  VALIDATOR  │───▶│  CURATOR    │
│  │             │    │             │    │             │    │             │
│  │ Prioritize  │    │ Map stacks  │    │ Create plan │    │ Curate      │
│  │ targets     │    │ to modules  │    │ & execute   │    │ evidence    │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
│                                                                    │
│  Input:             Input:             Input:             Input:        │
│  - Graph vulns      - Targets          - Triage          - Check       │
│  - Risk scores      - Tech stacks      - Mappings        - Results     │
│                     - Modules                                          │
│                                                                    │
│  Output:            Output:            Output:            Output:       │
│  - Ranked targets   - Module           - Execution       - Status      │
│  - Priorities       - Assignments      - Plan            - Updates     │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 VULN_TRIAGE (Triage) - Le Trieur

**Fichier source :** `agent_factory.py:236-259`

#### Configuration

```python
def build_vuln_triage(target_domain: str, tools: list = None) -> Agent:
    return build_agent(
        agent_id="vuln_triage",
        role="Vulnerability Triage Specialist (Code Name: Triage)",
        goal=f"""Identify and prioritize THEORETICAL/LIKELY vulnerabilities in the {target_domain} graph
that should be verified with active checks. Output a ranked list of targets for validation.""",
        backstory="""You are the vulnerability triage expert.
Your prioritization criteria:
1. CVSS score / risk_score - higher scores first
2. Attack complexity - easier attacks first
3. Target accessibility - reachable HTTP services first
4. Evidence gaps - vulns with missing evidence need verification"""
    )
```

#### Logique metier

**Mission principale :** Identifier les vulnerabilites theoriques qui meritent verification.

**Criteres de priorisation :**

| Critere | Poids | Justification |
|---------|-------|---------------|
| Risk Score | 40% | Les vulns critiques d'abord |
| Complexite | 25% | ROI: facile = verification rapide |
| Accessibilite | 20% | Pas de verification si cible down |
| Evidence gaps | 15% | Vulns sans preuves = prioritaires |

**Statuts de vulnerabilite filtrés :**
- `THEORETICAL` : Hypothese basee sur patterns (a verifier)
- `LIKELY` : Evidence partielle (a confirmer)

(Les statuts `CONFIRMED`, `FALSE_POSITIVE`, `MITIGATED` sont exclus)

---

### 7.3 STACK_POLICY (StackMap) - Le Mappeur

**Fichier source :** `agent_factory.py:262-287`

#### Configuration

```python
def build_stack_policy(target_domain: str, tools: list = None) -> Agent:
    return build_agent(
        agent_id="stack_policy",
        role="Technology Stack Policy Mapper (Code Name: StackMap)",
        goal=f"""For each target in {target_domain}, map its technology stack to the appropriate
check modules from the registry. Ensure ROE compliance and proper module selection.""",
        backstory="""You are the technology stack expert.

Your knowledge:
- PHP: Check for LFI, RCE, config exposure
- Node.js/Express: Check for prototype pollution, SSRF
- Java/Spring: Check for deserialization, XXE
- .NET: Check for viewstate issues, path traversal
- WordPress: Check for plugin vulns, xmlrpc abuse
- Generic: Security headers, server disclosure, config files"""
    )
```

#### Logique metier

**Mission principale :** Associer chaque stack technologique aux modules de verification appropries.

**Matrice Stack → Modules :**

| Stack | Modules recommandes | Raison |
|-------|---------------------|--------|
| PHP | `lfi-01`, `rce-php-01`, `config-exposure-01` | Historique de vulns LFI/RCE |
| Node.js | `prototype-pollution-01`, `ssrf-01` | Vulns specifiques Node |
| Java/Spring | `xxe-01`, `deserialization-01` | Vulns XML et serialisation |
| .NET | `viewstate-01`, `path-traversal-01` | Vulns specifiques .NET |
| WordPress | `wp-plugin-01`, `xmlrpc-01` | CMS avec nombreux plugins vulns |
| Generic | `security-headers-01`, `server-info-01` | Applicable a tous |

**Modes ROE (Rules of Engagement) :**

| Mode | Restrictions | Modules autorises |
|------|--------------|-------------------|
| STEALTH | GET only, no payloads | Headers, info disclosure |
| BALANCED | GET + POST safe | + Config exposure, basic checks |
| AGGRESSIVE | All methods | + Intrusive checks, fuzzing |

---

### 7.4 VALIDATION_PLANNER (Validator) - Le Planificateur

**Fichier source :** `agent_factory.py:290-317`

#### Configuration

```python
def build_validation_planner(target_domain: str, tools: list = None) -> Agent:
    return build_agent(
        agent_id="validation_planner",
        role="Verification Plan Orchestrator (Code Name: Validator)",
        goal=f"""Create a comprehensive verification plan for {target_domain} that sequences
check module executions while respecting ROE constraints and optimizing for coverage.""",
        backstory="""Your planning principles:
1. IDEMPOTENCY: Same plan inputs = same plan outputs
2. ROE COMPLIANCE: Respect mode restrictions
3. RATE LIMITING: Space out checks to avoid detection
4. DEPENDENCY ORDERING: Some checks depend on others
5. PARALLEL SAFETY: Group independent checks for parallel execution"""
    )
```

#### Logique metier

**Mission principale :** Creer un plan d'execution ordonne et idempotent.

**Contraintes de planification :**

1. **Idempotence** : Le meme input produit toujours le meme plan
```python
plan_id = hash(sorted(targets) + sorted(modules) + roe_mode)
```

2. **Dependances** : Certains checks doivent s'executer avant d'autres
```
auth_check → admin_panel_check  (besoin de savoir si auth existe)
port_scan → service_enum        (besoin de connaitre les ports ouverts)
```

3. **Rate limiting** : Espacement entre les requetes
```
STEALTH: 5s entre chaque check
BALANCED: 1s entre chaque check
AGGRESSIVE: 0.1s entre chaque check
```

4. **Parallelisation** : Grouper les checks independants
```
Groupe 1 (parallel): security-headers-01, server-info-01
Groupe 2 (parallel): config-exposure-01, robots-check-01
Groupe 3 (sequential): auth-bypass-01 → admin-access-01
```

---

### 7.5 EVIDENCE_CURATOR (Curator) - Le Curateur

**Fichier source :** `agent_factory.py:320-349`

#### Configuration

```python
def build_evidence_curator(target_domain: str, tools: list = None) -> Agent:
    return build_agent(
        agent_id="evidence_curator",
        role="Evidence Curator and Status Arbiter (Code Name: Curator)",
        goal=f"""Review check results for {target_domain}, curate evidence with proper hashing,
determine final vulnerability status, and update the graph with proof.""",
        backstory="""Your responsibilities:
1. EVIDENCE VALIDATION: Verify evidence hash integrity
2. SECRET REDACTION: Ensure no sensitive data in stored evidence
3. STATUS DETERMINATION: Based on proof quality
4. GRAPH UPDATE: Write final status and evidence to graph
5. DEDUPLICATION: Use evidence hashes to prevent duplicate storage"""
    )
```

#### Logique metier

**Mission principale :** Valider les preuves et determiner le statut final des vulnerabilites.

**Processus de curation :**

```
1. Recevoir les resultats des checks
2. Pour chaque resultat:
   a. Valider l'integrite (hash SHA256)
   b. Redacter les secrets (passwords, tokens)
   c. Evaluer la qualite de la preuve
   d. Determiner le statut final
   e. Mettre a jour le graphe
3. Deduplication par hash
4. Generer le rapport de synthese
```

**Matrice de determination du statut :**

| Qualite de preuve | Evidence | Statut final |
|-------------------|----------|--------------|
| Exploit reussi | Request/Response complets | CONFIRMED |
| Indicateur fort | Headers revealeurs, patterns | LIKELY |
| Check negatif | Aucune anomalie | FALSE_POSITIVE |
| Corrige | Etait vuln, plus maintenant | MITIGATED |

**Redaction des secrets :**

```
Avant: "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
Apres: "Authorization: Bearer [REDACTED_JWT]"

Avant: "password=SuperSecret123!"
Apres: "password=[REDACTED_PASSWORD]"
```

---

## 8. Agents Utilitaires

### 8.1 CODE_SMITH (CodeSmith) - Le Generateur de Code

**Fichier source :** `agents.yaml:104-112`

#### Configuration

```yaml
code_smith:
  role: Expert Python Security Scripter (Code Name: CodeSmith)
  goal: Generate precise, secure, and executable Python scripts to solve specific gaps identified by the Orchestrator.
  backstory: >
    You are a specialized coding agent. You don't guess; you implement.
    You write scripts using `requests` and `BeautifulSoup` to extract specific data.
    You always output valid, minimal, error-handled Python code.
```

#### Logique metier

**Mission principale :** Generer des scripts Python pour combler les lacunes des outils standards.

**Cas d'utilisation :**
- Parser une page avec structure non-standard
- Extraire des donnees d'un format proprietaire
- Automatiser une sequence de requetes complexe

**Contraintes de generation :**
```python
# Libraries autorisees
import requests
from bs4 import BeautifulSoup
import re
import json

# Structure obligatoire
def main(target_url):
    try:
        # Implementation
        result = {...}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    import sys
    main(sys.argv[1])
```

---

### 8.2 VULN_ANALYST - L'Analyste Vulnerabilites

**Fichier source :** `agents.yaml:94-97`

#### Configuration

```yaml
vuln_analyst:
  role: Vulnerability Intelligence Analyst
  goal: Surgically test high-value targets for vulnerabilities using Nuclei and Ffuf.
  backstory: >
    A specialized security researcher who verifies attack vectors.
    You only test targets that are strictly in scope and high priority.
    You prefer precise, safe payloads.
```

#### Logique metier

**Mission principale :** Executer des tests de vulnerabilite cibles et precis.

**Outils utilises :**
- `NucleiTool` : Scan de vulnerabilites basé sur templates
- `FfufTool` : Fuzzing de directories et parametres

**Modes de scan :**
```yaml
STEALTH:
  - Templates: exposures, misconfigurations (GET only)
  - Rate: 10 req/s max

BALANCED:
  - Templates: + cves, default-logins
  - Rate: 50 req/s max

AGGRESSIVE:
  - Templates: + vulnerabilities, takeovers
  - Rate: 150 req/s max
```

---

### 8.3 PARAM_HUNTER - Le Chasseur de Parametres

**Fichier source :** `agents.yaml:99-102`

#### Configuration

```yaml
param_hunter:
  role: Parameter Intelligence Analyst
  goal: Analyze endpoints to extract potential parameters and exploit vectors
  backstory: >
    Expert in API behaviour, URL manipulation, and parameter fuzzing.
    You meticulously extract query parameters from URLs and infer POST bodies.
```

#### Logique metier

**Mission principale :** Identifier tous les parametres injectables d'un endpoint.

**Sources de parametres :**
```
URL Query:     /search?q=test&page=1     → q, page
Path Params:   /users/123/profile        → user_id (infere)
POST Body:     {"username": "", "pass":} → username, pass
Headers:       X-Custom-Header: value    → X-Custom-Header
Cookies:       session=abc123            → session
```

**Classification des parametres :**

| Type | Pattern | Risque |
|------|---------|--------|
| ID | `id`, `user_id`, `item` | IDOR/SQLI |
| Redirect | `url`, `redirect`, `next` | Open Redirect |
| File | `file`, `path`, `document` | LFI/Path Traversal |
| Search | `q`, `query`, `search` | SQLI/XSS |
| Debug | `debug`, `test`, `verbose` | Info Disclosure |

---

## 9. Systeme de Taches (Tasks)

### 9.1 Structure d'une tache

```python
# task_factory.py:63-86
def build_task(
    description: str,      # Instructions detaillees
    agent: Agent,          # Agent responsable
    expected_output: str,  # Format de sortie attendu
    context: List[Task],   # Taches fournissant du contexte
) -> Task:
```

### 9.2 Chaines de contexte

Les taches peuvent recevoir le contexte des taches precedentes :

```
enumeration_task (Pathfinder)
        │
        ▼ context
analysis_task (Watchtower)
        │
        ▼ context
dns_task (DNS Analyst)
        │
        ▼ context
fingerprint_task (StackTrace)
        │
        ▼ context
js_mining_task (DeepScript)
```

**Implementation :**
```python
# task_factory.py:112-141
def build_analysis_task(watchtower: Agent, target_domain: str, enumeration_task: Task = None) -> Task:
    context = [enumeration_task] if enumeration_task else []
    return build_task(
        description=f"""Analyze the subdomain enumeration results for {target_domain}...""",
        agent=watchtower,
        expected_output="""STRICT JSON array...""",
        context=context,  # Recoit les resultats de enumeration_task
    )
```

### 9.3 Exemple de tache complete

```python
# task_factory.py:216-258
def build_endpoint_intel_task(endpoint_intel: Agent, target_domain: str, context_tasks: List[Task] = None) -> Task:
    return build_task(
        description=f"""Analyze and enrich discovered endpoints for {target_domain}.

YOUR MISSION:
1. CONFIRM or ADJUST the 'category' (API, ADMIN, AUTH, PUBLIC, STATIC, LEGACY, HEALTHCHECK).
2. CONFIRM or ADJUST the 'likelihood_score' (0-10) and 'impact_score' (0-10).
3. COMPUTE the 'risk_score' (0-100) based on likelihood × impact.
4. SET 'auth_required' (true/false) if you can deduce it.
5. SET 'tech_stack_hint' if identifiable (e.g., "PHP", "Rails", "Node").
6. PROPOSE 0-3 attack hypotheses for high-risk endpoints.

CRITICAL CONSTRAINTS:
- You MUST NOT invent new endpoints or domains.
- You ONLY enrich the endpoints provided in the input.
- Maximum 3 hypotheses per endpoint.
- Scores must be: likelihood 0-10, impact 0-10, risk 0-100.

ATTACK_TYPE VALUES:
XXE, SQLI, XSS, IDOR, BOLA, AUTH_BYPASS, RATE_LIMIT, RCE, SSRF, LFI, RFI, CSRF, OPEN_REDIRECT, INFO_DISCLOSURE""",

        agent=endpoint_intel,

        expected_output="""STRICT JSON object:
{
  "endpoints": [
    {
      "endpoint_id": "endpoint:http:...",
      "category": "ADMIN",
      "likelihood_score": 7,
      "impact_score": 9,
      "risk_score": 63,
      "auth_required": true,
      "tech_stack_hint": "PHP",
      "hypotheses": [
        {"title": "...", "attack_type": "AUTH_BYPASS", "confidence": 0.7, "priority": 4}
      ]
    }
  ]
}""",
        context=context_tasks,
    )
```

---

## 10. Patterns Anti-Hallucination

### 10.1 Le probleme de l'hallucination

Les LLM peuvent generer des informations plausibles mais fausses. Dans un contexte de reconnaissance, cela peut :
- Creer des sous-domaines inexistants
- Inventer des vulnerabilites
- Generer de fausses preuves

### 10.2 Strategies implementees

#### A. Contraintes explicites dans le backstory

```yaml
# agents.yaml
CRITICAL CONSTRAINTS:
1. You MUST NOT invent new endpoints or domains.
2. You ONLY enrich the endpoints you are given.
3. You stay strictly within the target domain scope.
4. Your output MUST be valid JSON only, no preamble.
```

#### B. Rules dans les descriptions de taches

```yaml
# tasks.yaml
CRITICAL ANTI-HALLUCINATION RULES:
1. You MUST NOT invent any subdomain. Use STRICTLY the ones provided.
2. If the list is empty or contains no relevant assets, state it explicitly.
3. DO NOT guess subdomains that "should" exist (e.g., no 'admin.target.com'
   unless it appears in the input).
```

#### C. Validation cote code

```python
# graph_client.py:136-149
async def add_endpoint(self, path: str, ...) -> bool:
    # Filter out external URLs (CDNs, third-party services)
    if path.startswith("http"):
        parsed = urlparse(path)
        # Only accept endpoints from target domain
        if not parsed.netloc.endswith(self.target_domain):
            return False  # Silently reject out-of-scope
```

#### D. Format de sortie strict

```yaml
expected_output: >
  A STRICT JSON report containing the filtered list of discovered subdomains.
  The output MUST be the EXACT JSON returned by the tool.
  DO NOT summarize, do not wrap in markdown code blocks.
  CRITICAL:
  - If the tool says "subdomains": [], you MUST return [].
  - If the tool returns an error, you MUST return [].
  - DO NOT INVENT "example.com" or "test.com".
```

### 10.3 Exemples de formulations anti-hallucination

| Mauvaise formulation | Bonne formulation |
|----------------------|-------------------|
| "Find subdomains" | "Return ONLY subdomains from the tool output" |
| "Analyze the API" | "Analyze the API endpoints PROVIDED IN THE INPUT" |
| "Generate hypotheses" | "Generate MAX 3 hypotheses for EXISTING endpoints only" |
| "Return results" | "Return STRICT JSON, NO preamble, NO examples" |

---

## 11. Flux de Donnees Inter-Agents

### 11.1 Diagramme de flux complet

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FLUX DE DONNEES INTER-AGENTS                        │
│                                                                              │
│  TARGET_DOMAIN                                                               │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐                                                            │
│  │ PATHFINDER  │ ─────────────────────────────────────────────┐             │
│  │             │                                               │             │
│  │ Output:     │                                               │             │
│  │ [subdomains]│                                               │             │
│  └──────┬──────┘                                               │             │
│         │                                                      │             │
│         ▼                                                      │             │
│  ┌─────────────┐                                               │             │
│  │ WATCHTOWER  │                                               │             │
│  │             │                                               │             │
│  │ Input:      │                                               │             │
│  │ [subdomains]│                                               │             │
│  │             │                                               │             │
│  │ Output:     │                                               │             │
│  │ [{subdomain,│                                               │             │
│  │   priority, │                                               │             │
│  │   tag}]     │                                               │             │
│  └──────┬──────┘                                               │             │
│         │                                                      │             │
│    ┌────┴────┐                                                 │             │
│    │         │                                                 │             │
│    ▼         ▼                                                 │             │
│ ┌──────┐  ┌──────┐                                            │             │
│ │ DNS  │  │ ASN  │                                            │             │
│ │      │  │      │                                            │             │
│ └──┬───┘  └──┬───┘                                            │             │
│    │         │                                                 │             │
│    └────┬────┘                                                 │             │
│         │                                                      │             │
│         ▼                                                      │             │
│  ┌─────────────┐                                               │             │
│  │ STACKTRACE  │                                               │             │
│  │             │                                               │             │
│  │ Input:      │◄───────────────────────────────────────────────┤             │
│  │ [subdomains │  (filtre: priority >= 8)                      │             │
│  │  + DNS/ASN] │                                               │             │
│  │             │                                               │             │
│  │ Output:     │                                               │             │
│  │ [{subdomain,│                                               │             │
│  │   http_info,│                                               │             │
│  │   tech}]    │                                               │             │
│  └──────┬──────┘                                               │             │
│         │                                                      │             │
│    ┌────┴────┐                                                 │             │
│    │         │                                                 │             │
│    ▼         ▼                                                 │             │
│ ┌──────┐  ┌──────────┐                                        │             │
│ │  JS  │  │ ENDPOINT │                                        │             │
│ │MINER │  │ ANALYST  │                                        │             │
│ └──┬───┘  └────┬─────┘                                        │             │
│    │           │                                               │             │
│    └─────┬─────┘                                               │             │
│          │                                                     │             │
│          ▼                                                     │             │
│  ┌──────────────┐                                              │             │
│  │  RISKAWARE   │                                              │             │
│  │              │                                              │             │
│  │ Input:       │                                              │             │
│  │ [endpoints,  │                                              │             │
│  │  js_intel]   │                                              │             │
│  │              │                                              │             │
│  │ Output:      │                                              │             │
│  │ [{endpoint,  │                                              │             │
│  │   risk_score,│                                              │             │
│  │   hypotheses}│                                              │             │
│  └──────┬───────┘                                              │             │
│         │                                                      │             │
│         ▼                                                      │             │
│  ┌──────────────┐              ┌──────────────┐               │             │
│  │  OVERWATCH   │─────────────▶│   REFLECTOR  │◄──────────────┘             │
│  │              │  all data    │              │  validates all               │
│  │ Output:      │              │ Output:      │                             │
│  │ [attack_plans│              │ [validation, │                             │
│  │  + actions]  │              │  enrichment] │                             │
│  └──────────────┘              └──────────────┘                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Format des donnees echangees

#### Pathfinder → Watchtower

```json
["api.example.com", "admin.example.com", "www.example.com"]
```

#### Watchtower → StackTrace

```json
[
  {"subdomain": "admin.example.com", "priority": 9, "tag": "ADMIN", "category": "AUTH_PORTAL"},
  {"subdomain": "api.example.com", "priority": 8, "tag": "API", "category": "APP_BACKEND"}
]
```

#### StackTrace → JS Miner

```json
[
  {
    "subdomain": "admin.example.com",
    "priority": 9,
    "http": {
      "url": "https://admin.example.com",
      "status_code": 200,
      "technologies": ["PHP", "Laravel"]
    }
  }
]
```

#### RiskAware → Overwatch

```json
{
  "endpoints": [
    {
      "endpoint_id": "endpoint:https://admin.example.com/users",
      "category": "ADMIN",
      "risk_score": 72,
      "hypotheses": [
        {"title": "Auth bypass", "attack_type": "AUTH_BYPASS", "confidence": 0.7}
      ]
    }
  ]
}
```

---

## 12. Configuration et Personnalisation

### 12.1 Fichiers de configuration

| Fichier | Role | Localisation |
|---------|------|--------------|
| `agents.yaml` | Definition des agents | `services/recon-orchestrator/config/` |
| `tasks.yaml` | Definition des taches | `services/recon-orchestrator/config/` |
| `budget.yaml` | Limites et seuils | `services/recon-orchestrator/config/` |

### 12.2 Personnalisation d'un agent

Pour modifier le comportement d'un agent, editez son entry dans `agents.yaml` :

```yaml
# Exemple: Rendre Pathfinder plus agressif
pathfinder:
  role: Lead Reconnaissance Orchestrator (Code Name: Pathfinder)
  goal: >
    Map the COMPLETE attack surface of {target_domain} using ALL available sources.
    Leave no subdomain undiscovered.
  backstory: >
    You are the most thorough scout in existence.
    Your strategic objectives are:
    1. ABSOLUTE EXHAUSTIVENESS: Use recursive mode, all sources, no limits.
    2. AGGRESSIVE DISCOVERY: If in doubt, include the subdomain.
    3. SPEED: Prioritize coverage over precision.
```

### 12.3 Ajout d'un nouvel agent

1. **Definir dans `agents.yaml`** :
```yaml
my_new_agent:
  role: "Specialized Role"
  goal: "Specific measurable goal"
  backstory: "Context and constraints"
```

2. **Creer le builder dans `agent_factory.py`** :
```python
def build_my_new_agent(target_domain: str, tools: list = None) -> Agent:
    return build_agent(
        agent_id="my_new_agent",
        role="...",
        goal="...",
        backstory="...",
        tools=tools,
    )
```

3. **Creer la tache dans `task_factory.py`** :
```python
def build_my_new_task(agent: Agent, target_domain: str, context: List[Task] = None) -> Task:
    return build_task(
        description="...",
        agent=agent,
        expected_output="...",
        context=context,
    )
```

4. **Integrer dans `crew_runner.py`** :
```python
# Dans run_full_mission()
my_agent = build_my_new_agent(self.target_domain, [self.tools["my_tool"]])
my_task = build_my_new_task(my_agent, self.target_domain, [previous_task])
```

### 12.4 Tuning des parametres

#### Temperature LLM

```python
# llm_client.py
temperature=0.7  # Valeur par defaut

# Pour plus de creativite (hypotheses):
temperature=0.9

# Pour plus de precision (parsing):
temperature=0.3
```

#### Iterations maximum

```python
# agent_factory.py
max_iter=15  # Valeur par defaut

# Pour taches complexes:
max_iter=25

# Pour taches simples:
max_iter=10
```

#### Rate limiting

```python
# agent_factory.py
max_rpm=10  # Requetes par minute au LLM

# Si Ollama est lent:
max_rpm=5

# Si GPU puissant:
max_rpm=30
```

---

## Annexes

### A. Glossaire

| Terme | Definition |
|-------|------------|
| **Agent** | Entite autonome avec role, goal et backstory |
| **Task** | Mission specifique assignee a un agent |
| **Crew** | Groupe d'agents collaborant |
| **Tool** | Capacite d'action externe (API, commande) |
| **Backstory** | Contexte et personnalite de l'agent |
| **Hallucination** | Generation de fausses informations par le LLM |
| **ROE** | Rules of Engagement (regles d'engagement) |
| **OSINT** | Open Source Intelligence (renseignement sources ouvertes) |

### B. References

- [CrewAI Documentation](https://docs.crewai.com/)
- [LangChain Integration](https://python.langchain.com/)
- [Ollama Models](https://ollama.ai/library)

### C. Changelog

| Version | Date | Changements |
|---------|------|-------------|
| 3.2.1 | Dec 2025 | Ajout Reflection, Deep Verification |
| 3.2.0 | Dec 2025 | Nuclei integration, UI fixes |
| 3.1.0 | Nov 2025 | Event Envelope v2, SSE reconnect |

---

*Documentation generee pour Recon Gotham v3.2.1*
*Decembre 2025*
