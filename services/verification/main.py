"""
Verification - Phase 24/25 controlled security testing
Full implementation with page_analyzer and security_tester
"""
import os
import re
import hashlib
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import httpx
import structlog

logger = structlog.get_logger()
app = FastAPI(title="Verification", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Service URLs
GRAPH_SERVICE = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")

# Limits
MAX_SERVICES_TO_PROBE = 15
MAX_ENDPOINTS_TO_TEST = 10
MIN_RISK_FOR_TESTING = 30


class ExecuteRequest(BaseModel):
    mission_id: str
    target_domain: str
    mode: str = "aggressive"
    options: Dict[str, Any] = {}


# ============================================
# PAGE ANALYZER (Phase 24)
# ============================================
class PageAnalyzer:
    """Deep page analysis for forms, APIs, and attack surface"""

    def analyze_url(self, url: str) -> Dict:
        """Analyze a URL for forms, API calls, and attack surface"""
        result = {
            "url": url,
            "reachable": False,
            "status_code": None,
            "response_time_ms": None,
            "forms": [],
            "api_endpoints": [],
            "technologies": [],
            "headers": {},
            "attack_surface": []
        }

        try:
            start = datetime.utcnow()
            resp = requests.get(url, timeout=10, verify=False, allow_redirects=True)
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000

            result["reachable"] = True
            result["status_code"] = resp.status_code
            result["response_time_ms"] = round(elapsed, 2)
            result["headers"] = dict(resp.headers)

            html = resp.text

            # Extract forms
            result["forms"] = self._extract_forms(html, url)

            # Extract API endpoints from JS
            result["api_endpoints"] = self._extract_api_calls(html)

            # Detect technologies from headers
            result["technologies"] = self._detect_technologies(resp.headers, html)

            # Build attack surface
            result["attack_surface"] = self._build_attack_surface(result)

        except Exception as e:
            result["error"] = str(e)

        return result

    def _extract_forms(self, html: str, base_url: str) -> List[Dict]:
        """Extract forms with fields"""
        forms = []

        for fm in re.finditer(r'<form([^>]*)>(.*?)</form>', html, re.IGNORECASE | re.DOTALL):
            attrs = fm.group(1)
            body = fm.group(2)

            # Extract action
            action_match = re.search(r'action=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            action = action_match.group(1) if action_match else ""

            # Extract method
            method_match = re.search(r'method=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            method = method_match.group(1).upper() if method_match else "GET"

            # Extract enctype
            enctype_match = re.search(r'enctype=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            enctype = enctype_match.group(1) if enctype_match else "application/x-www-form-urlencoded"

            # Extract fields
            fields = []
            for field in re.finditer(r'<input([^>]*)/?>', body, re.IGNORECASE):
                field_attrs = field.group(1)
                name_match = re.search(r'name=["\']([^"\']+)["\']', field_attrs, re.IGNORECASE)
                type_match = re.search(r'type=["\']([^"\']+)["\']', field_attrs, re.IGNORECASE)

                if name_match:
                    fields.append({
                        "name": name_match.group(1),
                        "type": type_match.group(1) if type_match else "text"
                    })

            # Also check textarea and select
            for field in re.finditer(r'<(textarea|select)([^>]*)>', body, re.IGNORECASE):
                name_match = re.search(r'name=["\']([^"\']+)["\']', field.group(2), re.IGNORECASE)
                if name_match:
                    fields.append({
                        "name": name_match.group(1),
                        "type": field.group(1).lower()
                    })

            forms.append({
                "action": action,
                "method": method,
                "enctype": enctype,
                "fields": fields,
                "has_password": any(f.get("type") == "password" for f in fields),
                "has_file_upload": enctype == "multipart/form-data"
            })

        return forms

    def _extract_api_calls(self, html: str) -> List[Dict]:
        """Extract API endpoints from JavaScript"""
        endpoints = []

        # Fetch patterns
        for m in re.finditer(r'fetch\s*\(\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
            endpoints.append({"path": m.group(1), "method": "GET", "source": "fetch"})

        # Axios patterns
        for m in re.finditer(r'axios\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
            endpoints.append({"path": m.group(2), "method": m.group(1).upper(), "source": "axios"})

        # XMLHttpRequest patterns
        for m in re.finditer(r'\.open\s*\(\s*["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
            endpoints.append({"path": m.group(2), "method": m.group(1).upper(), "source": "xhr"})

        return endpoints

    def _detect_technologies(self, headers: dict, html: str) -> List[str]:
        """Detect technologies from headers and HTML"""
        techs = []

        # Server header
        server = headers.get("Server", "")
        if "nginx" in server.lower():
            techs.append("Nginx")
        if "apache" in server.lower():
            techs.append("Apache")
        if "iis" in server.lower():
            techs.append("IIS")

        # X-Powered-By
        powered = headers.get("X-Powered-By", "")
        if "php" in powered.lower():
            techs.append("PHP")
        if "asp" in powered.lower():
            techs.append("ASP.NET")
        if "express" in powered.lower():
            techs.append("Express.js")

        # HTML patterns
        if "wp-content" in html or "wordpress" in html.lower():
            techs.append("WordPress")
        if "drupal" in html.lower():
            techs.append("Drupal")
        if "react" in html.lower() or "reactdom" in html.lower():
            techs.append("React")
        if "vue" in html.lower() or "v-if" in html:
            techs.append("Vue.js")
        if "angular" in html.lower() or "ng-" in html:
            techs.append("Angular")

        return list(set(techs))

    def _build_attack_surface(self, analysis: Dict) -> List[Dict]:
        """Build attack surface from analysis"""
        surface = []

        # Forms with sensitive fields
        for form in analysis.get("forms", []):
            if form.get("has_password"):
                surface.append({
                    "type": "AUTH_FORM",
                    "description": f"Login form found: {form.get('action')}",
                    "risk": "HIGH"
                })
            if form.get("has_file_upload"):
                surface.append({
                    "type": "FILE_UPLOAD",
                    "description": f"File upload form: {form.get('action')}",
                    "risk": "HIGH"
                })

        # API endpoints
        for ep in analysis.get("api_endpoints", []):
            if "admin" in ep.get("path", "").lower():
                surface.append({
                    "type": "ADMIN_API",
                    "description": f"Admin API endpoint: {ep.get('path')}",
                    "risk": "HIGH"
                })

        return surface


# ============================================
# SECURITY TESTER (Phase 25)
# ============================================
class SecurityTester:
    """Controlled security testing for endpoints"""

    # Safe test payloads (no actual exploitation)
    SAFE_PAYLOADS = {
        "sqli_probe": ["'", "''", "1' OR '1'='1", "1; --"],
        "xss_probe": ["<script>", "<img src=x>", "javascript:"],
        "lfi_probe": ["../", "..\\", "/etc/passwd"],
        "ssrf_probe": ["http://localhost", "http://127.0.0.1"],
    }

    def analyze_endpoint(self, endpoint: Dict) -> Dict:
        """Analyze endpoint for potential vulnerabilities"""
        result = {
            "endpoint_id": endpoint.get("id", ""),
            "potential_vulns": [],
            "test_signals": [],
            "recommended_tests": []
        }

        path = endpoint.get("properties", {}).get("path", "").lower()
        method = endpoint.get("properties", {}).get("method", "GET")
        category = endpoint.get("properties", {}).get("category", "UNKNOWN")
        risk_score = endpoint.get("properties", {}).get("risk_score", 0)

        # Analyze based on category
        if category == "ADMIN":
            result["potential_vulns"].append({
                "type": "AUTH_BYPASS",
                "confidence": 0.5,
                "reason": "Admin endpoint may have weak authentication"
            })
            result["recommended_tests"].append("nuclei_auth_scan")

        if category == "AUTH":
            result["potential_vulns"].append({
                "type": "BRUTE_FORCE",
                "confidence": 0.7,
                "reason": "Authentication endpoint susceptible to brute force"
            })
            result["recommended_tests"].append("nuclei_brute_force")

        if category == "API":
            result["potential_vulns"].append({
                "type": "IDOR",
                "confidence": 0.6,
                "reason": "API endpoint may have insecure direct object references"
            })
            result["recommended_tests"].append("ffuf_api_fuzz")

        # Path-based analysis
        if ".php" in path:
            result["potential_vulns"].append({
                "type": "LFI",
                "confidence": 0.4,
                "reason": "PHP endpoint may be vulnerable to LFI"
            })

        if "id=" in path or "{id}" in path:
            result["potential_vulns"].append({
                "type": "IDOR",
                "confidence": 0.6,
                "reason": "ID-based parameter detected"
            })

        if method in ["POST", "PUT"]:
            result["potential_vulns"].append({
                "type": "SQLI",
                "confidence": 0.4,
                "reason": "State-changing endpoint may be vulnerable to SQL injection"
            })

        return result

    def perform_safe_test(self, url: str, method: str = "GET") -> Dict:
        """Perform safe probing test (no actual exploitation)"""
        result = {
            "url": url,
            "baseline": None,
            "tests": [],
            "signals": []
        }

        try:
            # Get baseline response
            baseline_resp = requests.request(method, url, timeout=5, verify=False)
            result["baseline"] = {
                "status": baseline_resp.status_code,
                "size": len(baseline_resp.content),
                "hash": hashlib.md5(baseline_resp.content).hexdigest()[:16]
            }

            # Test with simple probe (just check if server behaves differently)
            test_url = url + ("&" if "?" in url else "?") + "test=1"
            test_resp = requests.request(method, test_url, timeout=5, verify=False)

            test_result = {
                "probe": "param_add",
                "status": test_resp.status_code,
                "size": len(test_resp.content),
                "hash": hashlib.md5(test_resp.content).hexdigest()[:16]
            }
            result["tests"].append(test_result)

            # Analyze signals
            if test_result["status"] != result["baseline"]["status"]:
                result["signals"].append({
                    "type": "STATUS_CHANGE",
                    "description": f"Status changed from {result['baseline']['status']} to {test_result['status']}"
                })

            if abs(test_result["size"] - result["baseline"]["size"]) > 100:
                result["signals"].append({
                    "type": "SIZE_CHANGE",
                    "description": f"Response size changed significantly"
                })

        except Exception as e:
            result["error"] = str(e)

        return result


# ============================================
# VERIFICATION RUNNER
# ============================================
class VerificationRunner:
    """Orchestrates verification phase"""

    def __init__(self, mission_id: str, target_domain: str, mode: str = "aggressive"):
        self.mission_id = mission_id
        self.target_domain = target_domain
        self.mode = mode
        self.page_analyzer = PageAnalyzer()
        self.security_tester = SecurityTester()
        self.results = {
            "services_probed": 0,
            "pages_analyzed": 0,
            "endpoints_tested": 0,
            "vulnerabilities_found": 0,
            "stack_versions": [],
            "errors": []
        }

    async def get_http_services(self) -> List[Dict]:
        """Fetch HTTP services from graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    params={"mission_id": self.mission_id, "type": "HTTP_SERVICE"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("nodes", [])
            except Exception as e:
                logger.error("get_http_services_failed", error=str(e))
        return []

    async def get_high_risk_endpoints(self) -> List[Dict]:
        """Fetch high-risk endpoints from graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    params={"mission_id": self.mission_id, "type": "ENDPOINT"}
                )
                if response.status_code == 200:
                    data = response.json()
                    endpoints = data.get("nodes", [])
                    # Filter by risk score
                    return [e for e in endpoints
                            if e.get("properties", {}).get("risk_score", 0) >= MIN_RISK_FOR_TESTING]
            except Exception as e:
                logger.error("get_endpoints_failed", error=str(e))
        return []

    async def get_hypotheses(self) -> List[Dict]:
        """Fetch hypotheses from graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    params={"mission_id": self.mission_id, "type": "HYPOTHESIS"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("nodes", [])
            except Exception as e:
                logger.error("get_hypotheses_failed", error=str(e))
        return []

    async def publish_node(self, node_type: str, node_id: str, properties: Dict) -> bool:
        """Publish a node to graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    json={
                        "id": node_id,
                        "type": node_type,
                        "mission_id": self.mission_id,
                        "properties": properties
                    }
                )
                return response.status_code in [200, 201]
            except Exception as e:
                logger.error("publish_node_failed", node_id=node_id, error=str(e))
                return False

    async def publish_edge(self, from_node: str, to_node: str, relation: str) -> bool:
        """Publish an edge to graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{GRAPH_SERVICE}/api/v1/edges",
                    json={
                        "from_node": from_node,
                        "to_node": to_node,
                        "relation": relation,
                        "mission_id": self.mission_id,
                        "properties": {}
                    }
                )
                return response.status_code in [200, 201]
            except Exception as e:
                logger.error("publish_edge_failed", error=str(e))
                return False

    async def run(self) -> Dict:
        """Execute verification phase"""
        start_time = datetime.utcnow()

        # Phase 24: Stack Analysis
        logger.info("phase_24_started", phase="stack_analysis")
        services = await self.get_http_services()

        for service in services[:MAX_SERVICES_TO_PROBE]:
            url = service.get("properties", {}).get("url") or service.get("id")
            if not url:
                continue

            analysis = self.page_analyzer.analyze_url(url)
            self.results["services_probed"] += 1

            if analysis.get("reachable"):
                self.results["pages_analyzed"] += 1

                # Store stack info
                for tech in analysis.get("technologies", []):
                    if tech not in self.results["stack_versions"]:
                        self.results["stack_versions"].append(tech)

                # Publish forms as endpoints
                for form in analysis.get("forms", []):
                    if form.get("action"):
                        form_id = f"endpoint:{url}{form['action']}"
                        await self.publish_node(
                            "ENDPOINT",
                            form_id,
                            {
                                "path": form["action"],
                                "method": form["method"],
                                "source": "PAGE_ANALYZER",
                                "origin": url,
                                "is_form": True,
                                "has_password": form.get("has_password", False),
                                "has_file_upload": form.get("has_file_upload", False)
                            }
                        )
                        await self.publish_edge(url, form_id, "EXPOSES_ENDPOINT")

        logger.info("phase_24_completed",
                   services_probed=self.results["services_probed"],
                   pages_analyzed=self.results["pages_analyzed"])

        # Phase 25: Active Verification (only in aggressive mode)
        if self.mode == "aggressive":
            logger.info("phase_25_started", phase="active_verification")

            endpoints = await self.get_high_risk_endpoints()
            logger.info("high_risk_endpoints", count=len(endpoints))

            for endpoint in endpoints[:MAX_ENDPOINTS_TO_TEST]:
                endpoint_id = endpoint.get("id", "")
                props = endpoint.get("properties", {})

                # Analyze endpoint
                analysis = self.security_tester.analyze_endpoint(endpoint)
                self.results["endpoints_tested"] += 1

                # Create vulnerabilities from high-confidence findings
                for vuln in analysis.get("potential_vulns", []):
                    if vuln.get("confidence", 0) >= 0.5:
                        vuln_id = f"vuln:{endpoint_id}:{vuln['type']}"
                        await self.publish_node(
                            "VULNERABILITY",
                            vuln_id,
                            {
                                "name": vuln["type"],
                                "severity": "MEDIUM" if vuln.get("confidence", 0) < 0.7 else "HIGH",
                                "confidence": vuln["confidence"],
                                "reason": vuln["reason"],
                                "status": "THEORETICAL",
                                "endpoint_id": endpoint_id,
                                "discovered_at": datetime.utcnow().isoformat()
                            }
                        )
                        await self.publish_edge(vuln_id, endpoint_id, "AFFECTS_ENDPOINT")
                        self.results["vulnerabilities_found"] += 1

            # Phase 25b: Convert high-priority hypotheses to vulnerabilities
            hypotheses = await self.get_hypotheses()
            for hyp in hypotheses:
                props = hyp.get("properties", {})
                if props.get("priority", 0) >= 4 and props.get("status") == "UNTESTED":
                    vuln_id = f"vuln:{hyp['id']}"
                    await self.publish_node(
                        "VULNERABILITY",
                        vuln_id,
                        {
                            "name": props.get("type", "UNKNOWN"),
                            "severity": "MEDIUM",
                            "confidence": props.get("confidence", 0.5),
                            "reason": props.get("description", ""),
                            "status": "THEORETICAL",
                            "from_hypothesis": hyp["id"],
                            "discovered_at": datetime.utcnow().isoformat()
                        }
                    )
                    endpoint_id = props.get("endpoint_id", "")
                    if endpoint_id:
                        await self.publish_edge(vuln_id, endpoint_id, "AFFECTS_ENDPOINT")
                    self.results["vulnerabilities_found"] += 1

            logger.info("phase_25_completed",
                       endpoints_tested=self.results["endpoints_tested"],
                       vulnerabilities=self.results["vulnerabilities_found"])

        duration = (datetime.utcnow() - start_time).total_seconds()

        return {
            "phase": "verification",
            "status": "completed",
            "duration": duration,
            "results": {
                "services_probed": self.results["services_probed"],
                "pages_analyzed": self.results["pages_analyzed"],
                "endpoints_tested": self.results["endpoints_tested"],
                "vulnerabilities": self.results["vulnerabilities_found"],
                "stack_versions": self.results["stack_versions"],
                "errors": len(self.results["errors"])
            }
        }


# ============================================
# API ENDPOINTS
# ============================================
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "verification", "version": "2.0.0"}


@app.get("/status")
async def status():
    return {
        "service": "verification",
        "graph_service": GRAPH_SERVICE
    }


@app.post("/api/v1/execute")
async def execute(request: ExecuteRequest):
    """Execute verification - controlled tests, vulnerability materialization"""
    logger.info("verification_started",
                mission_id=request.mission_id,
                target=request.target_domain,
                mode=request.mode)

    runner = VerificationRunner(
        mission_id=request.mission_id,
        target_domain=request.target_domain,
        mode=request.mode
    )

    result = await runner.run()

    logger.info("verification_completed",
                mission_id=request.mission_id,
                vulnerabilities=result["results"]["vulnerabilities"],
                duration=result["duration"])

    return result


@app.post("/api/v1/analyze-page")
async def analyze_page(url: str):
    """Analyze a single page (for testing)"""
    analyzer = PageAnalyzer()
    return analyzer.analyze_url(url)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
