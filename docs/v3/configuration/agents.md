# Configuration des Agents CrewAI

> **Documentation de la configuration des agents de reconnaissance**

---

## Vue d'Ensemble

Les agents CrewAI sont définis dans `config/agents.yaml`. Chaque agent a un rôle spécifique dans le pipeline de reconnaissance.

---

## Agents Disponibles

### Pathfinder

**Rôle**: Lead Reconnaissance Orchestrator

```yaml
pathfinder:
  role: "Lead Reconnaissance Orchestrator"
  goal: >
    Discover all subdomains, DNS records, and infrastructure
    information for the target domain using passive techniques.
  backstory: >
    You are an elite reconnaissance specialist with decades of
    experience in passive information gathering. Your methods are
    silent and leave no traces on target systems.
  tools:
    - subfinder
    - dns_resolver
  verbose: true
  allow_delegation: false
```

**Responsabilités**:
- Découverte de sous-domaines via Subfinder
- Résolution DNS initiale
- Coordination de la phase passive

### Watchtower

**Rôle**: Senior Intelligence Analyst

```yaml
watchtower:
  role: "Senior Intelligence Analyst"
  goal: >
    Analyze DNS records, ASN information, and organizational data
    to build a comprehensive intelligence picture.
  backstory: >
    You excel at connecting dots between disparate pieces of
    information. Your analysis has uncovered hidden infrastructure
    that others miss.
  tools:
    - dns_intel
    - asn_lookup
  verbose: true
  allow_delegation: false
```

**Responsabilités**:
- Analyse DNS approfondie (tous types d'enregistrements)
- Lookup ASN et informations organisationnelles
- Corrélation des données d'infrastructure

### StackTrace (Tech Fingerprinter)

**Rôle**: Senior Tech Fingerprinter

```yaml
tech_fingerprinter:
  role: "Senior Tech Fingerprinter (Code Name: StackTrace)"
  goal: >
    Identify technologies, frameworks, and server configurations
    by probing HTTP services.
  backstory: >
    Your expertise in technology fingerprinting is unmatched. A single
    HTTP response tells you everything about the target's tech stack.
  tools:
    - httpx
  verbose: true
  allow_delegation: false
```

**Responsabilités**:
- Probing HTTP des sous-domaines
- Détection des technologies (headers, signatures)
- Extraction des titres et status codes

### DeepScript (JS Intel)

**Rôle**: JavaScript Intelligence Miner

```yaml
js_intel:
  role: "JavaScript Intelligence Miner (Code Name: DeepScript)"
  goal: >
    Mine JavaScript files for API endpoints, secrets, and
    sensitive configuration data.
  backstory: >
    You can read obfuscated JavaScript like plain English. Hidden
    API keys and endpoints cannot escape your analysis.
  tools:
    - js_miner
  verbose: true
  allow_delegation: false
```

**Responsabilités**:
- Mining des fichiers JavaScript
- Extraction des endpoints API
- Recherche de secrets (API keys, tokens)

### DeepDive (Page Analyzer)

**Rôle**: Deep Page Intelligence Analyst

```yaml
page_analyzer:
  role: "Deep Page Intelligence Analyst (Code Name: DeepDive)"
  goal: >
    Perform deep analysis of web pages to extract forms, APIs,
    authentication mechanisms, and backend interaction points.
  backstory: >
    You see beyond what others see in a web page. Every form, every
    hidden input, every API call tells a story of the backend.
  tools:
    - page_analyzer
  verbose: true
  allow_delegation: false
```

**Responsabilités**:
- Analyse de formulaires HTML
- Détection des mécanismes d'authentification
- Extraction des points d'interaction backend

### Endpoint Intel

**Rôle**: Endpoint Intelligence Specialist

```yaml
endpoint_intel:
  role: "Endpoint Intelligence Specialist"
  goal: >
    Analyze and enrich discovered endpoints with risk scores,
    categories, and security hypotheses.
  backstory: >
    Your pattern recognition skills identify risky endpoints
    instantly. You've seen every vulnerability pattern there is.
  tools: []
  verbose: true
  allow_delegation: false
```

**Responsabilités**:
- Catégorisation des endpoints (API, ADMIN, AUTH, etc.)
- Calcul des scores de risque
- Génération d'hypothèses de sécurité

### Coder Agent

**Rôle**: Adaptive Code Intelligence

```yaml
coder_agent:
  role: "Adaptive Code Intelligence (Code Name: Coder)"
  goal: >
    Generate and execute Python scripts when standard tools fail
    or when custom analysis is needed.
  backstory: >
    When others hit a wall, you write the code to break through.
    Your scripts have solved problems nobody thought possible.
  tools:
    - python_executor
  verbose: true
  allow_delegation: false
```

**Responsabilités**:
- Génération de scripts Python à la demande
- Analyse personnalisée
- Fallback quand les outils standard échouent

---

## Configuration des Outils

### subfinder_tool

```yaml
subfinder:
  name: "Subfinder Tool"
  description: "Passive subdomain enumeration using multiple sources"
  timeout: 120
  sources:
    - certspotter
    - hackertarget
    - threatcrowd
    - urlscan
    - virustotal
```

### httpx_tool

```yaml
httpx:
  name: "HTTPX Tool"
  description: "Fast HTTP probing with technology detection"
  timeout: 30
  threads: 50
  options:
    status_code: true
    title: true
    tech_detect: true
    follow_redirects: true
```

### dns_resolver_tool

```yaml
dns_resolver:
  name: "DNS Resolver Tool"
  description: "DNS resolution for multiple record types"
  record_types:
    - A
    - AAAA
    - CNAME
    - MX
    - TXT
    - NS
    - SOA
  timeout: 10
```

### js_miner_tool

```yaml
js_miner:
  name: "JavaScript Miner Tool"
  description: "Extract endpoints and secrets from JavaScript"
  patterns:
    endpoints:
      - "/api/"
      - "/v1/"
      - "/graphql"
    secrets:
      - "api_key"
      - "token"
      - "secret"
```

### wayback_tool

```yaml
wayback:
  name: "Wayback Tool"
  description: "Historical URL discovery via Wayback Machine"
  max_results: 500
  filter_extensions:
    - js
    - json
    - xml
    - php
    - asp
```

---

## Personnalisation

### Ajouter un Nouvel Agent

1. Définir l'agent dans `config/agents.yaml`:

```yaml
my_custom_agent:
  role: "Custom Role"
  goal: "What the agent should accomplish"
  backstory: "Background story for context"
  tools:
    - tool_name
  verbose: true
  allow_delegation: false
```

2. Créer la tâche dans `config/tasks.yaml`:

```yaml
my_custom_task:
  description: "Task description with {target_domain}"
  agent: my_custom_agent
  expected_output: "Expected output format"
```

3. Intégrer dans le pipeline (`main.py` ou pipeline dédié)

### Modifier un Agent Existant

```yaml
pathfinder:
  role: "Modified Role"
  goal: "Updated goal"
  backstory: "New backstory"
  tools:
    - subfinder
    - dns_resolver
    - new_tool  # Ajouter un nouvel outil
  verbose: true
  allow_delegation: true  # Permettre la délégation
```

---

## Bonnes Pratiques

### Goals

- Être spécifique sur l'objectif
- Inclure le contexte de sécurité
- Mentionner les contraintes (passif vs actif)

### Backstory

- Donner de la personnalité à l'agent
- Inclure l'expertise relevant
- Créer un contexte pour les décisions

### Tools

- Lister uniquement les outils nécessaires
- Configurer les timeouts appropriés
- Documenter les dépendances

---

## Debugging

### Logs Verbeux

```yaml
pathfinder:
  verbose: true  # Activer les logs détaillés
```

### Désactiver un Agent

```yaml
disabled_agent:
  enabled: false  # Ne sera pas exécuté
```

### Tester un Agent

```python
# test_agent.py
from crewai import Agent
from config import load_agents

agents = load_agents()
pathfinder = agents['pathfinder']

# Test isolé
result = pathfinder.execute_task(
    task="Discover subdomains for example.com"
)
print(result)
```
