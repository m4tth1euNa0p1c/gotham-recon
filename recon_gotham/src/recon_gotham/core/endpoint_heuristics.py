"""
Phase 23: Endpoint Heuristics Engine
Provides deterministic pre-IA scoring and categorization for endpoints.
"""

import re
import yaml
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Tuple, Optional


def load_risk_policy() -> Dict:
    """Load risk policy from YAML config."""
    policy_path = Path(__file__).parent.parent / "config" / "risk_policies" / "endpoints.yaml"
    if policy_path.exists():
        with open(policy_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    # Return defaults if file not found
    return {
        "pre_score_weights": {
            "category_admin": 10,
            "category_auth": 10,
            "category_api": 8,
        },
        "likelihood_factors": {"external_exposure": 3, "no_auth": 3},
        "impact_factors": {"token_param": 4, "id_param": 3},
        "risk_formula": {"mode": "weighted_max", "likelihood_weight": 0.6, "impact_weight": 0.8},
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
    
    # API detection (expanded patterns)
    api_patterns = ["/api/", "/api_", "/rest/", "/graphql", "/v1/", "/v2/", "/v3/", "/json", "/xml", 
                   "api.", "/node/", "/rpc/", "/service/", "/endpoint/", "/data/", "/query/"]
    if any(p in path_lower for p in api_patterns):
        return "API"
    
    # Admin detection (expanded patterns)
    admin_patterns = ["/admin", "/portal", "/console", "/dashboard", "/manage", "/backend", "/control",
                     "/cms/", "/edit/", "/config", "/settings", "/panel", "/wp-admin", "/phpmyadmin"]
    if any(p in path_lower for p in admin_patterns):
        return "ADMIN"
    
    # Auth detection (expanded patterns)
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
    Returns list of dicts with name, location, datatype_hint, sensitivity, is_critical.
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
    Returns: (behavior_hint, id_based_access)
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
    policy = load_risk_policy()
    weights = policy.get("pre_score_weights", {})
    likelihood_factors = policy.get("likelihood_factors", {})
    impact_factors = policy.get("impact_factors", {})
    formula = policy.get("risk_formula", {})
    
    likelihood = 0
    impact = 0
    
    # Category-based scoring (Boosted for V3.0)
    if category == "ADMIN":
        likelihood += 5  # Admin panels often under-secured - Boosted
        impact += weights.get("category_admin", 10)  # Full value
    elif category == "AUTH":
        likelihood += 4  # Auth endpoints are critical - Boosted
        impact += weights.get("category_auth", 10)  # Full value
    elif category == "API":
        likelihood += 3  # APIs often have vulns - Boosted
        impact += weights.get("category_api", 8)  # Full value
    elif category == "LEGACY":
        likelihood += weights.get("legacy_extension", 4)  # Boosted
        impact += 4  # Legacy often has vulns - Boosted
    
    # Parameter-based scoring (Boosted)
    for p in params:
        if p.get("sensitivity") == "HIGH":
            impact += impact_factors.get("token_param", 4)  # Full value, not halved
        elif p.get("sensitivity") == "MEDIUM":
            impact += impact_factors.get("id_param", 3)  # Full value
        if p.get("is_critical"):
            impact += impact_factors.get("has_critical_param", 3)  # Full value
    
    # Behavior-based scoring (Boosted)
    if behavior_hint == "STATE_CHANGING":
        likelihood += likelihood_factors.get("state_changing_method", 3)  # Boosted
        impact += 3
    elif behavior_hint == "ID_BASED_ACCESS":
        likelihood += 3  # Boosted IDOR potential
    
    # Source-based scoring (Boosted)
    if source == "WAYBACK":
        likelihood += likelihood_factors.get("historical_endpoint", 3)  # Boosted
    
    # Clamp scores
    likelihood = max(0, min(10, likelihood))
    impact = max(0, min(10, impact))
    
    # Calculate risk score - Use MATRIX mode for higher scores
    # Matrix: likelihood * impact = 0-100
    risk = likelihood * impact
    
    risk = max(0, min(100, risk))
    
    return likelihood, impact, risk


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
    Returns dict with all computed fields ready for update_endpoint_metadata.
    """
    # Categorize
    category = categorize_endpoint(path, method, extension)
    
    # Extract params
    params = extract_parameters(url, path)
    
    # Detect behavior
    behavior_hint, id_based_access = detect_behavior(method, params)
    
    # Compute scores
    likelihood, impact, risk = compute_prescores(category, params, behavior_hint, source, method)
    
    # Infer auth_required (heuristic)
    auth_required = _infer_auth_required(path, category, params)
    
    # Infer tech_stack_hint from extension
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


def _infer_auth_required(path: str, category: str, params: List[Dict]) -> str:
    """
    Infer whether authentication is likely required for this endpoint.
    Returns: "true", "false", or "UNKNOWN"
    """
    path_lower = path.lower() if path else ""
    
    # Public patterns - likely no auth
    public_patterns = ["/.well-known/", "/public/", "/static/", "/assets/", "/favicon", "/robots.txt"]
    if any(p in path_lower for p in public_patterns):
        return "false"
    
    # Auth-related endpoints - likely require auth (except login itself)
    if category in ("ADMIN", "AUTH"):
        # Login/signup pages don't require auth to access
        if "/login" in path_lower or "/signin" in path_lower or "/signup" in path_lower or "/register" in path_lower:
            return "false"
        return "true"
    
    # API endpoints with ID-based access - likely require auth
    if category == "API":
        for p in params:
            if p.get("datatype_hint") == "id":
                return "true"
    
    # Has token/auth param - definitely requires auth
    for p in params:
        if p.get("is_critical") or p.get("sensitivity") == "HIGH":
            return "true"
    
    return "UNKNOWN"


def _infer_tech_stack(path: str, extension: str) -> str:
    """
    Infer technology stack from path and extension.
    Returns: tech hint or "Unknown"
    """
    path_lower = path.lower() if path else ""
    ext = extension.lower() if extension else ""
    
    # Extension-based inference
    if ext == ".php":
        return "PHP"
    elif ext in (".asp", ".aspx"):
        return "ASP.NET"
    elif ext == ".jsp":
        return "Java/JSP"
    elif ext in (".cgi", ".pl"):
        return "Perl/CGI"
    elif ext == ".rb":
        return "Ruby"
    elif ext == ".py":
        return "Python"
    
    # Path pattern-based inference
    if "/wp-" in path_lower or "/wordpress" in path_lower:
        return "WordPress/PHP"
    elif "/drupal" in path_lower:
        return "Drupal/PHP"
    elif "/joomla" in path_lower:
        return "Joomla/PHP"
    elif "/rails" in path_lower or "/assets/application" in path_lower:
        return "Ruby on Rails"
    elif "/django" in path_lower or "/admin/django" in path_lower:
        return "Django/Python"
    elif "/node_modules" in path_lower or "/express" in path_lower:
        return "Node.js"
    elif "/graphql" in path_lower:
        return "GraphQL"
    elif "/api/v" in path_lower:
        return "REST API"
    
    return "Unknown"
