"""
GraphQuery Tool for Deep Verification
Queries the graph-service for vulnerabilities and targets
"""
import json
import httpx
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import Field


class GraphQueryTool(BaseTool):
    """
    Tool for querying the knowledge graph for vulnerabilities and targets.
    Used by Deep Verification agents to get data for triage and validation.
    """
    name: str = "graph_query"
    description: str = """Query the knowledge graph for vulnerabilities and targets.

    Usage:
    - query_type: 'vulnerabilities' | 'targets' | 'http_services' | 'endpoints' | 'stats'
    - mission_id: The mission ID to query
    - filters: Optional JSON filters like {"status": "THEORETICAL", "min_risk": 50}

    Returns JSON data from the graph."""

    graph_service_url: str = Field(default="http://graph-service:8001")
    timeout: float = Field(default=30.0)

    def _run(
        self,
        query_type: str = "vulnerabilities",
        mission_id: str = "",
        filters: str = "{}"
    ) -> str:
        """
        Execute a graph query.

        Args:
            query_type: Type of query (vulnerabilities, targets, http_services, endpoints, stats)
            mission_id: Mission ID to query
            filters: JSON string of filters
        """
        if not mission_id:
            return json.dumps({"error": "mission_id is required"})

        try:
            filter_dict = json.loads(filters) if isinstance(filters, str) else filters
        except json.JSONDecodeError:
            filter_dict = {}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if query_type == "vulnerabilities":
                    return self._query_vulnerabilities(client, mission_id, filter_dict)
                elif query_type == "targets":
                    return self._query_targets(client, mission_id, filter_dict)
                elif query_type == "http_services":
                    return self._query_http_services(client, mission_id, filter_dict)
                elif query_type == "endpoints":
                    return self._query_endpoints(client, mission_id, filter_dict)
                elif query_type == "stats":
                    return self._query_stats(client, mission_id)
                else:
                    return json.dumps({"error": f"Unknown query_type: {query_type}"})
        except Exception as e:
            return json.dumps({"error": str(e), "query_type": query_type})

    def _query_vulnerabilities(
        self,
        client: httpx.Client,
        mission_id: str,
        filters: Dict[str, Any]
    ) -> str:
        """Query vulnerabilities from the graph."""
        # Build filter params
        params = {"mission_id": mission_id}
        if filters.get("status"):
            params["status"] = filters["status"]
        if filters.get("min_risk"):
            params["min_risk"] = filters["min_risk"]

        # Query nodes of type VULNERABILITY
        response = client.get(
            f"{self.graph_service_url}/api/v1/nodes",
            params={"mission_id": mission_id, "type": "VULNERABILITY", "limit": 100}
        )

        if response.status_code != 200:
            return json.dumps({"error": f"Graph query failed: {response.status_code}"})

        response_data = response.json()
        # Handle both {"nodes": [...]} and direct list formats
        if isinstance(response_data, dict):
            nodes = response_data.get("nodes", [])
        elif isinstance(response_data, list):
            nodes = response_data
        else:
            nodes = []

        # Apply filters
        vulnerabilities = []
        for node in nodes:
            props = node.get("properties", {})

            # Filter by status
            if filters.get("status"):
                if props.get("status") != filters["status"]:
                    continue

            # Filter by min_risk
            if filters.get("min_risk"):
                risk = props.get("risk_score", 0)
                if risk < filters["min_risk"]:
                    continue

            vulnerabilities.append({
                "id": node.get("id"),
                "type": node.get("type"),
                "label": node.get("label"),
                "attack_type": props.get("attack_type"),
                "status": props.get("status", "THEORETICAL"),
                "risk_score": props.get("risk_score", 0),
                "target_id": props.get("target_id"),
                "evidence_count": len(props.get("evidence", [])),
                "tool_call_id": props.get("tool_call_id"),
            })

        return json.dumps({
            "vulnerabilities": vulnerabilities,
            "count": len(vulnerabilities),
            "filters_applied": filters
        }, indent=2)

    def _query_targets(
        self,
        client: httpx.Client,
        mission_id: str,
        filters: Dict[str, Any]
    ) -> str:
        """Query verification targets (HTTP services with vulns)."""
        # Get HTTP services
        http_response = client.get(
            f"{self.graph_service_url}/api/v1/nodes",
            params={"mission_id": mission_id, "type": "HTTP_SERVICE", "limit": 100}
        )

        if http_response.status_code != 200:
            return json.dumps({"error": f"Graph query failed: {http_response.status_code}"})

        services_data = http_response.json()
        # Handle both {"nodes": [...]} and direct list formats
        if isinstance(services_data, dict):
            services = services_data.get("nodes", [])
        elif isinstance(services_data, list):
            services = services_data
        else:
            services = []

        # Get vulnerabilities
        vuln_response = client.get(
            f"{self.graph_service_url}/api/v1/nodes",
            params={"mission_id": mission_id, "type": "VULNERABILITY", "limit": 100}
        )

        vulns_data = vuln_response.json() if vuln_response.status_code == 200 else {}
        # Handle both {"nodes": [...]} and direct list formats
        if isinstance(vulns_data, dict):
            vulns = vulns_data.get("nodes", [])
        elif isinstance(vulns_data, list):
            vulns = vulns_data
        else:
            vulns = []

        # Build targets with their vulns
        targets = []
        for svc in services:
            props = svc.get("properties", {})
            svc_id = svc.get("id")

            # Find vulns targeting this service
            svc_vulns = [
                v for v in vulns
                if v.get("properties", {}).get("target_id") == svc_id
            ]

            # Calculate aggregate risk
            max_risk = max([v.get("properties", {}).get("risk_score", 0) for v in svc_vulns], default=0)

            targets.append({
                "target_id": svc_id,
                "target_url": props.get("url"),
                "target_type": "HTTP_SERVICE",
                "tech_stack": props.get("tech", "unknown"),
                "status_code": props.get("status_code"),
                "risk_score": max_risk,
                "vuln_count": len(svc_vulns),
                "vulns": [
                    {
                        "id": v.get("id"),
                        "attack_type": v.get("properties", {}).get("attack_type"),
                        "status": v.get("properties", {}).get("status", "THEORETICAL"),
                    }
                    for v in svc_vulns
                ]
            })

        # Sort by risk score
        targets.sort(key=lambda t: t["risk_score"], reverse=True)

        return json.dumps({
            "targets": targets[:20],  # Limit to top 20
            "count": len(targets),
        }, indent=2)

    def _query_http_services(
        self,
        client: httpx.Client,
        mission_id: str,
        filters: Dict[str, Any]
    ) -> str:
        """Query HTTP services."""
        response = client.get(
            f"{self.graph_service_url}/api/v1/nodes",
            params={"mission_id": mission_id, "type": "HTTP_SERVICE", "limit": 100}
        )

        if response.status_code != 200:
            return json.dumps({"error": f"Graph query failed: {response.status_code}"})

        response_data = response.json()
        # Handle both {"nodes": [...]} and direct list formats
        if isinstance(response_data, dict):
            services = response_data.get("nodes", [])
        elif isinstance(response_data, list):
            services = response_data
        else:
            services = []

        result = []
        for svc in services:
            props = svc.get("properties", {})
            result.append({
                "id": svc.get("id"),
                "url": props.get("url"),
                "status_code": props.get("status_code"),
                "tech": props.get("tech"),
                "server": props.get("server"),
            })

        return json.dumps({"http_services": result, "count": len(result)}, indent=2)

    def _query_endpoints(
        self,
        client: httpx.Client,
        mission_id: str,
        filters: Dict[str, Any]
    ) -> str:
        """Query endpoints."""
        response = client.get(
            f"{self.graph_service_url}/api/v1/nodes",
            params={"mission_id": mission_id, "type": "ENDPOINT", "limit": 200}
        )

        if response.status_code != 200:
            return json.dumps({"error": f"Graph query failed: {response.status_code}"})

        response_data = response.json()
        # Handle both {"nodes": [...]} and direct list formats
        if isinstance(response_data, dict):
            endpoints = response_data.get("nodes", [])
        elif isinstance(response_data, list):
            endpoints = response_data
        else:
            endpoints = []

        result = []
        for ep in endpoints:
            props = ep.get("properties", {})
            result.append({
                "id": ep.get("id"),
                "path": props.get("path"),
                "method": props.get("method", "GET"),
                "category": props.get("category"),
                "risk_score": props.get("risk_score", 0),
            })

        # Sort by risk
        result.sort(key=lambda e: e["risk_score"], reverse=True)

        return json.dumps({"endpoints": result[:50], "count": len(result)}, indent=2)

    def _query_stats(
        self,
        client: httpx.Client,
        mission_id: str
    ) -> str:
        """Query graph statistics."""
        response = client.get(
            f"{self.graph_service_url}/api/v1/missions/{mission_id}/stats"
        )

        if response.status_code != 200:
            return json.dumps({"error": f"Stats query failed: {response.status_code}"})

        return json.dumps(response.json(), indent=2)
