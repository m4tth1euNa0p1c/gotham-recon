# Runbook – Contexte & Instructions (Recon-Gotham aligné Goal V4)

## 1) Contexte cible (docs/goal/gotham_goal.md)
- Vision: système agentique offensif avec Mission Controller + pipelines Recon (1-25) puis Ops (26-30), piloté par AssetGraph/TTP graph.
- Exigences: scope strict, opsec/budget, TTP-aware planner, audit trail, playbooks exploitation non exécutés sans validation.
- Phases ops à venir: exploitation orchestrée, pivot/post-exploitation, coverage check, proof/remediation, reporting multi-format.

## 2) État actuel du code (main.py)
- Phases 1-25 implémentées; Phase 23 scindée en 23A (Validation & PageAnalyzer, découvre endpoints/forms) puis 23B (Enrichment heuristique + hypothèses).
- Phase 25b: matérialise des VULNERABILITY nodes à partir d’hypothèses priorité >=4 (tested_by: HYPOTHESIS_ANALYSIS).
- Reporting: asset_graph + mission summary + metrics JSON en sortie; planner enrichit l’attaque plan; apex/seed fallback pour éviter run vide.

## 3) Lancer une mission (commande)
- Basique: `python run_mission.py <domaine> --mode stealth`
- Actif + seeds: `python run_mission.py <domaine> --mode aggressive --seed-file test/<seed>.txt`
- Prérequis: .env avec MODEL_NAME ou Ollama dispo; outils externes (subfinder/httpx/nuclei/ffuf) accessibles selon mode.

## 4) Checkpoints après run
- Fichiers: `recon_gotham/output/<dom>_asset_graph.json`, `<dom>_summary.md`, `<dom>_<run>_metrics.json`, logs structuré (ReconLogger) dans output.
- Attendu (run non vide): endpoints_enriched > 0, hypotheses > 0, vulnerabilities >= hypothèses priorité>=4, attack plan présent.
- Vérif rapide: ouvrir metrics JSON et compter `counts`, ou greper `"type": "VULNERABILITY"` dans asset_graph.

## 5) Debug rapide (phases 23/25)
- Si endpoints_enriched = 0: vérifier Phase 23A logs (PageAnalyzer reachable URLs), seeds/Wayback, scope filter (target_domain in URL).
- Si hypotheses = 0: vérifier risk_score >= threshold (budget.thresholds.min_risk_for_verification), catégories API/ADMIN/AUTH via endpoint_heuristics.
- Si vulnerabilities = 0: vérifier hypothèses priorité >=4 statut UNTESTED avant Phase 25; ajuster thresholds dans config/budget.yaml au besoin.

## 6) Alignement avec Goal V4 (prochaines taches)
- Ajouter gate OPSEC après 23B (budget/scope/engagement profile) pour autoriser Phase 25 et futures phases 26-30.
- Étendre Planner pour TTP-aware attack paths (mapping MITRE ATT&CK) et préparation playbooks exploitation (sans exécution auto).
- Esquisser Operations Pipeline (26-30) conforme goal: exploitation orchestrée, pivot, coverage, proof/remédiation, reporting.
- Brancher code_smith comme fallback systématique sur échec outil, avec logs auditables.

## 7) Rendu/présentation pro
- Consolider rapports: management (synthèse), technique (graph + endpoints + vulns), runbook (steps reproductibles) en sortie docs/output.
- Garder métriques RED/USE et SLO internes pour stabilité (latence, erreurs outils), utile pour un rendu type Palantir/ops.
