"""
CheckRunner Tool for Deep Verification
Calls the scanner-proxy Check Runner service to execute verification modules
"""
import json
import httpx
from typing import Optional, List, Dict, Any
from crewai.tools import BaseTool
from pydantic import Field


class CheckRunnerTool(BaseTool):
    """
    Tool for executing verification check modules via the scanner-proxy service.
    Provides idempotent check execution with evidence collection.
    """
    name: str = "check_runner"
    description: str = """Execute verification check modules against targets.

    Usage:
    - action: 'run' | 'list_modules' | 'validate'
    - module_id: Check module ID (e.g., 'security-headers-01')
    - target_url: Full URL of the target to check
    - mission_id: The mission ID for tracking
    - mode: ROE mode ('STEALTH' | 'BALANCED' | 'AGGRESSIVE')

    Returns check results with evidence."""

    scanner_proxy_url: str = Field(default="http://scanner-proxy:8080")
    timeout: float = Field(default=60.0)

    def _run(
        self,
        action: str = "run",
        module_id: str = "",
        target_url: str = "",
        target_id: str = "",
        mission_id: str = "",
        mode: str = "BALANCED"
    ) -> str:
        """
        Execute a check runner action.

        Args:
            action: 'run' to execute a check, 'list_modules' to get available modules, 'validate' to validate ROE
            module_id: Check module ID for run/validate actions
            target_url: Target URL for run action
            target_id: Target ID for graph linking
            mission_id: Mission ID for tracking
            mode: ROE mode (STEALTH/BALANCED/AGGRESSIVE)
        """
        try:
            with httpx.Client(timeout=self.timeout) as client:
                if action == "list_modules":
                    return self._list_modules(client)
                elif action == "run":
                    return self._run_check(client, module_id, target_url, target_id, mission_id, mode)
                elif action == "validate":
                    return self._validate_roe(client, module_id, mode)
                else:
                    return json.dumps({"error": f"Unknown action: {action}"})
        except Exception as e:
            return json.dumps({"error": str(e), "action": action})

    def _list_modules(self, client: httpx.Client) -> str:
        """List available check modules."""
        response = client.get(f"{self.scanner_proxy_url}/api/v1/checks/modules")

        if response.status_code != 200:
            return json.dumps({"error": f"Failed to list modules: {response.status_code}"})

        modules = response.json()

        # Simplify for agent consumption
        result = []
        for mod in modules:
            result.append({
                "id": mod.get("id"),
                "name": mod.get("name"),
                "category": mod.get("category"),
                "attack_type": mod.get("attack_type"),
                "method": mod.get("method", "GET"),
                "roe_modes": mod.get("roe_modes", ["STEALTH", "BALANCED", "AGGRESSIVE"]),
            })

        return json.dumps({
            "modules": result,
            "count": len(result)
        }, indent=2)

    def _run_check(
        self,
        client: httpx.Client,
        module_id: str,
        target_url: str,
        target_id: str,
        mission_id: str,
        mode: str
    ) -> str:
        """Execute a check module against a target."""
        if not module_id:
            return json.dumps({"error": "module_id is required"})
        if not target_url:
            return json.dumps({"error": "target_url is required"})
        if not mission_id:
            return json.dumps({"error": "mission_id is required"})

        # Prepare request
        request_data = {
            "mission_id": mission_id,
            "module_id": module_id,
            "target_id": target_id or f"endpoint:{target_url}",
            "target_url": target_url,
            "mode": mode.upper(),
            "options": {}
        }

        response = client.post(
            f"{self.scanner_proxy_url}/api/v1/checks/run",
            json=request_data
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            return json.dumps({
                "error": f"Check execution failed: {response.status_code}",
                "detail": error_detail,
                "module_id": module_id,
                "target_url": target_url
            })

        result = response.json()

        # Format result for agent
        return json.dumps({
            "check_result": {
                "tool_call_id": result.get("tool_call_id"),
                "module_id": result.get("module_id"),
                "target_id": result.get("target_id"),
                "status": result.get("status"),
                "vuln_status": result.get("vuln_status"),
                "evidence_count": len(result.get("evidence", [])),
                "evidence": [
                    {
                        "kind": ev.get("kind"),
                        "summary": ev.get("summary"),
                        "hash": ev.get("hash"),
                    }
                    for ev in result.get("evidence", [])
                ],
                "duration_ms": result.get("duration_ms"),
                "error": result.get("error"),
            }
        }, indent=2)

    def _validate_roe(
        self,
        client: httpx.Client,
        module_id: str,
        mode: str
    ) -> str:
        """Validate if a module is allowed under current ROE mode."""
        if not module_id:
            return json.dumps({"error": "module_id is required"})

        response = client.post(
            f"{self.scanner_proxy_url}/api/v1/checks/validate",
            json={
                "module_id": module_id,
                "mode": mode.upper()
            }
        )

        if response.status_code != 200:
            return json.dumps({
                "allowed": False,
                "reason": f"Validation failed: {response.status_code}"
            })

        return json.dumps(response.json(), indent=2)


class BatchCheckRunnerTool(BaseTool):
    """
    Tool for executing multiple verification checks in batch.
    More efficient for running a verification plan.
    """
    name: str = "batch_check_runner"
    description: str = """Execute multiple verification checks in batch.

    Usage:
    - checks: JSON array of check requests
    - mission_id: The mission ID
    - mode: ROE mode

    Each check in the array should have: module_id, target_url, target_id

    Returns array of check results."""

    scanner_proxy_url: str = Field(default="http://scanner-proxy:8080")
    timeout: float = Field(default=300.0)  # 5 minutes for batch

    def _run(
        self,
        checks: str = "[]",
        mission_id: str = "",
        mode: str = "BALANCED"
    ) -> str:
        """
        Execute batch checks.

        Args:
            checks: JSON array of check configs [{module_id, target_url, target_id}, ...]
            mission_id: Mission ID
            mode: ROE mode
        """
        if not mission_id:
            return json.dumps({"error": "mission_id is required"})

        try:
            check_list = json.loads(checks) if isinstance(checks, str) else checks
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid checks JSON"})

        if not check_list:
            return json.dumps({"error": "No checks provided", "results": []})

        results = []
        errors = []

        with httpx.Client(timeout=self.timeout) as client:
            for i, check in enumerate(check_list):
                module_id = check.get("module_id")
                target_url = check.get("target_url")
                target_id = check.get("target_id", f"endpoint:{target_url}")

                if not module_id or not target_url:
                    errors.append({
                        "index": i,
                        "error": "Missing module_id or target_url"
                    })
                    continue

                try:
                    response = client.post(
                        f"{self.scanner_proxy_url}/api/v1/checks/run",
                        json={
                            "mission_id": mission_id,
                            "module_id": module_id,
                            "target_id": target_id,
                            "target_url": target_url,
                            "mode": mode.upper(),
                            "options": {}
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        results.append({
                            "index": i,
                            "tool_call_id": result.get("tool_call_id"),
                            "module_id": module_id,
                            "target_id": target_id,
                            "status": result.get("status"),
                            "vuln_status": result.get("vuln_status"),
                            "evidence_count": len(result.get("evidence", [])),
                        })
                    else:
                        errors.append({
                            "index": i,
                            "module_id": module_id,
                            "error": f"HTTP {response.status_code}"
                        })

                except Exception as e:
                    errors.append({
                        "index": i,
                        "module_id": module_id,
                        "error": str(e)
                    })

        return json.dumps({
            "results": results,
            "errors": errors,
            "total_checks": len(check_list),
            "successful": len(results),
            "failed": len(errors)
        }, indent=2)
