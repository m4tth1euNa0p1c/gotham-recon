"""
Graph Service Client
Sends discovered nodes to the graph-service via HTTP API
"""
import os
import json
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from .events import emit_node_added, emit_nodes_batch, emit_edge_added, emit_log

GRAPH_SERVICE_URL = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")


class GraphClient:
    """Client for graph-service HTTP API"""

    def __init__(self, mission_id: str, target_domain: str):
        self.mission_id = mission_id
        self.target_domain = target_domain
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def create_node(self, node_type: str, node_id: str, properties: Dict[str, Any]) -> bool:
        """Create a single node in graph-service"""
        try:
            response = await self.client.post(
                f"{GRAPH_SERVICE_URL}/api/v1/nodes",
                json={
                    "id": node_id,
                    "type": node_type,
                    "mission_id": self.mission_id,
                    "properties": properties
                }
            )
            if response.status_code in (200, 201):
                # Also emit to Kafka for SSE clients
                emit_node_added(self.mission_id, node_type, node_id, properties)
                return True
            else:
                emit_log(self.mission_id, "WARNING", f"Failed to create node {node_id}: {response.status_code}", "graph")
                return False
        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Graph API error creating node: {e}", "graph")
            return False

    async def create_nodes_batch(self, nodes: List[Dict[str, Any]]) -> int:
        """Create multiple nodes in batch"""
        if not nodes:
            return 0

        try:
            # Format for batch endpoint
            batch_nodes = [
                {
                    "id": n["id"],
                    "type": n["type"],
                    "mission_id": self.mission_id,
                    "properties": n.get("properties", {})
                }
                for n in nodes
            ]

            response = await self.client.post(
                f"{GRAPH_SERVICE_URL}/api/v1/nodes/batch",
                json=batch_nodes
            )

            if response.status_code in (200, 201):
                result = response.json()
                created_count = result.get("created", 0)
                emit_log(self.mission_id, "INFO", f"Created {created_count} nodes in graph", "graph")

                # Also emit to Kafka for SSE clients
                emit_nodes_batch(self.mission_id, batch_nodes)
                return created_count
            else:
                emit_log(self.mission_id, "WARNING", f"Batch create failed: {response.status_code}", "graph")
                return 0
        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Graph API batch error: {e}", "graph")
            return 0

    async def create_edge(self, from_node: str, to_node: str, relation: str) -> bool:
        """Create an edge between nodes"""
        try:
            response = await self.client.post(
                f"{GRAPH_SERVICE_URL}/api/v1/edges",
                json={
                    "from_node": from_node,
                    "to_node": to_node,
                    "relation": relation,
                    "mission_id": self.mission_id,
                    "properties": {}
                }
            )
            if response.status_code in (200, 201):
                emit_edge_added(self.mission_id, from_node, to_node, relation)
                return True
            return False
        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Graph API edge error: {e}", "graph")
            return False

    # Helper methods to create specific node types

    async def add_subdomain(self, subdomain: str, source: str = "crewai") -> bool:
        """Add a subdomain node"""
        node_id = f"subdomain:{subdomain}"
        return await self.create_node(
            "SUBDOMAIN",
            node_id,
            {
                "name": subdomain,
                "subdomain": subdomain,
                "source": source,
                "mission_id": self.mission_id
            }
        )

    async def add_http_service(self, url: str, status_code: int = None, tech: str = None) -> bool:
        """Add an HTTP service node"""
        node_id = f"http_service:{url}"
        props = {
            "url": url,
            "mission_id": self.mission_id
        }
        if status_code:
            props["status_code"] = status_code
        if tech:
            props["technology"] = tech
        return await self.create_node("HTTP_SERVICE", node_id, props)

    async def add_endpoint(self, path: str, method: str = "GET", category: str = None, risk_score: int = None) -> bool:
        """Add an endpoint node"""
        # Filter out external URLs (CDNs, third-party services)
        if path.startswith("http"):
            from urllib.parse import urlparse
            parsed = urlparse(path)
            # Only accept endpoints from target domain
            if not parsed.netloc.endswith(self.target_domain):
                return False  # Skip external URLs
            path = parsed.path or "/"

        # Skip empty or root-only paths if not meaningful
        if not path or path == "/":
            return False

        node_id = f"endpoint:{self.target_domain}{path}"
        props = {
            "path": path,
            "method": method,
            "name": path,
            "mission_id": self.mission_id
        }
        if category:
            props["category"] = category
        if risk_score is not None:
            props["risk_score"] = risk_score
        return await self.create_node("ENDPOINT", node_id, props)

    async def add_hypothesis(self, title: str, attack_type: str, target_id: str, confidence: float = 0.5) -> bool:
        """Add a hypothesis node"""
        node_id = f"hypothesis:{attack_type}:{target_id}"
        return await self.create_node(
            "HYPOTHESIS",
            node_id,
            {
                "title": title,
                "attack_type": attack_type,
                "target_id": target_id,
                "confidence": confidence,
                "mission_id": self.mission_id
            }
        )

    async def add_vulnerability(self, vuln_type: str, target_id: str, title: str,
                                risk_score: int = 50, status: str = "THEORETICAL") -> bool:
        """Add a vulnerability node"""
        import hashlib
        vuln_hash = hashlib.md5(f"{vuln_type}:{target_id}".encode()).hexdigest()[:8]
        node_id = f"vuln:{vuln_type.lower()}:{vuln_hash}"
        return await self.create_node(
            "VULNERABILITY",
            node_id,
            {
                "attack_type": vuln_type.upper(),
                "title": title,
                "target_id": target_id,
                "risk_score": risk_score,
                "status": status,
                "verified": False,
                "mission_id": self.mission_id
            }
        )

    async def generate_hypotheses_from_path(self, path: str) -> int:
        """
        Automatically generate hypotheses based on endpoint path patterns.
        Returns count of hypotheses created.
        """
        created = 0
        path_lower = path.lower()
        target_id = f"endpoint:{self.target_domain}{path}"

        # Pattern -> (attack_type, title, confidence, risk_score)
        PATTERNS = [
            # Admin/Auth patterns
            (r'admin|dashboard|panel|manage', 'AUTH_BYPASS', 'Admin interface authentication bypass', 0.7, 75),
            (r'login|signin|auth|session', 'AUTH_BYPASS', 'Authentication mechanism bypass', 0.6, 70),
            (r'password|reset|forgot', 'AUTH_BYPASS', 'Password reset flow vulnerability', 0.5, 65),

            # API patterns
            (r'/api/', 'BOLA', 'Broken Object Level Authorization on API', 0.6, 70),
            (r'/api/v[0-9]', 'INFO_DISCLOSURE', 'API version exposure and enumeration', 0.5, 50),
            (r'graphql', 'INFO_DISCLOSURE', 'GraphQL introspection enabled', 0.7, 60),

            # File patterns
            (r'upload|file|document|attachment', 'RCE', 'Unrestricted file upload vulnerability', 0.5, 85),
            (r'download|export|backup', 'LFI', 'Path traversal in file download', 0.6, 75),
            (r'\.php\?', 'LFI', 'PHP parameter injection vulnerability', 0.5, 70),

            # User patterns
            (r'user|profile|account|member', 'IDOR', 'Insecure direct object reference on user data', 0.6, 70),
            (r'edit|update|modify|delete', 'CSRF', 'Cross-site request forgery on state-changing action', 0.5, 60),

            # Data patterns
            (r'search|query|filter', 'SQLI', 'SQL injection in search/filter functionality', 0.5, 80),
            (r'id=|user_id=|item=', 'SQLI', 'SQL injection via parameter manipulation', 0.6, 80),
            (r'callback|redirect|return|next|url=', 'OPEN_REDIRECT', 'Open redirect vulnerability', 0.7, 55),

            # Config/Debug patterns
            (r'config|settings|\.env|debug', 'INFO_DISCLOSURE', 'Configuration file exposure', 0.7, 70),
            (r'phpinfo|server-status|health', 'INFO_DISCLOSURE', 'Server information disclosure', 0.8, 50),
            (r'\.git|\.svn|\.hg', 'INFO_DISCLOSURE', 'Version control exposure', 0.9, 75),
            (r'backup|\.bak|\.old|\.orig', 'INFO_DISCLOSURE', 'Backup file exposure', 0.8, 65),

            # Internal patterns
            (r'internal|private|dev|test|staging', 'INFO_DISCLOSURE', 'Internal/development endpoint exposure', 0.7, 60),
            (r'proxy|forward|fetch|curl', 'SSRF', 'Server-side request forgery vulnerability', 0.5, 80),
        ]

        import re
        for pattern, attack_type, title, confidence, risk_score in PATTERNS:
            if re.search(pattern, path_lower):
                # Create hypothesis
                if await self.add_hypothesis(title, attack_type, target_id, confidence):
                    created += 1
                # Create theoretical vulnerability
                if await self.add_vulnerability(attack_type, target_id, title, risk_score, "THEORETICAL"):
                    created += 1
                # Only create one hypothesis per endpoint to avoid spam
                break

        return created


def parse_crew_result(result: Any) -> List[str]:
    """
    Parse CrewAI result to extract discovered items
    Returns list of strings (subdomains, endpoints, etc.)
    """
    if result is None:
        return []

    result_str = str(result)
    items = []

    # Try to parse as JSON first
    try:
        # Look for JSON array in result
        import re
        json_match = re.search(r'\[[\s\S]*?\]', result_str)
        if json_match:
            data = json.loads(json_match.group())
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # Extract various fields
                        for key in ['subdomain', 'domain', 'url', 'path', 'endpoint']:
                            if key in item:
                                items.append(str(item[key]))
                    elif isinstance(item, str):
                        items.append(item)
    except (json.JSONDecodeError, TypeError):
        pass

    # Also look for domain-like patterns
    import re
    domain_pattern = r'[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z0-9][-a-zA-Z0-9.]*'
    domains = re.findall(domain_pattern, result_str)
    items.extend(domains)

    # Look for paths
    path_pattern = r'/[a-zA-Z0-9_/-]+'
    paths = re.findall(path_pattern, result_str)
    items.extend(paths)

    # Deduplicate
    return list(set(items))


async def publish_discovered_assets(
    graph_client: GraphClient,
    phase: str,
    result: Any,
    target_domain: str
) -> Dict[str, int]:
    """
    Parse phase results and publish discovered assets to graph-service

    Returns dict with counts of created nodes by type
    """
    counts = {"subdomains": 0, "endpoints": 0, "services": 0, "hypotheses": 0}

    if result is None:
        return counts

    result_str = str(result)
    emit_log(graph_client.mission_id, "DEBUG", f"Parsing {phase} result ({len(result_str)} chars)", "graph")

    # Parse items from result
    items = parse_crew_result(result)
    emit_log(graph_client.mission_id, "INFO", f"Found {len(items)} potential items in {phase} result", "graph")

    # Categorize and create nodes
    for item in items:
        item_lower = item.lower()

        # Check if it's a subdomain (contains target domain)
        if target_domain in item_lower and '/' not in item:
            if await graph_client.add_subdomain(item, source=phase):
                counts["subdomains"] += 1

        # Check if it's a URL/endpoint
        elif item.startswith('/') or item.startswith('http'):
            path = item
            if item.startswith('http'):
                # Extract path from URL
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(item)
                    path = parsed.path or '/'
                    # Also add HTTP service
                    if await graph_client.add_http_service(item):
                        counts["services"] += 1
                except:
                    pass

            if path and path != '/':
                if await graph_client.add_endpoint(path):
                    counts["endpoints"] += 1

    # Also try to parse structured JSON for hypotheses
    try:
        import re
        # Look for endpoint analysis results
        json_match = re.search(r'\{[\s\S]*"endpoint_id"[\s\S]*\}', result_str)
        if json_match:
            # Try parsing multiple objects
            for match in re.finditer(r'\{[^{}]*"endpoint_id"[^{}]*"hypotheses"[^{}]*\[[^\]]*\][^{}]*\}', result_str, re.DOTALL):
                try:
                    obj = json.loads(match.group())
                    if "hypotheses" in obj:
                        for hyp in obj["hypotheses"]:
                            if await graph_client.add_hypothesis(
                                hyp.get("title", "Unknown"),
                                hyp.get("attack_type", "UNKNOWN"),
                                obj.get("endpoint_id", "unknown"),
                                hyp.get("confidence", 0.5)
                            ):
                                counts["hypotheses"] += 1
                except:
                    pass
    except Exception as e:
        emit_log(graph_client.mission_id, "DEBUG", f"Hypothesis parsing error: {e}", "graph")

    emit_log(
        graph_client.mission_id,
        "INFO",
        f"Published to graph: {counts['subdomains']} subdomains, {counts['endpoints']} endpoints, {counts['services']} services, {counts['hypotheses']} hypotheses",
        phase
    )

    return counts
