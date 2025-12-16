"""
Endpoint Intelligence Pipeline - Phase 23 V2.3+
Enriches endpoints with risk scores, categories, parameters, and hypotheses.
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass

from recon_gotham.core.asset_graph import AssetGraph
from recon_gotham.core.endpoint_heuristics import enrich_endpoint


@dataclass
class EndpointIntelResult:
    """Result of Endpoint Intelligence pipeline."""
    endpoints_analyzed: int
    endpoints_enriched: int
    high_risk_count: int
    parameters_found: int
    hypotheses_generated: int
    category_distribution: Dict[str, int]
    errors: List[str]


class EndpointIntelPipeline:
    """
    Endpoint Intelligence Pipeline - Phase 23.
    
    Enriches each endpoint with:
    - category (API, ADMIN, AUTH, LEGACY, STATIC, UNKNOWN)
    - likelihood_score, impact_score, risk_score
    - auth_required hint
    - tech_stack_hint
    - behavior_hint
    - parameters (extracted from path/query)
    - hypotheses (potential vulnerabilities)
    """
    
    def __init__(self, graph: AssetGraph, settings: Dict, run_id: str):
        self.graph = graph
        self.settings = settings
        self.run_id = run_id
        self.target_domain = settings.get("target_domain")
        self.risk_threshold = settings.get("min_risk_for_active_scan", 30)
    
    def execute(self) -> EndpointIntelResult:
        """
        Execute endpoint intelligence enrichment.
        
        Returns:
            EndpointIntelResult with statistics
        """
        errors = []
        enriched_count = 0
        params_count = 0
        hypotheses_count = 0
        categories = {}
        
        # Get all endpoints
        endpoints = [n for n in self.graph.nodes if n.get("type") == "ENDPOINT"]
        
        for node in endpoints:
            try:
                props = node.get("properties", {})
                endpoint_id = node.get("id")
                
                # Extract fields
                path = props.get("path", "")
                origin = props.get("origin", "")
                method = props.get("method", "GET")
                source = props.get("source", "UNKNOWN")
                
                # Determine extension
                extension = None
                if "." in path.split("/")[-1]:
                    extension = "." + path.split(".")[-1].lower()
                
                # Apply heuristics enrichment
                enrichment = enrich_endpoint(
                    endpoint_id=endpoint_id,
                    url=origin,
                    path=path,
                    method=method,
                    source=source,
                    extension=extension,
                    existing_properties=props
                )
                
                # Update graph
                self.graph.update_endpoint_metadata(
                    endpoint_id=endpoint_id,
                    category=enrichment.get("category"),
                    risk_score=enrichment.get("risk_score"),
                    likelihood_score=enrichment.get("likelihood_score"),
                    impact_score=enrichment.get("impact_score"),
                    auth_required=enrichment.get("auth_required"),
                    tech_stack_hint=enrichment.get("tech_stack_hint"),
                    behavior=enrichment.get("behavior")
                )
                
                # Track category distribution
                cat = enrichment.get("category", "UNKNOWN")
                categories[cat] = categories.get(cat, 0) + 1
                
                # Add parameters
                for param in enrichment.get("parameters", []):
                    self.graph.add_parameter_v2(
                        endpoint_id=endpoint_id,
                        name=param.get("name"),
                        location=param.get("location", "query"),
                        datatype_hint=param.get("datatype_hint", "unknown"),
                        sensitivity=param.get("sensitivity", "LOW"),
                        is_critical=param.get("is_critical", False)
                    )
                    params_count += 1
                
                # Generate hypotheses for high-risk endpoints
                if enrichment.get("risk_score", 0) >= self.risk_threshold:
                    hyps = self._generate_hypotheses(enrichment, path)
                    for hyp in hyps:
                        self._add_hypothesis(endpoint_id, hyp)
                        hypotheses_count += 1
                
                enriched_count += 1
                
            except Exception as e:
                errors.append(f"Error enriching endpoint: {str(e)[:100]}")
        
        # Count high-risk
        high_risk = len([
            n for n in self.graph.nodes 
            if n.get("type") == "ENDPOINT" 
            and n.get("properties", {}).get("risk_score", 0) >= 70
        ])
        
        return EndpointIntelResult(
            endpoints_analyzed=len(endpoints),
            endpoints_enriched=enriched_count,
            high_risk_count=high_risk,
            parameters_found=params_count,
            hypotheses_generated=hypotheses_count,
            category_distribution=categories,
            errors=errors
        )
    
    def _generate_hypotheses(self, enrichment: Dict, path: str) -> List[Dict]:
        """Generate vulnerability hypotheses for an endpoint."""
        hypotheses = []
        category = enrichment.get("category", "")
        behavior = enrichment.get("behavior_hint", "")  # Fixed: was "behavior"
        params = enrichment.get("parameters", [])
        
        # ID-based access → IDOR
        if behavior == "ID_BASED_ACCESS":
            hypotheses.append({
                "attack_type": "IDOR",
                "title": "Potential Insecure Direct Object Reference",
                "description": f"Endpoint uses ID-based access pattern: {path}",
                "confidence": 0.6,
                "priority": 3
            })
        
        # Admin endpoints → Auth Bypass
        if category == "ADMIN":
            hypotheses.append({
                "attack_type": "AUTH_BYPASS",
                "title": "Potential Authentication Bypass",
                "description": f"Administrative endpoint detected: {path}",
                "confidence": 0.5,
                "priority": 4
            })
        
        # Auth endpoints → Credential attacks
        if category == "AUTH":
            hypotheses.append({
                "attack_type": "BRUTE_FORCE",
                "title": "Potential Brute Force Attack Surface",
                "description": f"Authentication endpoint detected: {path}",
                "confidence": 0.6,
                "priority": 5
            })
        
        # API endpoints with parameters → SQLi/XSS
        if category == "API" and params:
            for param in params:
                if param.get("sensitivity") in ["MEDIUM", "HIGH"]:
                    hypotheses.append({
                        "attack_type": "SQLI",
                        "title": f"Potential SQL Injection in parameter '{param.get('name')}'",
                        "description": f"Sensitive parameter detected on API endpoint",
                        "confidence": 0.4,
                        "priority": 4
                    })
        
        # Legacy PHP/ASP → Code Injection
        if enrichment.get("tech_stack_hint") in ["PHP", "ASP.NET"]:
            hypotheses.append({
                "attack_type": "CODE_INJECTION",
                "title": "Potential Code Injection",
                "description": f"Legacy technology stack detected: {enrichment.get('tech_stack_hint')}",
                "confidence": 0.3,
                "priority": 3
            })
        
        return hypotheses[:3]  # Limit to 3 per endpoint
    
    def _add_hypothesis(self, endpoint_id: str, hypothesis: Dict):
        """Add a hypothesis node to the graph."""
        hyp_id = f"hypothesis:{endpoint_id}:{hypothesis.get('attack_type')}"
        
        # Check if already exists
        existing = [n for n in self.graph.nodes if n.get("id") == hyp_id]
        if existing:
            return
        
        # Add node
        self.graph.nodes.append({
            "id": hyp_id,
            "type": "HYPOTHESIS",
            "properties": {
                "attack_type": hypothesis.get("attack_type"),
                "title": hypothesis.get("title"),
                "description": hypothesis.get("description"),
                "confidence": hypothesis.get("confidence"),
                "priority": hypothesis.get("priority"),
                "status": "UNTESTED"
            }
        })
        
        # Add edge
        self.graph.edges.append({
            "from": endpoint_id,
            "to": hyp_id,
            "type": "HAS_HYPOTHESIS"
        })
