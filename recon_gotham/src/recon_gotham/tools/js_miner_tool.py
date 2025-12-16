from __future__ import annotations
import json
import re
import requests
from typing import List, Dict, Any, Type
from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass

class JsMinerInput(BaseModel):
    """Schema for JsMinerTool arguments."""
    urls: List[str] = Field(
        ..., description="List of HTTP Service URLs to analyze (e.g., ['https://api.target.com', 'https://www.target.com']). Do NOT invent URLs."
    )

class JsMinerTool(BaseTool):
    """
    Downloads HTML pages from a list of URLs, extracts JS files,
    and attempts to detect endpoints and secrets via regex.
    Returns a structured JSON ready for AssetGraph ingestion.
    """
    name: str = "js_miner"
    description: str = (
        "Analyzes a list of HTTP URLs to extract JavaScript files, API endpoints, and secrets. "
        "Input MUST be a list of valid URLs. Returns strict JSON."
    )
    args_schema: Type[BaseModel] = JsMinerInput

    def _run(self, urls: List[str]) -> str:
        results = []

        # Ensure we have a list of strings
        if isinstance(urls, str):
            try:
                urls = json.loads(urls)
            except:
                urls = [urls]
        
        for url in urls:
            # Basic validation
            if not url or not url.startswith("http"):
                continue

            try:
                # 1. Download Page
                resp = requests.get(url, timeout=10, verify=False) # verify=False for broader recon compatibility
                html = resp.text
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "js": {
                        "js_files": [],
                        "endpoints": [],
                        "secrets": []
                    }
                })
                continue

            # 2. Extract JS files (Simple Regex)
            # Looks for <script src="...">
            js_files = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html, re.IGNORECASE)
            
            # Normalize URLs (handle relative paths)
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

            # 3. Detect Endpoints (Advanced Regex)
            endpoints = []
            
            # Common patterns for API calls in JS
            # 1. fetch('/api/...')
            # 2. axios.get('/api/...')
            # 3. xhr.open('GET', '/api/...')
            # 4. "url": "/api/..." (jQuery/Ajax objects)
            
            # Capture Method and Path if possible
            # Regex for axios/fetch with methods
            # Matches: axios.post('/api/login') -> Group 1=post, Group 2=/api/login
            method_patterns = [
                r'axios\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                r'\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', # Generic SDKs
                r'fetch\s*\(\s*["\']([^"\']+)["\']', # fetch defaults to GET usually, but capture path
            ]
            
            for pat in method_patterns:
                for m in re.finditer(pat, html, re.IGNORECASE):
                    if len(m.groups()) == 2:
                        method = m.group(1).upper()
                        path = m.group(2)
                    else:
                        method = "GET" # Fetch default
                        path = m.group(1)
                        
                    if self._is_interesting_path(path):
                        endpoints.append({
                            "path": path,
                            "method": method,
                            "source_js": "Explicit Call"
                        })

            # Catch-all for string literals looking like API paths (e.g. constant defs)
            # Matches strings starting with /api, /v1, /auth, etc.
            # Avoid long strings
            literal_pattern = r'["\'](/api/[a-zA-Z0-9/_\-]+|/v[0-9]+/[a-zA-Z0-9/_\-]+|/auth/[a-zA-Z0-9/_\-]+|/graphql[a-zA-Z0-9/_\-]*)["\']'
            for m in re.finditer(literal_pattern, html):
                path = m.group(1)
                endpoints.append({
                    "path": path,
                    "method": "UNKNOWN", # Literal, usage unknown
                    "source_js": "String Literal" 
                })

            # 4. Detect Secrets (Simple AWS-like Regex)
            secrets = []
            for m in re.finditer(r'(AKIA[0-9A-Z]{16})', html):
                secrets.append({
                    "value": m.group(1),
                    "kind": "AWS_KEY",
                    "source_js": "Inline HTML"
                })

            # Deduplication with Priority (Method > UNKNOWN)
            unique_endpoints = {}
            for ep in endpoints:
                p = ep["path"]
                m = ep["method"]
                
                if p not in unique_endpoints:
                    unique_endpoints[p] = ep
                else:
                    if unique_endpoints[p]["method"] == "UNKNOWN" and m != "UNKNOWN":
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
        if not path or len(path) < 2: return False
        if " " in path: return False
        # Filter out common false positives
        if path.endswith((".png", ".jpg", ".svg", ".css", ".js", ".woff")): return False
        return True
