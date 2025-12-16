"""
Advanced Subfinder wrapper for CrewAI agents.
Wraps ProjectDiscovery subfinder binary for subdomain enumeration.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional, Type, List

from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass


class SubfinderInput(BaseModel):
    """Schema for SubfinderTool arguments."""
    domain: str = Field(..., description="The root domain to scan (without protocol or www).")
    recursive: bool = Field(False, description="Enable recursive subdomain discovery.")
    all_sources: bool = Field(True, description="Use all available passive sources.")
    filter_string: Optional[str] = Field(None, description="Substring filter to restrict results.")
    smart_filter: bool = Field(False, description="If True, filters to high-interest domains only.")
    limit: Optional[int] = Field(None, description="Maximum number of subdomains to return.")
    timeout: int = Field(60, description="Process timeout in seconds.")


class SubfinderTool(BaseTool):
    """CrewAI tool wrapping the subfinder binary."""
    name: str = "subfinder_enum"
    description: str = (
        "Enumerate subdomains using ProjectDiscovery's subfinder binary with support for "
        "recursive mode, source selection and filtering. Returns a JSON string "
        "with the domain, count, discovered subdomains and options used."
    )
    args_schema: Type[BaseModel] = SubfinderInput

    def _run(
        self,
        domain: str,
        recursive: bool = False,
        all_sources: bool = True,
        filter_string: Optional[str] = None,
        smart_filter: bool = False,
        limit: Optional[int] = None,
        timeout: int = 60,
    ) -> str:
        """Run subfinder and process the results."""
        use_docker = False
        if not shutil.which("subfinder"):
            if shutil.which("docker"):
                use_docker = True
            else:
                return json.dumps({
                    "error": "subfinder_not_found",
                    "message": "Neither 'subfinder' binary nor 'docker' is available.",
                    "domain": domain,
                    "subdomains": [],
                }, indent=2)

        if use_docker:
            cmd: List[str] = [
                "docker", "run", "--rm",
                "projectdiscovery/subfinder",
                "-d", domain, "-silent", "-oJ",
            ]
        else:
            cmd = ["subfinder", "-d", domain, "-silent", "-oJ"]

        if all_sources:
            cmd.append("-all")
        if recursive:
            cmd.append("-recursive")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return json.dumps({
                "error": "subfinder_timeout",
                "message": f"Execution exceeded timeout of {timeout}s.",
                "domain": domain,
                "subdomains": [],
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "error": "subfinder_exception",
                "message": str(e),
                "domain": domain,
                "subdomains": [],
            }, indent=2)

        if proc.returncode != 0:
            return json.dumps({
                "error": "subfinder_exit_code",
                "exit_code": proc.returncode,
                "stderr": proc.stderr,
                "domain": domain,
                "subdomains": [],
            }, indent=2)

        subdomains: List[str] = []
        stdout = proc.stdout.strip()
        if stdout:
            for line in stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    host = obj.get("host")
                    if host:
                        if filter_string and filter_string not in host:
                            continue
                        if host not in subdomains:
                            subdomains.append(host)
                except json.JSONDecodeError:
                    continue

        if smart_filter:
            keywords = ['dev', 'test', 'stg', 'stage', 'sandbox', 'beta', 'vpn',
                       'internal', 'admin', 'preview', 'staging', 'api', 'dashboard',
                       'auth', 'login', 'portal']
            subdomains = [sd for sd in subdomains if any(k in sd for k in keywords)]

        if limit and len(subdomains) > limit:
            subdomains = subdomains[:limit]

        result = {
            "domain": domain,
            "count": len(subdomains),
            "subdomains": subdomains,
            "options": {
                "recursive": recursive,
                "all_sources": all_sources,
                "filter_string": filter_string,
                "smart_filter": smart_filter,
                "limit": limit,
                "timeout": timeout,
            },
        }

        if len(subdomains) == 0:
            result["status"] = "no_results"
            result["message"] = "Subfinder executed but found no matching subdomains."

        return json.dumps(result, indent=2)
