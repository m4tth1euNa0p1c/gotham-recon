"""
GraphUpdater Tool for Deep Verification
Updates vulnerability status and evidence in the graph-service
"""
import json
import httpx
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import Field


class GraphUpdaterTool(BaseTool):
    """
    Tool for updating vulnerability status and evidence in the knowledge graph.
    Used by Deep Verification agents to store verification results.
    """
    name: str = "graph_updater"
    description: str = """Update vulnerability status and evidence in the knowledge graph.

    Usage:
    - action: 'update_vuln_status' | 'add_evidence' | 'link_tool_call' | 'create_vuln'
    - mission_id: The mission ID
    - vuln_id: Vulnerability node ID (for update/link actions)
    - Additional params based on action

    Returns update result."""

    graph_service_url: str = Field(default="http://graph-service:8001")
    timeout: float = Field(default=30.0)

    def _run(
        self,
        action: str = "update_vuln_status",
        mission_id: str = "",
        vuln_id: str = "",
        target_id: str = "",
        status: str = "",
        evidence: str = "[]",
        tool_call_id: str = "",
        attack_type: str = "",
        title: str = "",
        risk_score: int = 0,
    ) -> str:
        """
        Execute a graph update action.

        Args:
            action: The update action to perform
            mission_id: Mission ID
            vuln_id: Vulnerability node ID
            target_id: Target node ID (for create_vuln)
            status: New status (CONFIRMED, LIKELY, FALSE_POSITIVE, MITIGATED)
            evidence: JSON array of evidence objects
            tool_call_id: Tool call ID for linking
            attack_type: Attack type for create_vuln
            title: Title for create_vuln
            risk_score: Risk score for create_vuln
        """
        if not mission_id:
            return json.dumps({"error": "mission_id is required"})

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if action == "update_vuln_status":
                    return self._update_vuln_status(client, mission_id, vuln_id, status, evidence, tool_call_id)
                elif action == "add_evidence":
                    return self._add_evidence(client, mission_id, vuln_id, evidence)
                elif action == "link_tool_call":
                    return self._link_tool_call(client, mission_id, vuln_id, tool_call_id)
                elif action == "create_vuln":
                    return self._create_vuln(client, mission_id, target_id, attack_type, title, status, risk_score, evidence, tool_call_id)
                else:
                    return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as e:
            return json.dumps({"error": str(e), "action": action})

    def _update_vuln_status(
        self,
        client: httpx.Client,
        mission_id: str,
        vuln_id: str,
        status: str,
        evidence: str,
        tool_call_id: str
    ) -> str:
        """Update vulnerability status with evidence."""
        if not vuln_id:
            return json.dumps({"error": "vuln_id is required for update_vuln_status"})
        if not status:
            return json.dumps({"error": "status is required for update_vuln_status"})

        # Validate status
        valid_statuses = ["THEORETICAL", "LIKELY", "CONFIRMED", "FALSE_POSITIVE", "MITIGATED"]
        if status.upper() not in valid_statuses:
            return json.dumps({"error": f"Invalid status: {status}. Must be one of {valid_statuses}"})

        try:
            evidence_list = json.loads(evidence) if isinstance(evidence, str) else evidence
        except json.JSONDecodeError:
            evidence_list = []

        # Build update payload
        update_data = {
            "properties": {
                "status": status.upper(),
                "verified": status.upper() in ["CONFIRMED", "FALSE_POSITIVE", "MITIGATED"],
            }
        }

        if tool_call_id:
            update_data["properties"]["tool_call_id"] = tool_call_id

        if evidence_list:
            update_data["properties"]["evidence"] = evidence_list

        # Update the node
        response = client.patch(
            f"{self.graph_service_url}/api/v1/nodes/{vuln_id}",
            json=update_data
        )

        if response.status_code not in [200, 204]:
            return json.dumps({
                "error": f"Update failed: {response.status_code}",
                "detail": response.text[:500] if response.text else None
            })

        return json.dumps({
            "success": True,
            "vuln_id": vuln_id,
            "new_status": status.upper(),
            "evidence_count": len(evidence_list),
            "tool_call_id": tool_call_id
        }, indent=2)

    def _add_evidence(
        self,
        client: httpx.Client,
        mission_id: str,
        vuln_id: str,
        evidence: str
    ) -> str:
        """Add evidence to an existing vulnerability."""
        if not vuln_id:
            return json.dumps({"error": "vuln_id is required for add_evidence"})

        try:
            evidence_list = json.loads(evidence) if isinstance(evidence, str) else evidence
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid evidence JSON"})

        if not evidence_list:
            return json.dumps({"error": "No evidence provided"})

        # First get existing evidence
        get_response = client.get(f"{self.graph_service_url}/api/v1/nodes/{vuln_id}")

        if get_response.status_code != 200:
            return json.dumps({"error": f"Failed to get vuln node: {get_response.status_code}"})

        node = get_response.json()
        existing_evidence = node.get("properties", {}).get("evidence", [])

        # Deduplicate by hash
        existing_hashes = {e.get("hash") for e in existing_evidence if e.get("hash")}
        new_evidence = [e for e in evidence_list if e.get("hash") not in existing_hashes]

        if not new_evidence:
            return json.dumps({
                "success": True,
                "vuln_id": vuln_id,
                "evidence_added": 0,
                "message": "All evidence already exists (deduplicated by hash)"
            })

        # Merge and update
        merged_evidence = existing_evidence + new_evidence

        response = client.patch(
            f"{self.graph_service_url}/api/v1/nodes/{vuln_id}",
            json={"properties": {"evidence": merged_evidence}}
        )

        if response.status_code not in [200, 204]:
            return json.dumps({"error": f"Add evidence failed: {response.status_code}"})

        return json.dumps({
            "success": True,
            "vuln_id": vuln_id,
            "evidence_added": len(new_evidence),
            "total_evidence": len(merged_evidence)
        }, indent=2)

    def _link_tool_call(
        self,
        client: httpx.Client,
        mission_id: str,
        vuln_id: str,
        tool_call_id: str
    ) -> str:
        """Link a tool call ID to a vulnerability for idempotency tracking."""
        if not vuln_id:
            return json.dumps({"error": "vuln_id is required for link_tool_call"})
        if not tool_call_id:
            return json.dumps({"error": "tool_call_id is required for link_tool_call"})

        response = client.patch(
            f"{self.graph_service_url}/api/v1/nodes/{vuln_id}",
            json={"properties": {"tool_call_id": tool_call_id}}
        )

        if response.status_code not in [200, 204]:
            return json.dumps({"error": f"Link failed: {response.status_code}"})

        return json.dumps({
            "success": True,
            "vuln_id": vuln_id,
            "tool_call_id": tool_call_id
        }, indent=2)

    def _create_vuln(
        self,
        client: httpx.Client,
        mission_id: str,
        target_id: str,
        attack_type: str,
        title: str,
        status: str,
        risk_score: int,
        evidence: str,
        tool_call_id: str
    ) -> str:
        """Create a new vulnerability node from verification results."""
        if not target_id:
            return json.dumps({"error": "target_id is required for create_vuln"})
        if not attack_type:
            return json.dumps({"error": "attack_type is required for create_vuln"})

        try:
            evidence_list = json.loads(evidence) if isinstance(evidence, str) else evidence
        except json.JSONDecodeError:
            evidence_list = []

        # Build node properties
        properties = {
            "attack_type": attack_type.upper(),
            "title": title or f"{attack_type} vulnerability",
            "status": (status or "CONFIRMED").upper(),
            "risk_score": risk_score or 50,
            "target_id": target_id,
            "verified": True,
            "source": "deep_verification",
        }

        if tool_call_id:
            properties["tool_call_id"] = tool_call_id

        if evidence_list:
            properties["evidence"] = evidence_list

        # Create vulnerability node
        node_data = {
            "mission_id": mission_id,
            "type": "VULNERABILITY",
            "label": title or f"VULN:{attack_type}",
            "properties": properties
        }

        response = client.post(
            f"{self.graph_service_url}/api/v1/nodes",
            json=node_data
        )

        if response.status_code not in [200, 201]:
            return json.dumps({
                "error": f"Create vuln failed: {response.status_code}",
                "detail": response.text[:500] if response.text else None
            })

        result = response.json()
        vuln_id = result.get("id")

        # Create edge to target if we have IDs
        if vuln_id and target_id:
            edge_data = {
                "mission_id": mission_id,
                "from_node": target_id,
                "to_node": vuln_id,
                "relation": "HAS_VULNERABILITY"
            }

            edge_response = client.post(
                f"{self.graph_service_url}/api/v1/edges",
                json=edge_data
            )

            if edge_response.status_code not in [200, 201]:
                # Log but don't fail
                pass

        return json.dumps({
            "success": True,
            "vuln_id": vuln_id,
            "attack_type": attack_type,
            "status": properties["status"],
            "target_id": target_id,
            "evidence_count": len(evidence_list)
        }, indent=2)


class BulkGraphUpdaterTool(BaseTool):
    """
    Tool for bulk updating vulnerability statuses from verification results.
    More efficient for processing a full verification plan's results.
    """
    name: str = "bulk_graph_updater"
    description: str = """Bulk update vulnerability statuses from verification results.

    Usage:
    - updates: JSON array of update objects
    - mission_id: The mission ID

    Each update should have: vuln_id, status, evidence, tool_call_id (optional)

    Returns summary of updates."""

    graph_service_url: str = Field(default="http://graph-service:8001")
    timeout: float = Field(default=60.0)

    def _run(
        self,
        updates: str = "[]",
        mission_id: str = ""
    ) -> str:
        """
        Execute bulk updates.

        Args:
            updates: JSON array of update configs [{vuln_id, status, evidence, tool_call_id}, ...]
            mission_id: Mission ID
        """
        if not mission_id:
            return json.dumps({"error": "mission_id is required"})

        try:
            update_list = json.loads(updates) if isinstance(updates, str) else updates
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid updates JSON"})

        if not update_list:
            return json.dumps({"error": "No updates provided", "results": []})

        results = []
        errors = []

        with httpx.Client(timeout=self.timeout) as client:
            for i, update in enumerate(update_list):
                vuln_id = update.get("vuln_id")
                status = update.get("status")
                evidence = update.get("evidence", [])
                tool_call_id = update.get("tool_call_id")

                if not vuln_id or not status:
                    errors.append({
                        "index": i,
                        "error": "Missing vuln_id or status"
                    })
                    continue

                try:
                    update_data = {
                        "properties": {
                            "status": status.upper(),
                            "verified": status.upper() in ["CONFIRMED", "FALSE_POSITIVE", "MITIGATED"],
                        }
                    }

                    if tool_call_id:
                        update_data["properties"]["tool_call_id"] = tool_call_id

                    if evidence:
                        update_data["properties"]["evidence"] = evidence

                    response = client.patch(
                        f"{self.graph_service_url}/api/v1/nodes/{vuln_id}",
                        json=update_data
                    )

                    if response.status_code in [200, 204]:
                        results.append({
                            "index": i,
                            "vuln_id": vuln_id,
                            "new_status": status.upper(),
                            "success": True
                        })
                    else:
                        errors.append({
                            "index": i,
                            "vuln_id": vuln_id,
                            "error": f"HTTP {response.status_code}"
                        })

                except Exception as e:
                    errors.append({
                        "index": i,
                        "vuln_id": vuln_id,
                        "error": str(e)
                    })

        # Count status changes
        status_counts = {}
        for r in results:
            s = r.get("new_status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1

        return json.dumps({
            "results": results,
            "errors": errors,
            "total_updates": len(update_list),
            "successful": len(results),
            "failed": len(errors),
            "status_counts": status_counts
        }, indent=2)
