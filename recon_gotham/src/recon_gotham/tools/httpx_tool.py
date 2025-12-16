"""
Httpx wrapper for CrewAI agents.

This module exposes a CrewAI-compatible tool that wraps the
ProjectDiscovery httpx binary. It takes a list of subdomains and
performs active probing to retrieve status codes, technologies,
titles, and IP addresses, returning a structured JSON string.
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
    from crewai.tools import BaseTool  # type: ignore
except ImportError:
    # Fallback for environments without crewai installed
    class BaseTool:
        pass


class HttpxInput(BaseModel):
    """Schema for HttpxTool arguments."""

    subdomains: List[str] = Field(
        ..., description="List of subdomains (strings) to probe."
    )
    ports: Optional[str] = Field(
        None,
        description="Comma-separated list of ports to probe (e.g., '80,443,8080'). "
                    "If omitted, httpx will use its standard port logic."
    )
    timeout: int = Field(
        10,
        description="Timeout in seconds per host. Default is 10s."
    )


class HttpxTool(BaseTool):
    """CrewAI tool wrapping the httpx binary.

    This tool takes a list of subdomains, probes them using httpx, and returns
    detailed technical information (status, tech stack, title, IP) as a JSON string.
    """

    name: str = "httpx_probe"
    description: str = (
        "Probe a list of subdomains to gather technical details: status code, "
        "technology stack, page title, and IP address. Returns structured JSON results."
    )
    args_schema: Type[BaseModel] = HttpxInput

    def _run(
        self,
        subdomains: List[str],
        ports: Optional[str] = None,
        timeout: int = 10,
    ) -> str:
        """Run httpx on a list of domains."""
        if not subdomains:
            return json.dumps(
                {
                    "target_count": 0,
                    "result_count": 0,
                    "results": [],
                    "options": {"ports": ports, "timeout": timeout},
                },
                indent=2,
            )

        # Check binary availability
        use_docker = False
        if not shutil.which("httpx"):
            if shutil.which("docker"):
                use_docker = True
            else:
                return json.dumps(
                    {
                        "error": "httpx_not_found",
                        "message": "Neither 'httpx' binary nor 'docker' is available.",
                        "subdomains": subdomains,
                        "results": [],
                    },
                    indent=2,
                )

        # Create temp file for input list
        fd, temp_path = tempfile.mkstemp(suffix=".txt", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                for sd in subdomains:
                    f.write(f"{sd}\n")

            # Build command
            # We request:
            # - status code (-sc)
            # - title (-title)
            # - technology detection (-tech-detect)
            # - IP info (-ip)
            # - JSON output (-json)
            # - silent mode (-silent)
            if use_docker:
                cmd = [
                    "docker", "run", "--rm", "-i",
                    "projectdiscovery/httpx",
                    "-sc", "-title", "-tech-detect", "-ip",
                    "-json", "-silent",
                    "-timeout", str(timeout),
                ]
            else:
                cmd = [
                    "httpx",
                    "-l", temp_path,
                    "-sc", "-title", "-tech-detect", "-ip",
                    "-json", "-silent",
                    "-timeout", str(timeout),
                ]

            if ports:
                cmd.extend(["-p", ports])

            # Execute command
            try:
                if use_docker:
                    # Pass subdomains via stdin for docker
                    with open(temp_path, "r") as f:
                        stdin_content = f.read()

                    proc = subprocess.run(
                        cmd,
                        input=stdin_content,
                        capture_output=True,
                        text=True,
                        timeout=timeout * max(1, len(subdomains)) + 30,
                    )
                else:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=timeout * max(1, len(subdomains)) + 30,
                    )
            except subprocess.TimeoutExpired:
                return json.dumps(
                    {
                        "error": "httpx_timeout",
                        "message": f"Execution exceeded the aggregate timeout.",
                        "subdomains": subdomains,
                        "results": [],
                    },
                    indent=2,
                )
            except Exception as e:
                return json.dumps(
                    {
                        "error": "httpx_exception",
                        "message": f"Unexpected error: {str(e)}",
                        "subdomains": subdomains,
                        "results": [],
                    },
                    indent=2,
                )
        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if proc.returncode != 0:
            return json.dumps(
                {
                    "error": "httpx_error",
                    "message": proc.stderr or "Unknown error",
                    "exit_code": proc.returncode,
                    "subdomains": subdomains,
                    "results": [],
                },
                indent=2,
            )

        # Parse JSON Lines output
        results: List[Dict[str, Any]] = []
        stdout = proc.stdout.strip()
        if stdout:
            for line in stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # httpx JSON typically has:
                    # - input: original host
                    # - url: final probed URL
                    # - status_code
                    # - title
                    # - tech: list of detected technologies (if -tech-detect)
                    # - ip / a: IP info (if -ip)
                    ip_value = data.get("ip")
                    if not ip_value and "a" in data:
                        ip_value = data["a"][0] if data["a"] else None

                    clean_res: Dict[str, Any] = {
                        "host": data.get("input"),
                        "url": data.get("url"),
                        "status_code": data.get("status_code"),
                        "title": data.get("title"),
                        "technologies": data.get("tech", []),
                        "ip": ip_value,
                    }
                    results.append(clean_res)
                except json.JSONDecodeError:
                    continue

        output = {
            "target_count": len(subdomains),
            "result_count": len(results),
            "results": results,
            "options": {
                "ports": ports,
                "timeout": timeout,
            },
        }
        return json.dumps(output, indent=2)
