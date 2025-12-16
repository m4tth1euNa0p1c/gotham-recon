"""
Planner - Attack path scoring and action suggestions
Full implementation with planner.py logic
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Tuple, Generator
from datetime import datetime
import httpx
import structlog

logger = structlog.get_logger()
app = FastAPI(title="Planner", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Service URLs
GRAPH_SERVICE = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")


class PlanRequest(BaseModel):
    mission_id: str
    top_k: int = 5


class AttackPath(BaseModel):
    target: str
    score: int
    actions: List[str]
    reasons: List[str]
    url: Optional[str] = None


# ============================================
# PLANNER ENGINE
# ============================================

def iter_paths_sub_http_js(graph_data: Dict) -> Generator[Tuple, None, None]:
    """
    Iterate over paths: SUBDOMAIN -> HTTP_SERVICE [-> JS_FILE].
    Also traverses infrastructure and endpoints.
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    node_index = {n["id"]: n for n in nodes}

    sub_to_http = {}
    http_to_js = {}
    sub_to_ip = {}
    ip_to_asn = {}
    sub_to_dns = {}
    http_to_endpoints = {}
    node_to_vulns = {}

    for edge in edges:
        rel = edge.get("type") or edge.get("relation", "")
        src = edge["from"]
        dst = edge["to"]

        if rel == "EXPOSES_HTTP":
            sub_to_http.setdefault(src, []).append(dst)
        elif rel == "LOADS_JS":
            http_to_js.setdefault(src, []).append(dst)
        elif rel == "EXPOSES_ENDPOINT":
            http_to_endpoints.setdefault(src, []).append(dst)
        elif rel == "RESOLVES_TO":
            sub_to_ip.setdefault(src, []).append(dst)
        elif rel == "BELONGS_TO":
            ip_to_asn.setdefault(src, []).append(dst)
        elif rel == "HAS_RECORD":
            sub_to_dns.setdefault(src, []).append(dst)
        elif rel.startswith("AFFECTS"):
            node_to_vulns.setdefault(dst, []).append(src)

    for node in nodes:
        if node["type"] != "SUBDOMAIN":
            continue

        sub_id = node["id"]

        # Resolve Infra (IP + ASN)
        infra_nodes = []
        ip_ids = sub_to_ip.get(sub_id, [])
        for ip_id in ip_ids:
            ip_node = node_index.get(ip_id)
            if ip_node:
                infra_nodes.append(ip_node)
                asn_ids = ip_to_asn.get(ip_id, [])
                for asn_id in asn_ids:
                    asn_node = node_index.get(asn_id)
                    if asn_node:
                        infra_nodes.append(asn_node)

        # Resolve DNS Records
        dns_nodes = []
        dns_ids = sub_to_dns.get(sub_id, [])
        for d_id in dns_ids:
            d_node = node_index.get(d_id)
            if d_node:
                dns_nodes.append(d_node)

        # Resolve HTTP/JS
        http_ids = sub_to_http.get(sub_id, [])

        # Collect vulnerabilities
        vuln_nodes = []

        def collect_vulns(nid):
            v_ids = node_to_vulns.get(nid, [])
            for v_id in v_ids:
                v_node = node_index.get(v_id)
                if v_node:
                    vuln_nodes.append(v_node)

        collect_vulns(sub_id)

        for h_id in http_ids:
            http_node = node_index.get(h_id)
            if not http_node:
                continue

            collect_vulns(h_id)

            js_ids = http_to_js.get(h_id, [])
            for j_id in js_ids:
                collect_vulns(j_id)

            # Resolve Endpoints
            ep_ids = http_to_endpoints.get(h_id, [])
            endpoint_nodes = []
            for ep_id in ep_ids:
                ep_node = node_index.get(ep_id)
                if ep_node:
                    endpoint_nodes.append(ep_node)
                    collect_vulns(ep_id)

            # Deduplicate Vulns
            unique_vulns = {v["id"]: v for v in vuln_nodes}
            vuln_nodes_list = list(unique_vulns.values())

            if js_ids:
                for j_id in js_ids:
                    js_node = node_index.get(j_id)
                    if js_node:
                        yield (node, http_node, js_node, infra_nodes, dns_nodes, endpoint_nodes, vuln_nodes_list)
            else:
                yield (node, http_node, None, infra_nodes, dns_nodes, endpoint_nodes, vuln_nodes_list)

        if not http_ids and (infra_nodes or dns_nodes):
            unique_vulns = {v["id"]: v for v in vuln_nodes}
            vuln_nodes_list = list(unique_vulns.values())
            yield (node, {}, None, infra_nodes, dns_nodes, [], vuln_nodes_list)


def score_path(subnode: Dict, httpnode: Dict, jsnode: Optional[Dict],
               infra_nodes: List[Dict], dns_nodes: List[Dict],
               endpoint_nodes: List[Dict], vuln_nodes: List[Dict] = [],
               memory_boost: int = 0) -> Tuple[int, List[str]]:
    """Score an attack path based on node properties."""
    score = 0
    reasons = []

    # Memory Boost
    if memory_boost > 0:
        score += memory_boost
        reasons.append(f"Memory Boost (+{memory_boost})")

    # Subdomain Analysis
    sub_props = subnode.get("properties", {})
    score += sub_props.get("priority", 0)

    tag = str(sub_props.get("tag", "")).upper()
    sub_name = subnode.get("id", "").lower()

    # Tag Bonuses
    if "AUTH" in tag or "login" in sub_name:
        score += 5
        reasons.append("Auth Portal (+5)")
    elif "BACKUP" in tag or "backup" in sub_name:
        score += 4
        reasons.append("Backup Exposed (+4)")
    elif "ADMIN" in tag or "admin" in sub_name:
        score += 5
        reasons.append("Admin Panel (+5)")
    elif "DEV" in tag or "dev" in sub_name or "staging" in sub_name:
        score += 4
        reasons.append("Dev Environment (+4)")
    elif "MAIL" in tag or "mail" in sub_name:
        score += 4
        reasons.append("Mailing System (+4)")

    category = str(sub_props.get("category", "")).upper()
    if "APP_BACKEND" in category:
        score += 3
        reasons.append("App Backend (+3)")

    # Infra Analysis
    asns = [n for n in infra_nodes if n.get("type") == "ASN"]
    seen_orgs = set()

    for node in asns:
        org = node.get("properties", {}).get("org", "").lower()
        if org in seen_orgs:
            continue
        seen_orgs.add(org)

        if "cloudflare" in org or "akamai" in org or "fastly" in org:
            score -= 1
            reasons.append("CDN Protected (-1)")
        elif "ovh" in org:
            score += 3
            reasons.append("OVH Backend (+3)")
        elif "amazon" in org or "aws" in org:
            score += 1
            reasons.append("AWS Infra (+1)")

    # DNS Analysis
    has_mx = False
    has_spf = False
    has_dmarc = False

    for node in dns_nodes:
        if node.get("type") == "DNS_RECORD":
            rtype = node.get("properties", {}).get("type", "")
            val = node.get("properties", {}).get("value", "")

            if rtype == "MX":
                has_mx = True
            if rtype == "TXT":
                if "v=spf1" in val:
                    has_spf = True
                if "v=DMARC1" in val:
                    has_dmarc = True

    if has_mx and has_spf:
        score += 2
        reasons.append("Structured Emailing (+2)")

    if has_mx and not has_dmarc:
        score += 1
        reasons.append("Missing DMARC (+1)")

    # Technology Bonus
    if httpnode:
        technologies = httpnode.get("properties", {}).get("technologies", [])
        if technologies:
            if any(tech in technologies for tech in ["Express", "Spring", "Django", "Laravel", "Node.js"]):
                score += 3
                reasons.append("Backend Stack (+3)")

    # JS File Analysis
    if jsnode:
        js_url = str(jsnode.get("properties", {}).get("url", "")).lower()
        high_kw = ["auth", "api", "secrets", "config", "key"]

        if any(k in js_url for k in high_kw):
            score += 3
            reasons.append("Sensitive JS Keyword (+3)")

    # Endpoint Analysis
    if endpoint_nodes:
        if len(endpoint_nodes) > 0:
            reasons.append(f"Endpoints Found (+{min(len(endpoint_nodes), 5)})")
            score += min(len(endpoint_nodes), 5)

        admin_bonus = False
        api_bonus = False
        high_risk_bonus = False

        for ep in endpoint_nodes:
            props = ep.get("properties", {})
            path = props.get("path", "").lower()
            source = props.get("source", "")
            method = props.get("method", "")
            category = props.get("category", "").upper()
            risk_score = props.get("risk_score", 0)

            # Category-based scoring
            if category in ("ADMIN", "AUTH") and not admin_bonus:
                score += 4
                reasons.append(f"{category} Endpoint (+4)")
                admin_bonus = True
            elif category == "API" and not api_bonus:
                score += 2
                reasons.append("API Endpoint (+2)")
                api_bonus = True
            elif category == "LEGACY":
                score += 2
                reasons.append("Legacy Endpoint (+2)")

            # Risk score-based boost
            if risk_score >= 70 and not high_risk_bonus:
                bonus = min(5, risk_score // 20)
                score += bonus
                reasons.append(f"High Risk Endpoint ({risk_score}) (+{bonus})")
                high_risk_bonus = True

            # Behavior-based scoring
            behavior = props.get("behavior_hint", "")
            if behavior == "STATE_CHANGING":
                score += 2
                reasons.append("State Changing Behavior (+2)")
            elif behavior == "ID_BASED_ACCESS":
                score += 1
                reasons.append("ID-Based Access (IDOR potential) (+1)")

            # Source-based
            if source == "WAYBACK":
                score += 2
                reasons.append("Historical Endpoint (+2)")
            if source == "ROBOTS":
                score += 2
                reasons.append("Robots Disallow (+2)")

            if method in ("POST", "PUT"):
                score += 1
                reasons.append("State Changing Method (+1)")

    # Vulnerability Analysis
    if vuln_nodes:
        for v in vuln_nodes:
            props = v.get("properties", {})
            severity = props.get("severity", "LOW")
            name = props.get("name", "Unknown")
            confirmed = props.get("confirmed", False)

            val = 1
            if severity == "CRITICAL":
                val = 7
            elif severity == "HIGH":
                val = 5
            elif severity == "MEDIUM":
                val = 3

            if confirmed:
                val += 3
                reasons.append(f"CONFIRMED Vulnerability: {name} (+3)")

            score += val
            reasons.append(f"{severity} Vulnerability: {name} (+{val})")

    return score, list(set(reasons))


def suggest_actions(subnode: Dict, httpnode: Dict, jsnode: Optional[Dict],
                   dns_nodes: List[Dict], endpoint_nodes: List[Dict],
                   vuln_nodes: List[Dict] = []) -> List[str]:
    """Suggest next actions for a path."""
    actions = []

    # Calculate max endpoint risk
    max_endpoint_risk = 0
    has_high_value_category = False

    for ep in endpoint_nodes:
        props = ep.get("properties", {})
        risk = props.get("risk_score", 0)
        category = props.get("category", "").upper()

        if risk > max_endpoint_risk:
            max_endpoint_risk = risk
        if category in ("ADMIN", "AUTH", "API"):
            has_high_value_category = True

    # HTTP Actions
    if httpnode and httpnode.get("id"):
        if max_endpoint_risk >= 30 or has_high_value_category or vuln_nodes:
            actions.append("nuclei_scan")
        if jsnode:
            actions.append("parameter_mining")
    else:
        actions.append("dns_audit")

    # Endpoint-specific actions
    if endpoint_nodes:
        if max_endpoint_risk >= 40 or has_high_value_category:
            actions.append("ffuf_api_fuzz")

        for ep in endpoint_nodes:
            props = ep.get("properties", {})
            path = props.get("path", "")
            category = props.get("category", "").upper()
            risk = props.get("risk_score", 0)

            if (category in ("ADMIN", "AUTH") or "/admin" in path or "/login" in path) and risk >= 30:
                actions.append("nuclei_auth_scan")
            if "/graphql" in path:
                actions.append("graphql_introspection")

    # DNS Specific
    for node in dns_nodes:
        rtype = node.get("properties", {}).get("type", "")
        if rtype == "MX":
            actions.append("smtp_test")
            break

    if not actions:
        actions.append("manual_review")

    if vuln_nodes:
        actions.append("manual_validation")
        has_exploitable = any(
            v.get("properties", {}).get("severity") in ["CRITICAL", "HIGH"] or
            v.get("properties", {}).get("confirmed")
            for v in vuln_nodes
        )
        if has_exploitable:
            actions.append("exploit_lab")

    return list(set(actions))


def find_top_paths(graph_data: Dict, memory_context: Dict = None, k: int = 5) -> List[Dict]:
    """Find top attack paths from graph data."""
    best_paths: Dict[str, Dict] = {}
    memory_context = memory_context or {"keywords": [], "targets": []}
    past_targets = memory_context.get("targets", [])

    for sub, http, js, infra, dns, eps, vulns in iter_paths_sub_http_js(graph_data):
        sub_id = sub.get("id", "")
        mem_boost = 3 if sub_id in past_targets else 0

        current_score, reasons = score_path(sub, http, js, infra, dns, eps, vulns, memory_boost=mem_boost)

        path_info = {
            "score": current_score,
            "subdomain": sub_id,
            "url": http.get("properties", {}).get("url") if http else None,
            "reason": " | ".join(reasons),
            "next_actions": suggest_actions(sub, http, js, dns, eps, vulns)
        }

        if sub_id not in best_paths or current_score > best_paths[sub_id]["score"]:
            best_paths[sub_id] = path_info

    scored_paths = list(best_paths.values())
    scored_paths.sort(key=lambda x: x["score"], reverse=True)
    return scored_paths[:k]


def find_top_offensive_endpoints(graph_data: Dict, limit: int = 10) -> List[Dict]:
    """Find top offensive endpoints for targeted scanning."""
    nodes = graph_data.get("nodes", [])
    endpoint_targets = []

    for node in nodes:
        if node.get("type") != "ENDPOINT":
            continue

        props = node.get("properties", {})
        risk_score = props.get("risk_score", 0)

        target = {
            "endpoint_id": node["id"],
            "url": props.get("origin", ""),
            "path": props.get("path", ""),
            "method": props.get("method", "GET"),
            "category": props.get("category", "UNKNOWN"),
            "risk_score": risk_score,
            "likelihood_score": props.get("likelihood_score", 0),
            "impact_score": props.get("impact_score", 0),
            "behavior_hint": props.get("behavior_hint", "UNKNOWN"),
            "auth_required": props.get("auth_required", False),
            "suggested_tools": [],
        }

        category = target["category"]
        behavior = target["behavior_hint"]

        if category in ("ADMIN", "AUTH"):
            target["suggested_tools"].extend(["nuclei_auth_scan", "ffuf_dir_fuzz"])
        elif category == "API":
            target["suggested_tools"].extend(["nuclei_api_scan", "ffuf_api_fuzz"])
        elif category == "LEGACY":
            target["suggested_tools"].append("nuclei_legacy_scan")

        if behavior == "ID_BASED_ACCESS":
            target["suggested_tools"].append("idor_test")
        if behavior == "STATE_CHANGING":
            target["suggested_tools"].append("csrf_test")

        if not target["suggested_tools"]:
            target["suggested_tools"].append("nuclei_general")

        endpoint_targets.append(target)

    endpoint_targets.sort(key=lambda x: (x["risk_score"], x["likelihood_score"]), reverse=True)
    return endpoint_targets[:limit]


# ============================================
# PLANNER RUNNER
# ============================================
class PlannerRunner:
    """Orchestrates attack planning"""

    def __init__(self, mission_id: str):
        self.mission_id = mission_id

    async def get_graph_data(self) -> Dict:
        """Fetch full graph data from graph-service"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Get nodes
                nodes_response = await client.get(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    params={"mission_id": self.mission_id}
                )
                nodes = nodes_response.json().get("nodes", []) if nodes_response.status_code == 200 else []

                # Get edges
                edges_response = await client.get(
                    f"{GRAPH_SERVICE}/api/v1/edges",
                    params={"mission_id": self.mission_id}
                )
                edges = edges_response.json().get("edges", []) if edges_response.status_code == 200 else []

                return {"nodes": nodes, "edges": edges}

            except Exception as e:
                logger.error("get_graph_data_failed", error=str(e))
                return {"nodes": [], "edges": []}

    async def publish_attack_path(self, path: Dict) -> bool:
        """Publish attack path node to graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                path_id = f"attack_path:{path['subdomain']}"
                response = await client.post(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    json={
                        "id": path_id,
                        "type": "ATTACK_PATH",
                        "mission_id": self.mission_id,
                        "properties": {
                            "target": path["subdomain"],
                            "score": path["score"],
                            "url": path.get("url"),
                            "reason": path["reason"],
                            "next_actions": path["next_actions"],
                            "computed_at": datetime.utcnow().isoformat()
                        }
                    }
                )
                return response.status_code in [200, 201]
            except Exception as e:
                logger.error("publish_attack_path_failed", error=str(e))
                return False

    async def run(self, top_k: int = 5) -> Dict:
        """Execute attack planning"""
        start_time = datetime.utcnow()

        # Get graph data
        graph_data = await self.get_graph_data()
        node_count = len(graph_data.get("nodes", []))
        edge_count = len(graph_data.get("edges", []))

        logger.info("planner_started",
                   mission_id=self.mission_id,
                   nodes=node_count,
                   edges=edge_count)

        if node_count == 0:
            return {
                "mission_id": self.mission_id,
                "paths": [],
                "top_endpoints": [],
                "computed_at": datetime.utcnow().isoformat(),
                "duration": (datetime.utcnow() - start_time).total_seconds()
            }

        # Find top attack paths
        top_paths = find_top_paths(graph_data, k=top_k)

        # Publish attack paths
        for path in top_paths:
            await self.publish_attack_path(path)

        # Find top offensive endpoints
        top_endpoints = find_top_offensive_endpoints(graph_data, limit=10)

        duration = (datetime.utcnow() - start_time).total_seconds()

        logger.info("planner_completed",
                   mission_id=self.mission_id,
                   paths=len(top_paths),
                   endpoints=len(top_endpoints),
                   duration=duration)

        return {
            "mission_id": self.mission_id,
            "paths": top_paths,
            "top_endpoints": top_endpoints,
            "computed_at": datetime.utcnow().isoformat(),
            "duration": duration
        }


# ============================================
# API ENDPOINTS
# ============================================
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "planner", "version": "2.0.0"}


@app.get("/status")
async def status():
    return {
        "service": "planner",
        "graph_service": GRAPH_SERVICE
    }


@app.post("/api/v1/plan")
async def generate_plan(request: PlanRequest):
    """Generate attack plan from graph analysis"""
    logger.info("planning_requested",
                mission_id=request.mission_id,
                top_k=request.top_k)

    runner = PlannerRunner(mission_id=request.mission_id)
    result = await runner.run(top_k=request.top_k)

    return result


@app.get("/api/v1/plan/{mission_id}")
async def get_plan(mission_id: str, top_k: int = 5):
    """Get attack plan for a mission"""
    runner = PlannerRunner(mission_id=mission_id)
    return await runner.run(top_k=top_k)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
