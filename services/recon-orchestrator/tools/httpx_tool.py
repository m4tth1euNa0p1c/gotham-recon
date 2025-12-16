"""
Httpx wrapper for CrewAI agents.
Wraps ProjectDiscovery httpx for HTTP probing and tech detection.
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


class HttpxInput(BaseModel):
    """Schema for HttpxTool arguments."""
    subdomains: List[str] = Field(..., description="List of subdomains to probe.")
    ports: Optional[str] = Field(None, description="Comma-separated ports (e.g., '80,443,8080').")
    timeout: int = Field(10, description="Timeout in seconds per host.")


class HttpxTool(BaseTool):
    """CrewAI tool wrapping the httpx binary."""
    name: str = "httpx_probe"
    description: str = (
        "Probe a list of subdomains to gather technical details: status code, "
        "technology stack, page title, and IP address. Returns structured JSON."
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
            return json.dumps({
                "target_count": 0,
                "result_count": 0,
                "results": [],
            }, indent=2)

        # Use httpx-pd (ProjectDiscovery) to avoid conflict with Python httpx package
        httpx_binary = "httpx-pd"
        use_docker = False
        if not shutil.which(httpx_binary):
            # Fallback to httpx if httpx-pd not available
            if shutil.which("httpx"):
                httpx_binary = "httpx"
            elif shutil.which("docker"):
                use_docker = True
            else:
                return json.dumps({
                    "error": "httpx_not_found",
                    "message": "Neither 'httpx-pd' binary nor 'docker' is available.",
                    "results": [],
                }, indent=2)

        fd, temp_path = tempfile.mkstemp(suffix=".txt", text=True)
        try:
            with os.fdopen(fd, "w") as f:
                for sd in subdomains:
                    f.write(f"{sd}\n")

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
                    httpx_binary,
                    "-l", temp_path,
                    "-sc", "-title", "-tech-detect", "-ip",
                    "-json", "-silent",
                    "-timeout", str(timeout),
                ]

            if ports:
                cmd.extend(["-p", ports])

            try:
                if use_docker:
                    with open(temp_path, "r") as f:
                        stdin_content = f.read()
                    proc = subprocess.run(
                        cmd, input=stdin_content,
                        capture_output=True, text=True,
                        timeout=timeout * max(1, len(subdomains)) + 30,
                    )
                else:
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True,
                        timeout=timeout * max(1, len(subdomains)) + 30,
                    )
            except subprocess.TimeoutExpired:
                return json.dumps({
                    "error": "httpx_timeout",
                    "message": "Execution exceeded timeout.",
                    "results": [],
                }, indent=2)
            except Exception as e:
                return json.dumps({
                    "error": "httpx_exception",
                    "message": str(e),
                    "results": [],
                }, indent=2)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if proc.returncode != 0:
            return json.dumps({
                "error": "httpx_error",
                "message": proc.stderr or "Unknown error",
                "results": [],
            }, indent=2)

        results: List[Dict[str, Any]] = []
        stdout = proc.stdout.strip()
        if stdout:
            for line in stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ip_value = data.get("ip")
                    if not ip_value and "a" in data:
                        ip_value = data["a"][0] if data["a"] else None

                    results.append({
                        "host": data.get("input"),
                        "url": data.get("url"),
                        "status_code": data.get("status_code"),
                        "title": data.get("title"),
                        "technologies": data.get("tech", []),
                        "ip": ip_value,
                    })
                except json.JSONDecodeError:
                    continue

        return json.dumps({
            "target_count": len(subdomains),
            "result_count": len(results),
            "results": results,
        }, indent=2)
