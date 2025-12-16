"""
Endpoint Intel - Phase 23 endpoint enrichment and hypothesis generation
Full implementation with endpoint_heuristics engine
"""
import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import httpx
import structlog

logger = structlog.get_logger()
app = FastAPI(title="Endpoint Intel", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Service URLs
GRAPH_SERVICE = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")


class ExecuteRequest(BaseModel):
    mission_id: str
    target_domain: str
    mode: str = "aggressive"
    options: Dict[str, Any] = {}


# ============================================
# ENDPOINT HEURISTICS ENGINE
# ============================================

# Risk policy defaults
RISK_POLICY = {
    "pre_score_weights": {
        "category_admin": 10,
        "category_auth": 10,
        "category_api": 8,
        "legacy_extension": 4,
    },
    "likelihood_factors": {
        "external_exposure": 3,
        "no_auth": 3,
        "state_changing_method": 3,
        "historical_endpoint": 3,
    },
    "impact_factors": {
        "token_param": 4,
        "id_param": 3,
        "has_critical_param": 3,
    },
}


def categorize_endpoint(path: str, method: str = "GET", extension: str = None) -> str:
    """
    Determine endpoint category from path, method, and extension.
    Returns: API, ADMIN, AUTH, LEGACY, HEALTHCHECK, STATIC, PUBLIC, or UNKNOWN
    """
    path_lower = path.lower() if path else ""

    # Static assets (lowest priority)
    static_extensions = {".css", ".js", ".png", ".jpg", ".gif", ".ico", ".woff", ".woff2", ".svg"}
    if extension and extension.lower() in static_extensions:
        return "STATIC"

    # API detection
    api_patterns = ["/api/", "/api_", "/rest/", "/graphql", "/v1/", "/v2/", "/v3/", "/json", "/xml",
                    "api.", "/node/", "/rpc/", "/service/", "/endpoint/", "/data/", "/query/"]
    if any(p in path_lower for p in api_patterns):
        return "API"

    # Admin detection
    admin_patterns = ["/admin", "/portal", "/console", "/dashboard", "/manage", "/backend", "/control",
                      "/cms/", "/edit/", "/config", "/settings", "/panel", "/wp-admin", "/phpmyadmin"]
    if any(p in path_lower for p in admin_patterns):
        return "ADMIN"

    # Auth detection
    auth_patterns = ["/auth", "/login", "/logout", "/sso", "/oauth", "/signin", "/signup", "/register",
                     "/password", "/forgot", "/session", "/user/", "/account", "/membre", "/inscription"]
    if any(p in path_lower for p in auth_patterns):
        return "AUTH"

    # Legacy detection
    legacy_extensions = {".php", ".asp", ".aspx", ".jsp", ".cgi", ".pl", ".swf"}
    if extension and extension.lower() in legacy_extensions:
        return "LEGACY"

    # Healthcheck detection
    health_patterns = ["/health", "/ping", "/status", "/_health", "/ready", "/live"]
    if any(p in path_lower for p in health_patterns):
        return "HEALTHCHECK"

    return "UNKNOWN"


def extract_parameters(url: str, path: str) -> List[Dict]:
    """
    Extract parameters from URL query string and path patterns.
    """
    params = []

    # 1. Parse query string
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        for name in query_params.keys():
            param_info = _classify_param(name, "query")
            params.append(param_info)
    except Exception:
        pass

    # 2. Extract path parameters (patterns like /{id}, /{user_id})
    path_param_pattern = r'\{([^}]+)\}'
    matches = re.findall(path_param_pattern, path)
    for name in matches:
        param_info = _classify_param(name, "path")
        params.append(param_info)

    # 3. Detect numeric IDs in path (e.g., /users/123)
    numeric_pattern = r'/(\d{1,})(?:/|$)'
    if re.search(numeric_pattern, path):
        params.append({
            "name": "_numeric_id",
            "location": "path",
            "datatype_hint": "id",
            "sensitivity": "MEDIUM",
            "is_critical": False,
        })

    return params


def _classify_param(name: str, location: str) -> Dict:
    """Classify a parameter based on its name."""
    name_lower = name.lower()

    # High sensitivity patterns
    high_sens = ["token", "key", "secret", "password", "pwd", "auth", "session", "api_key", "apikey", "access_token", "bearer"]
    if any(p in name_lower for p in high_sens):
        return {
            "name": name,
            "location": location,
            "datatype_hint": "token",
            "sensitivity": "HIGH",
            "is_critical": True,
        }

    # Medium sensitivity (ID patterns)
    id_patterns = ["id", "user_id", "account_id", "uid", "email", "username", "phone", "user", "account"]
    if any(p in name_lower for p in id_patterns):
        return {
            "name": name,
            "location": location,
            "datatype_hint": "id",
            "sensitivity": "MEDIUM",
            "is_critical": False,
        }

    # Default: low sensitivity
    return {
        "name": name,
        "location": location,
        "datatype_hint": "string",
        "sensitivity": "LOW",
        "is_critical": False,
    }


def detect_behavior(method: str, params: List[Dict]) -> Tuple[str, bool]:
    """
    Determine endpoint behavior hint and id_based_access flag.
    """
    method = method.upper() if method else "GET"

    # Check for id-based access
    id_based = any(p.get("datatype_hint") == "id" for p in params)

    # Determine behavior
    state_changing_methods = {"POST", "PUT", "DELETE", "PATCH"}
    has_sensitive = any(p.get("sensitivity") in ("MEDIUM", "HIGH") for p in params)

    if method in state_changing_methods and has_sensitive:
        return "STATE_CHANGING", id_based
    elif id_based:
        return "ID_BASED_ACCESS", True
    elif method == "GET":
        return "READ_ONLY", id_based
    else:
        return "OTHER", id_based


def compute_prescores(
    category: str,
    params: List[Dict],
    behavior_hint: str,
    source: str = "UNKNOWN",
    method: str = "GET",
) -> Tuple[int, int, int]:
    """
    Compute likelihood, impact, and risk scores based on heuristics.
    Returns: (likelihood_score, impact_score, risk_score)
    """
    weights = RISK_POLICY.get("pre_score_weights", {})
    likelihood_factors = RISK_POLICY.get("likelihood_factors", {})
    impact_factors = RISK_POLICY.get("impact_factors", {})

    likelihood = 0
    impact = 0

    # Category-based scoring
    if category == "ADMIN":
        likelihood += 5
        impact += weights.get("category_admin", 10)
    elif category == "AUTH":
        likelihood += 4
        impact += weights.get("category_auth", 10)
    elif category == "API":
        likelihood += 3
        impact += weights.get("category_api", 8)
    elif category == "LEGACY":
        likelihood += weights.get("legacy_extension", 4)
        impact += 4

    # Parameter-based scoring
    for p in params:
        if p.get("sensitivity") == "HIGH":
            impact += impact_factors.get("token_param", 4)
        elif p.get("sensitivity") == "MEDIUM":
            impact += impact_factors.get("id_param", 3)
        if p.get("is_critical"):
            impact += impact_factors.get("has_critical_param", 3)

    # Behavior-based scoring
    if behavior_hint == "STATE_CHANGING":
        likelihood += likelihood_factors.get("state_changing_method", 3)
        impact += 3
    elif behavior_hint == "ID_BASED_ACCESS":
        likelihood += 3

    # Source-based scoring
    if source == "WAYBACK":
        likelihood += likelihood_factors.get("historical_endpoint", 3)

    # Clamp scores
    likelihood = max(0, min(10, likelihood))
    impact = max(0, min(10, impact))

    # Calculate risk score (matrix: likelihood * impact = 0-100)
    risk = likelihood * impact
    risk = max(0, min(100, risk))

    return likelihood, impact, risk


def _infer_auth_required(path: str, category: str, params: List[Dict]) -> str:
    """Infer whether authentication is likely required."""
    path_lower = path.lower() if path else ""

    # Public patterns
    public_patterns = ["/.well-known/", "/public/", "/static/", "/assets/", "/favicon", "/robots.txt"]
    if any(p in path_lower for p in public_patterns):
        return "false"

    # Auth-related endpoints
    if category in ("ADMIN", "AUTH"):
        if "/login" in path_lower or "/signin" in path_lower or "/signup" in path_lower or "/register" in path_lower:
            return "false"
        return "true"

    # API endpoints with ID-based access
    if category == "API":
        for p in params:
            if p.get("datatype_hint") == "id":
                return "true"

    # Has token/auth param
    for p in params:
        if p.get("is_critical") or p.get("sensitivity") == "HIGH":
            return "true"

    return "UNKNOWN"


def _infer_tech_stack(path: str, extension: str) -> str:
    """Infer technology stack from path and extension."""
    path_lower = path.lower() if path else ""
    ext = extension.lower() if extension else ""

    if ext == ".php":
        return "PHP"
    elif ext in (".asp", ".aspx"):
        return "ASP.NET"
    elif ext == ".jsp":
        return "Java/JSP"
    elif ext in (".cgi", ".pl"):
        return "Perl/CGI"

    if "/wp-" in path_lower or "/wordpress" in path_lower:
        return "WordPress/PHP"
    elif "/drupal" in path_lower:
        return "Drupal/PHP"
    elif "/graphql" in path_lower:
        return "GraphQL"
    elif "/api/v" in path_lower:
        return "REST API"

    return "Unknown"


def enrich_endpoint(
    endpoint_id: str,
    url: str,
    path: str,
    method: str,
    source: str,
    extension: str = None,
) -> Dict:
    """
    Full heuristic enrichment for a single endpoint.
    """
    # Categorize
    category = categorize_endpoint(path, method, extension)

    # Extract params
    params = extract_parameters(url, path)

    # Detect behavior
    behavior_hint, id_based_access = detect_behavior(method, params)

    # Compute scores
    likelihood, impact, risk = compute_prescores(category, params, behavior_hint, source, method)

    # Infer auth_required
    auth_required = _infer_auth_required(path, category, params)

    # Infer tech_stack_hint
    tech_stack_hint = _infer_tech_stack(path, extension)

    return {
        "endpoint_id": endpoint_id,
        "category": category,
        "likelihood_score": likelihood,
        "impact_score": impact,
        "risk_score": risk,
        "behavior_hint": behavior_hint,
        "id_based_access": id_based_access,
        "auth_required": auth_required,
        "tech_stack_hint": tech_stack_hint,
        "parameters": params,
    }


def generate_hypotheses(endpoint_id: str, enrichment: Dict) -> List[Dict]:
    """
    Generate vulnerability hypotheses based on endpoint enrichment.
    """
    hypotheses = []
    risk_score = enrichment.get("risk_score", 0)
    category = enrichment.get("category", "UNKNOWN")
    behavior = enrichment.get("behavior_hint", "")
    params = enrichment.get("parameters", [])

    # Only generate hypotheses for high-risk endpoints
    if risk_score < 30:
        return hypotheses

    # IDOR hypothesis for ID-based access
    if enrichment.get("id_based_access"):
        hypotheses.append({
            "type": "IDOR",
            "endpoint_id": endpoint_id,
            "priority": min(5, risk_score // 20),
            "confidence": 0.6,
            "description": f"ID-based access pattern detected. Potential IDOR vulnerability.",
            "status": "UNTESTED"
        })

    # Auth bypass for admin/auth endpoints
    if category in ("ADMIN", "AUTH") and risk_score >= 40:
        hypotheses.append({
            "type": "AUTH_BYPASS",
            "endpoint_id": endpoint_id,
            "priority": min(5, risk_score // 20),
            "confidence": 0.5,
            "description": f"Authentication endpoint with high risk. Potential auth bypass.",
            "status": "UNTESTED"
        })

    # SQLi hypothesis for state-changing with params
    if behavior == "STATE_CHANGING" and any(p.get("sensitivity") in ("MEDIUM", "HIGH") for p in params):
        hypotheses.append({
            "type": "SQLI",
            "endpoint_id": endpoint_id,
            "priority": min(5, risk_score // 20),
            "confidence": 0.4,
            "description": f"State-changing endpoint with sensitive parameters. Potential SQL injection.",
            "status": "UNTESTED"
        })

    # Brute force for auth endpoints
    if category == "AUTH" and "/login" in enrichment.get("endpoint_id", "").lower():
        hypotheses.append({
            "type": "BRUTE_FORCE",
            "endpoint_id": endpoint_id,
            "priority": 3,
            "confidence": 0.7,
            "description": "Login endpoint. Potential brute force target.",
            "status": "UNTESTED"
        })

    return hypotheses[:3]  # Max 3 hypotheses per endpoint


# ============================================
# ENDPOINT INTEL RUNNER
# ============================================
class EndpointIntelRunner:
    """Orchestrates endpoint intelligence phase"""

    def __init__(self, mission_id: str, target_domain: str, mode: str = "aggressive"):
        self.mission_id = mission_id
        self.target_domain = target_domain
        self.mode = mode
        self.results = {
            "endpoints_analyzed": 0,
            "endpoints_enriched": 0,
            "parameters_found": 0,
            "hypotheses_generated": 0,
            "category_distribution": {},
            "high_risk_count": 0,
            "errors": []
        }

    async def get_endpoints(self) -> List[Dict]:
        """Fetch endpoints from graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    params={"mission_id": self.mission_id, "type": "ENDPOINT"}
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("nodes", [])
            except Exception as e:
                logger.error("get_endpoints_failed", error=str(e))
        return []

    async def update_endpoint(self, endpoint_id: str, properties: Dict) -> bool:
        """Update endpoint node in graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.patch(
                    f"{GRAPH_SERVICE}/api/v1/nodes/{endpoint_id}",
                    json={"properties": properties}
                )
                return response.status_code in [200, 201]
            except Exception as e:
                logger.error("update_endpoint_failed", endpoint_id=endpoint_id, error=str(e))
                return False

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
        """Execute endpoint intelligence phase"""
        start_time = datetime.utcnow()

        # 1. Get all endpoints
        endpoints = await self.get_endpoints()
        self.results["endpoints_analyzed"] = len(endpoints)
        logger.info("endpoint_intel_started", endpoints=len(endpoints))

        if not endpoints:
            logger.warning("no_endpoints_found")
            return self._build_result(start_time)

        # 2. Enrich each endpoint
        for endpoint in endpoints:
            endpoint_id = endpoint.get("id", "")
            props = endpoint.get("properties", {})

            path = props.get("path", "")
            origin = props.get("origin", "")
            method = props.get("method", "GET")
            source = props.get("source", "UNKNOWN")

            # Get extension from path
            extension = None
            if "." in path.split("/")[-1]:
                extension = "." + path.split(".")[-1].split("?")[0]

            # Enrich endpoint
            url = f"{origin}{path}" if origin and path.startswith("/") else path
            enrichment = enrich_endpoint(endpoint_id, url, path, method, source, extension)

            # Update category distribution
            category = enrichment["category"]
            self.results["category_distribution"][category] = self.results["category_distribution"].get(category, 0) + 1

            # Track high-risk endpoints
            if enrichment["risk_score"] >= 50:
                self.results["high_risk_count"] += 1

            # Track parameters
            self.results["parameters_found"] += len(enrichment["parameters"])

            # Update endpoint in graph
            update_props = {
                "category": enrichment["category"],
                "likelihood_score": enrichment["likelihood_score"],
                "impact_score": enrichment["impact_score"],
                "risk_score": enrichment["risk_score"],
                "behavior_hint": enrichment["behavior_hint"],
                "id_based_access": enrichment["id_based_access"],
                "auth_required": enrichment["auth_required"],
                "tech_stack_hint": enrichment["tech_stack_hint"],
                "enriched_at": datetime.utcnow().isoformat()
            }

            await self.update_endpoint(endpoint_id, update_props)
            self.results["endpoints_enriched"] += 1

            # Publish parameters as nodes
            for param in enrichment["parameters"]:
                param_id = f"param:{endpoint_id}:{param['name']}"
                await self.publish_node(
                    "PARAMETER",
                    param_id,
                    {
                        "name": param["name"],
                        "location": param["location"],
                        "datatype_hint": param["datatype_hint"],
                        "sensitivity": param["sensitivity"],
                        "is_critical": param["is_critical"],
                        "endpoint_id": endpoint_id
                    }
                )
                await self.publish_edge(endpoint_id, param_id, "HAS_PARAMETER")

            # Generate and publish hypotheses
            hypotheses = generate_hypotheses(endpoint_id, enrichment)
            for hyp in hypotheses:
                hyp_id = f"hypothesis:{endpoint_id}:{hyp['type']}"
                await self.publish_node(
                    "HYPOTHESIS",
                    hyp_id,
                    {
                        "type": hyp["type"],
                        "priority": hyp["priority"],
                        "confidence": hyp["confidence"],
                        "description": hyp["description"],
                        "status": hyp["status"],
                        "endpoint_id": endpoint_id
                    }
                )
                await self.publish_edge(endpoint_id, hyp_id, "HAS_HYPOTHESIS")
                self.results["hypotheses_generated"] += 1

            logger.debug("endpoint_enriched",
                        endpoint_id=endpoint_id,
                        category=category,
                        risk_score=enrichment["risk_score"])

        return self._build_result(start_time)

    def _build_result(self, start_time: datetime) -> Dict:
        duration = (datetime.utcnow() - start_time).total_seconds()
        return {
            "phase": "endpoint_intel",
            "status": "completed",
            "duration": duration,
            "results": {
                "endpoints_analyzed": self.results["endpoints_analyzed"],
                "endpoints_enriched": self.results["endpoints_enriched"],
                "parameters": self.results["parameters_found"],
                "hypotheses": self.results["hypotheses_generated"],
                "high_risk_count": self.results["high_risk_count"],
                "category_distribution": self.results["category_distribution"],
                "errors": len(self.results["errors"])
            }
        }


# ============================================
# API ENDPOINTS
# ============================================
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "endpoint-intel", "version": "2.0.0"}


@app.get("/status")
async def status():
    return {
        "service": "endpoint-intel",
        "graph_service": GRAPH_SERVICE
    }


@app.post("/api/v1/execute")
async def execute(request: ExecuteRequest):
    """Execute endpoint intelligence - categorization, risk scoring, hypothesis generation"""
    logger.info("endpoint_intel_started",
                mission_id=request.mission_id,
                target=request.target_domain,
                mode=request.mode)

    runner = EndpointIntelRunner(
        mission_id=request.mission_id,
        target_domain=request.target_domain,
        mode=request.mode
    )

    result = await runner.run()

    logger.info("endpoint_intel_completed",
                mission_id=request.mission_id,
                endpoints_enriched=result["results"]["endpoints_enriched"],
                hypotheses=result["results"]["hypotheses"],
                duration=result["duration"])

    return result


@app.post("/api/v1/enrich")
async def enrich_single(endpoint: Dict[str, Any]):
    """Enrich a single endpoint (for testing/ad-hoc use)"""
    endpoint_id = endpoint.get("id", "")
    path = endpoint.get("path", "")
    origin = endpoint.get("origin", "")
    method = endpoint.get("method", "GET")
    source = endpoint.get("source", "UNKNOWN")

    extension = None
    if "." in path.split("/")[-1]:
        extension = "." + path.split(".")[-1].split("?")[0]

    url = f"{origin}{path}" if origin and path.startswith("/") else path
    enrichment = enrich_endpoint(endpoint_id, url, path, method, source, extension)
    hypotheses = generate_hypotheses(endpoint_id, enrichment)

    return {
        "enrichment": enrichment,
        "hypotheses": hypotheses
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
