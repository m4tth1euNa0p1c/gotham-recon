"""
Active Recon - Phase 3 HTTP probing, crawling, JS mining
Full implementation with httpx, wayback, html_crawler, js_miner
"""
import os
import json
import re
import shutil
import subprocess
import tempfile
import asyncio
import requests
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from urllib.parse import urlparse
import httpx as httpx_client
import structlog

logger = structlog.get_logger()
app = FastAPI(title="Active Recon", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Service URLs
GRAPH_SERVICE = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")


class ExecuteRequest(BaseModel):
    mission_id: str
    target_domain: str
    mode: str = "aggressive"
    options: Dict[str, Any] = {}


# ============================================
# HTTPX TOOL
# ============================================
class HttpxTool:
    """HTTP probing tool using httpx binary or Docker"""

    def run(self, subdomains: List[str], ports: Optional[str] = None, timeout: int = 10) -> Dict:
        if not subdomains:
            return {"target_count": 0, "result_count": 0, "results": []}

        use_docker = False
        # Check for ProjectDiscovery httpx binary (not Python httpx)
        httpx_binary = "/usr/local/bin/httpx"
        if not os.path.isfile(httpx_binary):
            if shutil.which("docker"):
                use_docker = True
            else:
                return {"error": "httpx_not_found", "results": []}

        # Use /tmp for volume mounting with Docker
        temp_dir = "/tmp"
        temp_filename = f"httpx_targets_{os.getpid()}.txt"
        temp_path = os.path.join(temp_dir, temp_filename)

        try:
            with open(temp_path, "w") as f:
                for sd in subdomains:
                    f.write(f"{sd}\n")

            logger.info("httpx_input_file", path=temp_path, targets=len(subdomains))

            if use_docker:
                # Mount the temp file into Docker container
                cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{temp_path}:/targets.txt:ro",
                    "projectdiscovery/httpx",
                    "-l", "/targets.txt",
                    "-sc", "-title", "-tech-detect", "-ip",
                    "-json", "-silent",
                    "-timeout", str(timeout),
                ]
            else:
                cmd = [
                    httpx_binary,  # Use full path to ProjectDiscovery httpx
                    "-l", temp_path,
                    "-sc", "-title", "-tech-detect", "-ip",
                    "-json", "-silent",
                    "-timeout", str(timeout),
                ]

            if ports:
                cmd.extend(["-p", ports])

            logger.info("httpx_cmd", cmd=" ".join(cmd))

            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout * max(1, len(subdomains)) + 60
                )
                logger.info("httpx_raw_output", stdout_len=len(proc.stdout or ""), stderr=proc.stderr[:500] if proc.stderr else "")
            except subprocess.TimeoutExpired:
                return {"error": "httpx_timeout", "results": []}
            except Exception as e:
                logger.error("httpx_error", error=str(e))
                return {"error": str(e), "results": []}
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        results = []
        stdout = proc.stdout.strip() if proc.stdout else ""
        if stdout:
            for line in stdout.split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    ip_value = data.get("ip") or (data.get("a", [None])[0] if data.get("a") else None)
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

        return {
            "target_count": len(subdomains),
            "result_count": len(results),
            "results": results
        }


# ============================================
# WAYBACK TOOL
# ============================================
class WaybackTool:
    """Queries Wayback Machine for historical endpoints"""

    INTERESTING_EXTENSIONS = [".php", ".asp", ".aspx", ".jsp", ".json", ".xml"]
    INTERESTING_KEYWORDS = ["/api/", "/admin/", "/graphql", "/wp-json/", "/auth/", "/v1/", "/v2/"]
    IGNORED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".svg", ".woff", ".ttf", ".ico"]

    def run(self, domains: List[str]) -> List[Dict]:
        results = []

        for domain in domains:
            if not domain:
                continue

            api_url = f"http://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=json&fl=original&collapse=urlkey&limit=3000"

            try:
                time.sleep(1)  # Be polite
                resp = requests.get(api_url, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    if data and data[0][0] == "original":
                        data = data[1:]

                    found_urls = set()

                    for row in data:
                        raw_url = row[0]
                        lower_url = raw_url.lower()

                        if any(lower_url.endswith(ext) for ext in self.IGNORED_EXTENSIONS):
                            continue

                        is_interesting = (
                            any(ext in lower_url for ext in self.INTERESTING_EXTENSIONS) or
                            any(kw in lower_url for kw in self.INTERESTING_KEYWORDS)
                        )

                        if is_interesting:
                            base_path = raw_url.split("?")[0] if "?" in raw_url else raw_url
                            found_urls.add((raw_url, base_path))

                    seen_paths = set()
                    for full_url, base_path in found_urls:
                        if base_path in seen_paths:
                            continue
                        seen_paths.add(base_path)
                        results.append({
                            "path": full_url,
                            "method": "GET",
                            "source": "WAYBACK",
                            "origin": domain
                        })
            except Exception as e:
                logger.warning("wayback_error", domain=domain, error=str(e))
                continue

        return results


# ============================================
# HTML CRAWLER TOOL
# ============================================
class HtmlCrawlerTool:
    """Crawls HTML pages to extract endpoints from href, action, src"""

    INTERESTING_PREFIXES = ["/api", "/auth", "/admin", "/backend", "/graphql", "/ajax", "/v1", "/v2"]

    def run(self, urls: List[str]) -> List[Dict]:
        results = []

        for url in urls:
            if not url or not url.startswith("http"):
                continue

            try:
                resp = requests.get(url, timeout=10, verify=False)
                html = resp.text
            except Exception:
                continue

            found_endpoints = []

            # Forms
            for fm in re.finditer(r'<form\s+([^>]+)>', html, re.IGNORECASE):
                attrs = fm.group(1)
                action_match = re.search(r'action=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
                method_match = re.search(r'method=["\']([^"\']+)["\']', attrs, re.IGNORECASE)

                action = action_match.group(1) if action_match else ""
                method = method_match.group(1).upper() if method_match else "GET"

                if action and self._is_interesting(action):
                    found_endpoints.append({
                        "path": action,
                        "method": method,
                        "source": "HTML_FORM",
                        "origin": url
                    })

            # Links
            for link in re.findall(r'(?:href|src)=["\']([^"\']+)["\']', html, re.IGNORECASE):
                if self._is_interesting(link):
                    found_endpoints.append({
                        "path": link,
                        "method": "GET",
                        "source": "HTML_LINK",
                        "origin": url
                    })

            # Deduplicate
            unique_eps = {f"{ep['path']}:{ep['method']}": ep for ep in found_endpoints}
            results.extend(list(unique_eps.values()))

        return results

    def _is_interesting(self, path: str) -> bool:
        if not path or len(path) < 2:
            return False
        lower_path = path.lower()
        if any(prefix in lower_path for prefix in self.INTERESTING_PREFIXES):
            return True
        if ".php" in lower_path or ".jsp" in lower_path:
            return True
        return False


# ============================================
# JS MINER TOOL
# ============================================
class JsMinerTool:
    """Extracts JS files, API endpoints, and secrets from pages"""

    def run(self, urls: List[str]) -> List[Dict]:
        results = []

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

            # Extract endpoints
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

            # Literal API paths
            literal_pattern = r'["\'](/api/[a-zA-Z0-9/_\-]+|/v[0-9]+/[a-zA-Z0-9/_\-]+|/auth/[a-zA-Z0-9/_\-]+|/graphql[a-zA-Z0-9/_\-]*)["\']'
            for m in re.finditer(literal_pattern, html):
                endpoints.append({
                    "path": m.group(1),
                    "method": "UNKNOWN",
                    "source_js": "String Literal"
                })

            # Extract secrets (AWS keys)
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
                    "secrets": secrets
                }
            })

        return results

    def _is_interesting_path(self, path: str) -> bool:
        if not path or len(path) < 2:
            return False
        if " " in path:
            return False
        if path.endswith((".png", ".jpg", ".svg", ".css", ".js", ".woff")):
            return False
        return True


# ============================================
# ACTIVE RECON RUNNER
# ============================================
class ActiveReconRunner:
    """Orchestrates active reconnaissance phase"""

    def __init__(self, mission_id: str, target_domain: str, mode: str = "aggressive"):
        self.mission_id = mission_id
        self.target_domain = target_domain
        self.mode = mode
        self.httpx_tool = HttpxTool()
        self.wayback_tool = WaybackTool()
        self.html_crawler_tool = HtmlCrawlerTool()
        self.js_miner_tool = JsMinerTool()
        self.results = {
            "http_services": [],
            "endpoints": [],
            "js_files": [],
            "secrets": [],
            "errors": []
        }

    async def get_subdomains(self) -> List[str]:
        """Fetch subdomains from graph-service"""
        async with httpx_client.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    params={"mission_id": self.mission_id, "type": "SUBDOMAIN"}
                )
                if response.status_code == 200:
                    data = response.json()
                    nodes = data.get("nodes", [])
                    return [n.get("id") or n.get("properties", {}).get("name") for n in nodes if n]
            except Exception as e:
                logger.error("get_subdomains_failed", error=str(e))
        return []

    async def publish_node(self, node_type: str, node_id: str, properties: Dict) -> bool:
        """Publish a node to graph-service"""
        async with httpx_client.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{GRAPH_SERVICE}/api/v1/nodes",
                    json={
                        "id": node_id,
                        "type": node_type,
                        "mission_id": self.mission_id,
                        "properties": properties
                    }
                )
                return response.status_code in [200, 201]
            except Exception as e:
                logger.error("publish_node_failed", node_id=node_id, error=str(e))
                return False

    async def publish_edge(self, from_node: str, to_node: str, relation: str) -> bool:
        """Publish an edge to graph-service"""
        async with httpx_client.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{GRAPH_SERVICE}/api/v1/edges",
                    json={
                        "from_node": from_node,
                        "to_node": to_node,
                        "relation": relation,
                        "mission_id": self.mission_id,
                        "properties": {}
                    }
                )
                return response.status_code in [200, 201]
            except Exception as e:
                logger.error("publish_edge_failed", error=str(e))
                return False

    async def run(self) -> Dict:
        """Execute full active recon phase"""
        start_time = datetime.utcnow()

        # 1. Get discovered subdomains
        subdomains = await self.get_subdomains()
        if not subdomains:
            subdomains = [self.target_domain, f"www.{self.target_domain}"]

        logger.info("active_recon_subdomains", count=len(subdomains))

        # 2. HTTP Probing
        logger.info("httpx_probing_started", targets=len(subdomains))
        loop = asyncio.get_event_loop()
        httpx_result = await loop.run_in_executor(None, self.httpx_tool.run, subdomains)

        http_services = []
        for result in httpx_result.get("results", []):
            url = result.get("url")
            if url:
                http_services.append(url)
                subdomain = result.get("host") or urlparse(url).netloc

                # Publish HTTP_SERVICE node
                await self.publish_node(
                    "HTTP_SERVICE",
                    url,
                    {
                        "url": url,
                        "status_code": result.get("status_code"),
                        "title": result.get("title"),
                        "technologies": result.get("technologies", []),
                        "ip": result.get("ip"),
                        "discovered_at": datetime.utcnow().isoformat()
                    }
                )
                # Link subdomain -> HTTP_SERVICE
                await self.publish_edge(subdomain, url, "EXPOSES_HTTP")

        self.results["http_services"] = http_services
        logger.info("httpx_probing_completed", services=len(http_services))

        # 3. Wayback Machine
        logger.info("wayback_started", domains=[self.target_domain])
        wayback_results = await loop.run_in_executor(
            None, self.wayback_tool.run, [self.target_domain]
        )

        for endpoint in wayback_results:
            path = endpoint.get("path", "")
            method = endpoint.get("method", "GET")

            # Publish ENDPOINT node
            endpoint_id = f"endpoint:{path}"
            await self.publish_node(
                "ENDPOINT",
                endpoint_id,
                {
                    "path": path,
                    "method": method,
                    "source": "WAYBACK",
                    "confidence": 0.6,
                    "discovered_at": datetime.utcnow().isoformat()
                }
            )
            self.results["endpoints"].append(endpoint)

        logger.info("wayback_completed", endpoints=len(wayback_results))

        # 4. HTML Crawling (on confirmed HTTP services)
        if http_services:
            logger.info("html_crawling_started", targets=len(http_services[:15]))
            crawl_results = await loop.run_in_executor(
                None, self.html_crawler_tool.run, http_services[:15]
            )

            for endpoint in crawl_results:
                path = endpoint.get("path", "")
                origin = endpoint.get("origin", "")
                method = endpoint.get("method", "GET")

                endpoint_id = f"endpoint:{origin}{path}" if path.startswith("/") else f"endpoint:{path}"
                await self.publish_node(
                    "ENDPOINT",
                    endpoint_id,
                    {
                        "path": path,
                        "method": method,
                        "source": endpoint.get("source", "HTML"),
                        "origin": origin,
                        "confidence": 0.8,
                        "discovered_at": datetime.utcnow().isoformat()
                    }
                )

                # Link HTTP_SERVICE -> ENDPOINT
                if origin in http_services:
                    await self.publish_edge(origin, endpoint_id, "EXPOSES_ENDPOINT")

                self.results["endpoints"].append(endpoint)

            logger.info("html_crawling_completed", endpoints=len(crawl_results))

        # 5. JS Mining
        if http_services:
            logger.info("js_mining_started", targets=len(http_services[:10]))
            js_results = await loop.run_in_executor(
                None, self.js_miner_tool.run, http_services[:10]
            )

            for result in js_results:
                url = result.get("url", "")
                js_data = result.get("js", {})

                # JS Files
                for js_file in js_data.get("js_files", []):
                    js_id = f"js:{js_file}"
                    await self.publish_node(
                        "JS_FILE",
                        js_id,
                        {
                            "url": js_file,
                            "origin": url,
                            "discovered_at": datetime.utcnow().isoformat()
                        }
                    )
                    if url in http_services:
                        await self.publish_edge(url, js_id, "LOADS_JS")
                    self.results["js_files"].append(js_file)

                # JS Endpoints
                for ep in js_data.get("endpoints", []):
                    path = ep.get("path", "")
                    endpoint_id = f"endpoint:{url}{path}" if path.startswith("/") else f"endpoint:{path}"
                    await self.publish_node(
                        "ENDPOINT",
                        endpoint_id,
                        {
                            "path": path,
                            "method": ep.get("method", "GET"),
                            "source": "JS_MINER",
                            "origin": url,
                            "confidence": 0.7,
                            "discovered_at": datetime.utcnow().isoformat()
                        }
                    )
                    if url in http_services:
                        await self.publish_edge(url, endpoint_id, "EXPOSES_ENDPOINT")
                    self.results["endpoints"].append(ep)

                # Secrets
                for secret in js_data.get("secrets", []):
                    secret_id = f"secret:{secret.get('value', '')[:10]}"
                    await self.publish_node(
                        "SECRET",
                        secret_id,
                        {
                            "value": secret.get("value"),
                            "kind": secret.get("kind"),
                            "origin": url,
                            "discovered_at": datetime.utcnow().isoformat()
                        }
                    )
                    if url in http_services:
                        await self.publish_edge(url, secret_id, "LEAKS_SECRET")
                    self.results["secrets"].append(secret)

            logger.info("js_mining_completed",
                       js_files=len(self.results["js_files"]),
                       secrets=len(self.results["secrets"]))

        duration = (datetime.utcnow() - start_time).total_seconds()

        return {
            "phase": "active_recon",
            "status": "completed",
            "duration": duration,
            "results": {
                "http_services": len(self.results["http_services"]),
                "endpoints": len(self.results["endpoints"]),
                "js_files": len(self.results["js_files"]),
                "secrets": len(self.results["secrets"]),
                "errors": len(self.results["errors"])
            },
            "discovered": {
                "http_services": self.results["http_services"][:20],
                "endpoints": [e.get("path") for e in self.results["endpoints"][:20]],
                "js_files": self.results["js_files"][:10],
                "secrets_count": len(self.results["secrets"])
            }
        }


# ============================================
# API ENDPOINTS
# ============================================
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "active-recon", "version": "2.0.0"}


@app.get("/status")
async def status():
    return {
        "service": "active-recon",
        "httpx_available": shutil.which("httpx") is not None or shutil.which("docker") is not None,
        "graph_service": GRAPH_SERVICE
    }


@app.post("/api/v1/execute")
async def execute(request: ExecuteRequest):
    """Execute active recon - HTTP probing, crawling, JS analysis"""
    logger.info("active_recon_started",
                mission_id=request.mission_id,
                target=request.target_domain,
                mode=request.mode)

    runner = ActiveReconRunner(
        mission_id=request.mission_id,
        target_domain=request.target_domain,
        mode=request.mode
    )

    result = await runner.run()

    logger.info("active_recon_completed",
                mission_id=request.mission_id,
                http_services=result["results"]["http_services"],
                endpoints=result["results"]["endpoints"],
                duration=result["duration"])

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
