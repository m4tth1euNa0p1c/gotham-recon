"""
Nuclei wrapper for CrewAI agents.
Wraps ProjectDiscovery Nuclei for vulnerability scanning.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import os
from typing import Optional, Type, List, Dict, Any

from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass


class NucleiInput(BaseModel):
    """Schema for NucleiTool arguments."""
    targets: List[str] = Field(..., description="List of URLs or hosts to scan.")
    templates: Optional[str] = Field(
        None,
        description="Comma-separated template tags to use (e.g., 'cve,misconfig,exposure'). Default scans common vulns."
    )
    severity: Optional[str] = Field(
        "medium,high,critical",
        description="Comma-separated severity levels (info,low,medium,high,critical)."
    )
    rate_limit: int = Field(50, description="Rate limit (requests per second).")
    timeout: int = Field(120, description="Scan timeout in seconds.")


class NucleiTool(BaseTool):
    """CrewAI tool wrapping the Nuclei vulnerability scanner."""
    name: str = "nuclei_scan"
    description: str = (
        "Scan targets for vulnerabilities using ProjectDiscovery's Nuclei scanner. "
        "Returns JSON with discovered vulnerabilities including CVEs, misconfigurations, "
        "exposures, and other security issues."
    )
    args_schema: Type[BaseModel] = NucleiInput

    def _run(
        self,
        targets: List[str],
        templates: Optional[str] = None,
        severity: Optional[str] = "medium,high,critical",
        rate_limit: int = 50,
        timeout: int = 120,
    ) -> str:
        """Run Nuclei vulnerability scan on targets."""
        if not targets:
            return json.dumps({
                "target_count": 0,
                "vulnerability_count": 0,
                "vulnerabilities": [],
            }, indent=2)

        # Check if nuclei is available
        if not shutil.which("nuclei"):
            return json.dumps({
                "error": "nuclei_not_found",
                "message": "Nuclei binary is not available in PATH.",
                "vulnerabilities": [],
            }, indent=2)

        # Create temp file with targets
        fd, targets_file = tempfile.mkstemp(suffix=".txt", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                for target in targets:
                    # Ensure proper URL format
                    if not target.startswith(("http://", "https://")):
                        f.write(f"https://{target}\n")
                        f.write(f"http://{target}\n")
                    else:
                        f.write(f"{target}\n")

            # Build nuclei command
            cmd = [
                "nuclei",
                "-l", targets_file,
                "-jsonl",  # JSON Lines output
                "-silent",
                "-rate-limit", str(rate_limit),
                "-timeout", "10",  # Per-request timeout
                "-retries", "1",
                "-no-color",
            ]

            # Add severity filter
            if severity:
                cmd.extend(["-severity", severity])

            # Add template tags if specified
            if templates:
                cmd.extend(["-tags", templates])
            else:
                # Default: scan for common web vulnerabilities
                cmd.extend(["-tags", "cve,misconfig,exposure,xss,sqli,lfi,rce,ssrf,redirect,disclosure"])

            # Run nuclei
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return json.dumps({
                    "error": "nuclei_timeout",
                    "message": f"Scan exceeded timeout of {timeout}s.",
                    "partial_results": True,
                    "vulnerabilities": [],
                }, indent=2)
            except Exception as e:
                return json.dumps({
                    "error": "nuclei_exception",
                    "message": str(e),
                    "vulnerabilities": [],
                }, indent=2)

        finally:
            if os.path.exists(targets_file):
                os.remove(targets_file)

        # Parse results
        vulnerabilities: List[Dict[str, Any]] = []
        stdout = proc.stdout.strip()

        if stdout:
            for line in stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    finding = json.loads(line)

                    # Extract relevant fields
                    vuln = {
                        "template_id": finding.get("template-id", "unknown"),
                        "template_name": finding.get("info", {}).get("name", "Unknown"),
                        "severity": finding.get("info", {}).get("severity", "unknown"),
                        "type": finding.get("type", "unknown"),
                        "host": finding.get("host", ""),
                        "matched_at": finding.get("matched-at", ""),
                        "matcher_name": finding.get("matcher-name", ""),
                        "description": finding.get("info", {}).get("description", ""),
                        "reference": finding.get("info", {}).get("reference", []),
                        "tags": finding.get("info", {}).get("tags", []),
                        "curl_command": finding.get("curl-command", ""),
                        "extracted_results": finding.get("extracted-results", []),
                    }

                    # Map severity to risk score
                    severity_scores = {
                        "info": 10,
                        "low": 30,
                        "medium": 50,
                        "high": 75,
                        "critical": 95,
                    }
                    vuln["risk_score"] = severity_scores.get(vuln["severity"], 50)

                    # Map to attack type
                    vuln["attack_type"] = self._map_to_attack_type(finding)

                    vulnerabilities.append(vuln)

                except json.JSONDecodeError:
                    continue

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        vulnerabilities.sort(key=lambda v: severity_order.get(v["severity"], 5))

        return json.dumps({
            "target_count": len(targets),
            "vulnerability_count": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "severity_summary": self._get_severity_summary(vulnerabilities),
        }, indent=2)

    def _map_to_attack_type(self, finding: Dict[str, Any]) -> str:
        """Map Nuclei finding to standard attack type."""
        template_id = finding.get("template-id", "").lower()
        tags = finding.get("info", {}).get("tags", [])
        tags_str = " ".join(tags).lower()

        # Map based on template ID and tags
        if "sqli" in template_id or "sql" in tags_str:
            return "SQLI"
        elif "xss" in template_id or "xss" in tags_str:
            return "XSS"
        elif "rce" in template_id or "rce" in tags_str or "command" in tags_str:
            return "RCE"
        elif "ssrf" in template_id or "ssrf" in tags_str:
            return "SSRF"
        elif "lfi" in template_id or "lfi" in tags_str or "path-traversal" in tags_str:
            return "LFI"
        elif "rfi" in template_id or "rfi" in tags_str:
            return "RFI"
        elif "redirect" in template_id or "redirect" in tags_str:
            return "OPEN_REDIRECT"
        elif "xxe" in template_id or "xxe" in tags_str:
            return "XXE"
        elif "csrf" in template_id or "csrf" in tags_str:
            return "CSRF"
        elif "auth" in template_id or "auth" in tags_str or "bypass" in tags_str:
            return "AUTH_BYPASS"
        elif "disclosure" in template_id or "exposure" in tags_str or "info" in tags_str:
            return "INFO_DISCLOSURE"
        elif "misconfig" in template_id or "misconfig" in tags_str:
            return "MISCONFIGURATION"
        elif "cve" in template_id:
            return "CVE"
        else:
            return "OTHER"

    def _get_severity_summary(self, vulnerabilities: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get count of vulnerabilities by severity."""
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for vuln in vulnerabilities:
            sev = vuln.get("severity", "info")
            if sev in summary:
                summary[sev] += 1
        return summary


class NucleiQuickScanTool(BaseTool):
    """Quick Nuclei scan focused on high-severity issues only."""
    name: str = "nuclei_quick_scan"
    description: str = (
        "Quick vulnerability scan for high and critical severity issues only. "
        "Faster than full scan, focuses on most impactful vulnerabilities."
    )
    args_schema: Type[BaseModel] = NucleiInput

    def _run(
        self,
        targets: List[str],
        templates: Optional[str] = None,
        severity: Optional[str] = "high,critical",
        rate_limit: int = 100,
        timeout: int = 60,
    ) -> str:
        """Run quick Nuclei scan."""
        full_tool = NucleiTool()
        return full_tool._run(
            targets=targets,
            templates=templates or "cve,critical",
            severity=severity,
            rate_limit=rate_limit,
            timeout=timeout,
        )
