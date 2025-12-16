"""
JavaScript Miner tool for CrewAI agents.
Extracts JS files, API endpoints, and secrets from web pages.
"""
from __future__ import annotations

import json
import re
import requests
from typing import List, Type

from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass


class JsMinerInput(BaseModel):
    """Schema for JsMinerTool arguments."""
    urls: List[str] = Field(
        ..., description="List of HTTP URLs to analyze for JS files and endpoints."
    )


class JsMinerTool(BaseTool):
    """Extracts JavaScript files, API endpoints, and secrets from web pages."""
    name: str = "js_miner"
    description: str = (
        "Analyzes a list of HTTP URLs to extract JavaScript files, API endpoints, and secrets. "
        "Returns structured JSON with js_files, endpoints, and secrets."
    )
    args_schema: Type[BaseModel] = JsMinerInput

    def _run(self, urls: List[str]) -> str:
        """Analyze URLs for JS intelligence."""
        results = []

        if isinstance(urls, str):
            try:
                urls = json.loads(urls)
            except:
                urls = [urls]

        for url in urls:
            if not url or not url.startswith("http"):
                continue

            try:
                resp = requests.get(url, timeout=10, verify=False)
                html = resp.text
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "js": {"js_files": [], "endpoints": [], "secrets": []}
                })
                continue

            # Extract JS files
            js_files = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html, re.IGNORECASE)
            js_files_full = []
            for src in js_files:
                if src.startswith("//"):
                    js_files_full.append(f"https:{src}")
                elif src.startswith("/"):
                    js_files_full.append(f"{url.rstrip('/')}{src}")
                elif src.startswith("http"):
                    js_files_full.append(src)
                else:
                    js_files_full.append(f"{url.rstrip('/')}/{src}")

            # Detect endpoints
            endpoints = []
            method_patterns = [
                r'axios\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                r'\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                r'fetch\s*\(\s*["\']([^"\']+)["\']',
            ]

            for pat in method_patterns:
                for m in re.finditer(pat, html, re.IGNORECASE):
                    if len(m.groups()) == 2:
                        method = m.group(1).upper()
                        path = m.group(2)
                    else:
                        method = "GET"
                        path = m.group(1)
                    if self._is_interesting_path(path):
                        endpoints.append({
                            "path": path,
                            "method": method,
                            "source_js": "Explicit Call"
                        })

            # String literals that look like API paths
            literal_pattern = r'["\'](/api/[a-zA-Z0-9/_\-]+|/v[0-9]+/[a-zA-Z0-9/_\-]+|/auth/[a-zA-Z0-9/_\-]+|/graphql[a-zA-Z0-9/_\-]*)["\']'
            for m in re.finditer(literal_pattern, html):
                path = m.group(1)
                endpoints.append({
                    "path": path,
                    "method": "UNKNOWN",
                    "source_js": "String Literal"
                })

            # Detect secrets (AWS keys, etc.)
            secrets = []
            for m in re.finditer(r'(AKIA[0-9A-Z]{16})', html):
                secrets.append({
                    "value": m.group(1),
                    "kind": "AWS_KEY",
                    "source_js": "Inline HTML"
                })

            # Deduplicate endpoints
            unique_endpoints = {}
            for ep in endpoints:
                p = ep["path"]
                m = ep["method"]
                if p not in unique_endpoints:
                    unique_endpoints[p] = ep
                elif unique_endpoints[p]["method"] == "UNKNOWN" and m != "UNKNOWN":
                    unique_endpoints[p] = ep

            results.append({
                "url": url,
                "js": {
                    "js_files": list(set(js_files_full)),
                    "endpoints": list(unique_endpoints.values()),
                    "secrets": [dict(t) for t in {tuple(d.items()) for d in secrets}]
                }
            })

        return json.dumps(results, indent=2)

    def _is_interesting_path(self, path: str) -> bool:
        """Check if path is worth tracking."""
        if not path or len(path) < 2:
            return False
        if " " in path:
            return False
        if path.endswith((".png", ".jpg", ".svg", ".css", ".js", ".woff")):
            return False
        return True
