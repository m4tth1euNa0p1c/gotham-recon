"""
Advanced Subfinder wrapper for CrewAI agents.

This module exposes a CrewAI-compatible tool that wraps the
ProjectDiscovery subfinder binary. It supports recursive enumeration,
the ability to query all sources and optional substring filtering. The
result is returned as a JSON-formatted string for easy consumption by
other agents or downstream tools.

Attributes
----------
SubfinderInput : pydantic.BaseModel
    Defines the arguments accepted by the tool. Includes options
    controlling recursive enumeration, source selection, filtering and
    a timeout.
SubfinderTool : crewai.tools.BaseTool
    The actual tool class, implementing the `_run` method that
    executes subfinder and processes its output.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional, Type, List

from pydantic import BaseModel, Field
try:
    from crewai.tools import BaseTool  # type: ignore
except ImportError:
    # Fallback definition for environments without crewai installed, to allow
    # local testing of the logic. This BaseTool will be replaced by the
    # real one when used within a CrewAI runtime.
    class BaseTool:
        pass


class SubfinderInput(BaseModel):
    """Schema for SubfinderTool arguments.

    Parameters
    ----------
    domain : str
        The root domain to enumerate (e.g. "example.com").
    recursive : bool, optional
        When True, enables recursive enumeration to discover nested
        subdomains. Defaults to False.
    all_sources : bool, optional
        When True, uses all passive sources available to subfinder. Defaults
        to True.
    filter_string : str, optional
        Optional substring to filter returned subdomains. Only hosts
        containing this substring will be returned. The match is
        case-sensitive. Defaults to None.
    timeout : int, optional
        Maximum allowed execution time for the subfinder process, in
        seconds. Defaults to 60.
    """

    domain: str = Field(
        ..., description="The root domain to scan (without protocol or www)."
    )
    recursive: bool = Field(
        False, description="Enable recursive subdomain discovery."
    )
    all_sources: bool = Field(
        True, description="Use all available passive sources."
    )
    filter_string: Optional[str] = Field(
        None,
        description="Substring filter to restrict results to hosts containing this value.",
    )
    smart_filter: bool = Field(
        False, description="If True, filters results to only include high-interest domains (dev, staging, admin, vpn...)."
    )
    limit: Optional[int] = Field(
        None, description="Maximum number of subdomains to return."
    )
    timeout: int = Field(
        60, description="Process timeout in seconds."
    )


class SubfinderTool(BaseTool):
    """CrewAI tool wrapping the subfinder binary.

    This tool executes the subfinder binary with the specified options,
    parses the JSON-lines output, applies optional filtering and returns
    a JSON string describing the results. In case of errors, the JSON
    returned will contain an 'error' key with contextual information.
    """
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
        """Run subfinder and process the results.

        Returns
        -------
        str
            A JSON-formatted string containing the keys 'domain', 'count',
            'subdomains' and 'options'. On error, returns a JSON string
            containing 'error' and 'message'.
        """
        # Check if subfinder binary is available
        use_docker = False
        if not shutil.which("subfinder"):
            # Check if docker is available
            if shutil.which("docker"):
                use_docker = True
            else:
                return json.dumps(
                    {
                        "error": "subfinder_binaire_introuvable",
                        "message": (
                            "Neither 'subfinder' binary nor 'docker' is available. "
                            "Install subfinder locally or build the docker image 'gotham/subfinder'."
                        ),
                        "domain": domain,
                        "subdomains": [],
                    },
                    indent=2,
                )

        # Build command
        if use_docker:
            # Docker command: docker run --rm gotham/subfinder -d domain -silent -oJ ...
            cmd: List[str] = [
                "docker",
                "run",
                "--rm",
                "gotham/subfinder",
                "-d",
                domain,
                "-silent",
                "-oJ",
            ]
        else:
            # Local command
            cmd: List[str] = ["subfinder", "-d", domain, "-silent", "-oJ"]

        if all_sources:
            cmd.append("-all")
        if recursive:
            cmd.append("-recursive")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return json.dumps(
                {
                    "error": "subfinder_timeout",
                    "message": f"Execution exceeded the timeout of {timeout} seconds.",
                    "domain": domain,
                    "subdomains": [],
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {
                    "error": "subfinder_exception",
                    "message": f"Unexpected error: {str(e)}",
                    "domain": domain,
                    "subdomains": [],
                },
                indent=2,
            )

        if proc.returncode != 0:
            return json.dumps(
                {
                    "error": "subfinder_exit_code",
                    "exit_code": proc.returncode,
                    "stderr": proc.stderr,
                    "domain": domain,
                    "subdomains": [],
                },
                indent=2,
            )

        # Parse output
        subdomains: List[str] = []
        stdout = proc.stdout.strip()
        if stdout:
            lines = [line.strip() for line in stdout.split("\n") if line.strip()]
            for line in lines:
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
        
        # --- Smart Filtering & limit ---
        smart_filtered_subdomains = []
        if smart_filter:
            # Keywords indicating high value targets
            keywords = ['dev', 'test', 'stg', 'stage', 'sandbox', 'beta', 'vpn', 'internal', 'admin', 'preview', 'staging', 'api', 'dashboard', 'auth', 'login', 'portal']
            for sd in subdomains:
                if any(k in sd for k in keywords):
                    smart_filtered_subdomains.append(sd)
            
            # If smart filter is on, we primarily return these. 
            # If the list is empty, we might want to fallback or just return empty.
            # Here we replace the main list with the filtered one.
            subdomains = smart_filtered_subdomains

        # Apply limit
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

        # 🔹 Ajout important : signaler explicitement l'absence de résultats
        if len(subdomains) == 0:
            result["status"] = "no_results"
            result["message"] = (
                "Subfinder executed successfully but did not find any subdomains "
                "matching the criteria (smart_filter active)."
            )

        return json.dumps(result, indent=2)
