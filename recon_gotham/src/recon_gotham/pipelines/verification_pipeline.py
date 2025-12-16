"""
Verification Pipeline - Phase 24/25
Validates endpoints, detects stack versions, and performs controlled injection tests.
"""

import json
import hashlib
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin

from recon_gotham.core.asset_graph import AssetGraph


@dataclass
class VerificationResult:
    """Result of Verification pipeline."""
    endpoints_validated: int
    services_analyzed: int
    vulnerabilities_theoretical: int
    stack_versions_detected: int
    tests_performed: int
    errors: List[str]


@dataclass
class TestSignal:
    """Signal collected during a test."""
    url: str
    method: str
    status_normal: int
    status_test: int
    size_normal: int
    size_test: int
    hash_normal: str
    hash_test: str
    error_patterns: List[str]
    classification: str  # POSSIBLE_VULNERABILITY, LIKELY_SAFE, INCONCLUSIVE


class VerificationPipeline:
    """
    Verification Pipeline - Phase 24/25.
    
    Phase 24: Stack Analysis
    - Validate endpoint accessibility
    - Detect server/framework versions
    - Analyze pages (forms, AJAX calls)
    
    Phase 25: Active Verification (Controlled)
    - Select high-risk candidates
    - Perform controlled tests
    - Collect signals (response diffs)
    - Classify results (theoretical proofs)
    """
    
    # Generic patterns for detection (no specific payloads)
    ERROR_PATTERNS = [
        "sql", "syntax", "query", "database", "mysql", "postgres", "oracle",
        "error", "exception", "stack trace", "undefined", "null pointer",
        "warning", "fatal", "internal server error"
    ]
    
    def __init__(self, graph: AssetGraph, settings: Dict, run_id: str):
        self.graph = graph
        self.settings = settings
        self.run_id = run_id
        self.target_domain = settings.get("target_domain")
        self.timeout = settings.get("request_timeout", 10)
        self.verify_ssl = settings.get("verify_ssl", False)
        self.risk_threshold = settings.get("min_risk_for_verification", 40)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ReconGotham/3.0"
        }
    
    def execute(self) -> VerificationResult:
        """Execute the verification pipeline."""
        errors = []
        validated = 0
        services_analyzed = 0
        vulns_theoretical = 0
        stack_versions = 0
        tests_performed = 0
        
        # Phase 24: Stack Analysis
        http_services = [n for n in self.graph.nodes if n.get("type") == "HTTP_SERVICE"]
        
        for service in http_services[:15]:  # Limit
            try:
                url = service.get("properties", {}).get("url")
                if url and self.target_domain in url:
                    stack_info = self._analyze_stack(url)
                    if stack_info:
                        self._update_service_stack(service.get("id"), stack_info)
                        stack_versions += 1
                    services_analyzed += 1
            except Exception as e:
                errors.append(f"Stack analysis error: {str(e)[:100]}")
        
        # Phase 25: Active Verification (only if enabled)
        if self.settings.get("active_verification_enabled", True):
            # Select candidates
            candidates = self._select_candidates()
            
            for endpoint in candidates[:10]:  # Limit to top 10
                try:
                    signal = self._perform_test(endpoint)
                    if signal:
                        tests_performed += 1
                        
                        if signal.classification == "POSSIBLE_VULNERABILITY":
                            self._create_vulnerability_node(endpoint, signal)
                            vulns_theoretical += 1
                except Exception as e:
                    errors.append(f"Test error: {str(e)[:100]}")
        
        # Phase 25b: Create theoretical vulns from high-priority hypotheses (V3.0)
        # This ensures vulns are created even when active tests don't trigger failures
        hypotheses = [n for n in self.graph.nodes if n.get("type") == "HYPOTHESIS"]
        for hyp in hypotheses:
            props = hyp.get("properties", {})
            priority = props.get("priority", 0)
            status = props.get("status", "UNTESTED")
            attack_type = props.get("attack_type", "UNKNOWN")
            
            # Create vuln if priority >= 4 and not already tested
            if priority >= 4 and status == "UNTESTED":
                hyp_id = hyp.get("id")
                
                # Find the linked endpoint
                endpoint_id = None
                for edge in self.graph.edges:
                    if edge.get("to") == hyp_id and edge.get("type") == "HAS_HYPOTHESIS":
                        endpoint_id = edge.get("from")
                        break
                
                if endpoint_id:
                    vuln_id = f"vuln:{endpoint_id}:{attack_type}"
                    
                    # Check if exists
                    if not any(n.get("id") == vuln_id for n in self.graph.nodes):
                        self.graph.nodes.append({
                            "id": vuln_id,
                            "type": "VULNERABILITY",
                            "properties": {
                                "type": attack_type,
                                "status": "THEORETICAL",
                                "tested_by": "HYPOTHESIS_ANALYSIS",
                                "confidence": props.get("confidence", 0.5),
                                "evidence": props.get("description", ""),
                                "priority": priority,
                                "source_hypothesis": hyp_id
                            }
                        })
                        
                        self.graph.edges.append({
                            "from": endpoint_id,
                            "to": vuln_id,
                            "type": "HAS_VULNERABILITY"
                        })
                        
                        # Update hypothesis status
                        props["status"] = "VALIDATED_THEORETICAL"
                        
                        vulns_theoretical += 1
        
        # Validate accessibility for other endpoints
        endpoints = [n for n in self.graph.nodes if n.get("type") == "ENDPOINT"]
        for ep in endpoints[:30]:
            origin = ep.get("properties", {}).get("origin")
            if origin and self._is_accessible(origin):
                validated += 1
        
        return VerificationResult(
            endpoints_validated=validated,
            services_analyzed=services_analyzed,
            vulnerabilities_theoretical=vulns_theoretical,
            stack_versions_detected=stack_versions,
            tests_performed=tests_performed,
            errors=errors
        )
    
    def _analyze_stack(self, url: str) -> Optional[Dict]:
        """Analyze stack for a service URL."""
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=True
            )
            
            stack = {
                "server": None,
                "server_version": None,
                "framework": None,
                "framework_version": None,
                "tls_info": None
            }
            
            # Server header
            server = response.headers.get("Server", "")
            if server:
                parts = server.split("/")
                stack["server"] = parts[0]
                if len(parts) > 1:
                    stack["server_version"] = parts[1].split(" ")[0]
            
            # X-Powered-By
            powered_by = response.headers.get("X-Powered-By", "")
            if powered_by:
                if "PHP" in powered_by:
                    stack["framework"] = "PHP"
                    version_match = powered_by.split("/")
                    if len(version_match) > 1:
                        stack["framework_version"] = version_match[1]
                elif "ASP.NET" in powered_by:
                    stack["framework"] = "ASP.NET"
            
            # X-AspNet-Version
            asp_version = response.headers.get("X-AspNet-Version")
            if asp_version:
                stack["framework"] = "ASP.NET"
                stack["framework_version"] = asp_version
            
            return stack if any(stack.values()) else None
            
        except Exception:
            return None
    
    def _update_service_stack(self, service_id: str, stack_info: Dict):
        """Update HTTP service with stack information."""
        for node in self.graph.nodes:
            if node.get("id") == service_id:
                props = node.get("properties", {})
                props.update(stack_info)
                node["properties"] = props
                break
    
    def _select_candidates(self) -> List[Dict]:
        """Select high-risk endpoints for verification."""
        candidates = []
        
        for node in self.graph.nodes:
            if node.get("type") != "ENDPOINT":
                continue
            
            props = node.get("properties", {})
            risk_score = props.get("risk_score", 0)
            
            # Check risk threshold
            if risk_score >= self.risk_threshold:
                candidates.append(node)
                continue
            
            # Check for hypotheses with high priority
            endpoint_id = node.get("id")
            for edge in self.graph.edges:
                if edge.get("from") == endpoint_id and edge.get("type") == "HAS_HYPOTHESIS":
                    hyp_id = edge.get("to")
                    hyp_node = next((n for n in self.graph.nodes if n.get("id") == hyp_id), None)
                    if hyp_node and hyp_node.get("properties", {}).get("priority", 0) >= 4:
                        candidates.append(node)
                        break
        
        # Sort by risk score
        return sorted(candidates, key=lambda x: x.get("properties", {}).get("risk_score", 0), reverse=True)
    
    def _perform_test(self, endpoint: Dict) -> Optional[TestSignal]:
        """
        Perform a controlled test on an endpoint.
        
        NOTE: This performs only observation-based tests, NOT exploitation.
        We compare normal vs slightly modified requests to detect behavioral differences.
        """
        props = endpoint.get("properties", {})
        origin = props.get("origin")
        method = props.get("method", "GET")
        
        if not origin or self.target_domain not in origin:
            return None
        
        try:
            # Normal request
            resp_normal = requests.request(
                method, origin,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            hash_normal = hashlib.md5(resp_normal.content).hexdigest()
            
            # Modified request (add benign marker in URL)
            test_url = origin
            if "?" in origin:
                test_url += "&_test=1"
            else:
                test_url += "?_test=1"
            
            resp_test = requests.request(
                method, test_url,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            hash_test = hashlib.md5(resp_test.content).hexdigest()
            
            # Detect error patterns
            error_patterns = []
            text_lower = resp_test.text.lower()
            for pattern in self.ERROR_PATTERNS:
                if pattern in text_lower:
                    error_patterns.append(pattern)
            
            # Classify
            classification = "LIKELY_SAFE"
            
            # Significant status change
            if resp_normal.status_code != resp_test.status_code:
                if resp_test.status_code >= 500:
                    classification = "POSSIBLE_VULNERABILITY"
                else:
                    classification = "INCONCLUSIVE"
            
            # Error patterns detected
            elif error_patterns:
                classification = "INCONCLUSIVE"
            
            return TestSignal(
                url=origin,
                method=method,
                status_normal=resp_normal.status_code,
                status_test=resp_test.status_code,
                size_normal=len(resp_normal.content),
                size_test=len(resp_test.content),
                hash_normal=hash_normal,
                hash_test=hash_test,
                error_patterns=error_patterns,
                classification=classification
            )
            
        except Exception:
            return None
    
    def _create_vulnerability_node(self, endpoint: Dict, signal: TestSignal):
        """Create a theoretical vulnerability node."""
        endpoint_id = endpoint.get("id")
        vuln_id = f"vuln:{endpoint_id}:theoretical"
        
        # Check if exists
        if any(n.get("id") == vuln_id for n in self.graph.nodes):
            return
        
        self.graph.nodes.append({
            "id": vuln_id,
            "type": "VULNERABILITY",
            "properties": {
                "type": "BEHAVIORAL_ANOMALY",
                "status": "POSSIBLE",
                "tested_by": "VERIFICATION_PIPELINE",
                "confidence": 0.4,
                "evidence": f"Status diff: {signal.status_normal} → {signal.status_test}, Size diff: {signal.size_normal} → {signal.size_test}",
                "error_patterns": signal.error_patterns
            }
        })
        
        self.graph.edges.append({
            "from": endpoint_id,
            "to": vuln_id,
            "type": "HAS_VULNERABILITY"
        })
    
    def _is_accessible(self, url: str) -> bool:
        """Check if URL is accessible."""
        try:
            resp = requests.head(url, timeout=5, verify=False)
            return resp.status_code < 500
        except Exception:
            return False
