"""
OSINT Runner - Phase 1 Passive Reconnaissance
Uses REAL tools: Subfinder (Docker), Wayback Machine, DNS
Matches CLI workflow exactly
"""
import os
import sys
import json
import yaml
import asyncio
import subprocess
import shutil
import tempfile
import time
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse
import httpx
import structlog

# Disable telemetry
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPTOUT"] = "true"

logger = structlog.get_logger()
app = FastAPI(title="OSINT Runner", version="2.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Service URLs
GRAPH_SERVICE = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:14b")


class ExecuteRequest(BaseModel):
    mission_id: str
    target_domain: str
    mode: str = "aggressive"
    options: Dict[str, Any] = {}


# ============================================
# SUBFINDER TOOL (matches CLI implementation)
# ============================================
class SubfinderTool:
    """Real subdomain enumeration using Subfinder binary or Docker"""

    def run(self, domain: str, recursive: bool = False, all_sources: bool = True, timeout: int = 120) -> Dict:
        logger.info("subfinder_starting", domain=domain, timeout=timeout)

        use_docker = False
        if not shutil.which("subfinder"):
            if shutil.which("docker"):
                use_docker = True
                logger.info("subfinder_using_docker")
            else:
                logger.warning("subfinder_not_available")
                return {"domain": domain, "count": 0, "subdomains": [], "error": "subfinder_not_found"}

        try:
            if use_docker:
                cmd = [
                    "docker", "run", "--rm",
                    "projectdiscovery/subfinder",
                    "-d", domain,
                    "-silent", "-oJ",
                    "-timeout", str(min(timeout, 60))
                ]
                if all_sources:
                    cmd.append("-all")
            else:
                cmd = [
                    "subfinder",
                    "-d", domain,
                    "-silent", "-oJ",
                    "-timeout", str(min(timeout, 60))
                ]
                if all_sources:
                    cmd.append("-all")
                if recursive:
                    cmd.append("-recursive")

            logger.info("subfinder_cmd", cmd=" ".join(cmd))
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            subdomains = []
            if proc.stdout:
                for line in proc.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        host = data.get("host", "")
                        if host and domain in host:
                            subdomains.append(host)
                    except json.JSONDecodeError:
                        # Plain text output
                        if domain in line:
                            subdomains.append(line.strip())

            # Deduplicate
            subdomains = list(set(subdomains))
            logger.info("subfinder_completed", domain=domain, count=len(subdomains))

            return {
                "domain": domain,
                "count": len(subdomains),
                "subdomains": subdomains
            }

        except subprocess.TimeoutExpired:
            logger.error("subfinder_timeout", domain=domain, timeout=timeout)
            return {"domain": domain, "count": 0, "subdomains": [], "error": "timeout"}
        except Exception as e:
            logger.error("subfinder_error", error=str(e))
            return {"domain": domain, "count": 0, "subdomains": [], "error": str(e)}


# ============================================
# WAYBACK TOOL (matches CLI implementation)
# ============================================
class WaybackTool:
    """Queries Wayback Machine for historical URLs"""

    INTERESTING_EXTENSIONS = [".php", ".asp", ".aspx", ".jsp", ".json", ".xml", ".txt"]
    INTERESTING_KEYWORDS = ["/api/", "/admin/", "/graphql", "/wp-json/", "/auth/", "/v1/", "/v2/", "/login", "/user"]
    IGNORED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".svg", ".woff", ".woff2", ".ttf", ".ico", ".mp4", ".mp3"]

    def run(self, domains: List[str], limit: int = 3000) -> List[Dict]:
        logger.info("wayback_starting", domains=domains, limit=limit)
        results = []

        for domain in domains:
            if not domain:
                continue

            # Query Wayback CDX API
            api_url = f"http://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=json&fl=original&collapse=urlkey&limit={limit}"

            try:
                time.sleep(1)  # Rate limiting
                resp = requests.get(api_url, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    # Skip header row
                    if data and data[0][0] == "original":
                        data = data[1:]

                    found_urls = set()

                    for row in data:
                        raw_url = row[0]
                        lower_url = raw_url.lower()

                        # Skip ignored extensions
                        if any(lower_url.endswith(ext) for ext in self.IGNORED_EXTENSIONS):
                            continue

                        # Check if interesting
                        is_interesting = (
                            any(ext in lower_url for ext in self.INTERESTING_EXTENSIONS) or
                            any(kw in lower_url for kw in self.INTERESTING_KEYWORDS)
                        )

                        if is_interesting:
                            base_path = raw_url.split("?")[0] if "?" in raw_url else raw_url
                            found_urls.add((raw_url, base_path))

                    # Deduplicate by base path
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

                    logger.info("wayback_domain_completed", domain=domain, endpoints=len(seen_paths))

            except Exception as e:
                logger.warning("wayback_error", domain=domain, error=str(e))
                continue

        logger.info("wayback_completed", total_endpoints=len(results))
        return results


# ============================================
# OSINT RUNNER (matches CLI workflow)
# ============================================
class OsintRunner:
    """OSINT Runner with real tool integration - matches CLI workflow"""

    def __init__(self, target_domain: str, mission_id: str, mode: str = "aggressive"):
        self.target_domain = target_domain
        self.mission_id = mission_id
        self.mode = mode
        self.subfinder_tool = SubfinderTool()
        self.wayback_tool = WaybackTool()
        self.results = {
            "subdomains": [],
            "endpoints": [],
            "dns_records": [],
            "errors": []
        }

    async def publish_node(self, node_type: str, node_id: str, properties: Dict) -> bool:
        """Publish a node to graph-service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        """Execute OSINT phase - matches CLI workflow"""
        start_time = datetime.utcnow()
        loop = asyncio.get_event_loop()

        # ========================================
        # STEP 1: Create root domain node
        # ========================================
        await self.publish_node(
            "DOMAIN",
            self.target_domain,
            {"name": self.target_domain, "source": "seed", "mission_id": self.mission_id}
        )
        logger.info("domain_node_created", domain=self.target_domain)

        # ========================================
        # STEP 2: Subfinder Direct Bypass (matches CLI)
        # ========================================
        logger.info("phase_subfinder_starting", domain=self.target_domain)
        subfinder_result = await loop.run_in_executor(
            None,
            lambda: self.subfinder_tool.run(
                domain=self.target_domain,
                recursive=False,
                all_sources=True,
                timeout=120
            )
        )

        subdomains = subfinder_result.get("subdomains", [])
        if subfinder_result.get("error"):
            self.results["errors"].append(f"subfinder: {subfinder_result['error']}")

        # Publish discovered subdomains
        for subdomain in subdomains:
            if self.target_domain not in subdomain:
                logger.warning("rejected_out_of_scope", subdomain=subdomain)
                continue

            await self.publish_node(
                "SUBDOMAIN",
                subdomain,
                {
                    "name": subdomain,
                    "priority": 5,
                    "tag": "SUBFINDER_DIRECT",
                    "category": "RECON",
                    "source": "subfinder",
                    "discovered_at": datetime.utcnow().isoformat()
                }
            )
            await self.publish_edge(self.target_domain, subdomain, "HAS_SUBDOMAIN")
            self.results["subdomains"].append(subdomain)

        logger.info("phase_subfinder_completed", count=len(self.results["subdomains"]))

        # ========================================
        # STEP 3: Wayback Historical Scan (matches CLI)
        # ========================================
        logger.info("phase_wayback_starting")

        # Query Wayback for all discovered subdomains + apex
        wayback_domains = list(set(self.results["subdomains"] + [self.target_domain]))

        wayback_results = await loop.run_in_executor(
            None,
            lambda: self.wayback_tool.run(wayback_domains)
        )

        # Publish discovered endpoints
        for endpoint in wayback_results:
            path = endpoint.get("path", "")

            # Scope check
            try:
                parsed = urlparse(path)
                if parsed.netloc and self.target_domain not in parsed.netloc:
                    continue
            except:
                pass

            endpoint_id = f"endpoint:{path}"
            await self.publish_node(
                "ENDPOINT",
                endpoint_id,
                {
                    "path": path,
                    "method": endpoint.get("method", "GET"),
                    "source": "WAYBACK",
                    "origin": endpoint.get("origin", ""),
                    "confidence": 0.6,
                    "discovered_at": datetime.utcnow().isoformat()
                }
            )
            self.results["endpoints"].append(endpoint)

        logger.info("phase_wayback_completed", endpoints=len(wayback_results))

        # ========================================
        # STEP 4: Safety Net - Apex Fallback (matches CLI)
        # ========================================
        if len(self.results["subdomains"]) == 0:
            logger.warning("safety_net_triggered", reason="zero_subdomains")

            # Inject apex domain
            await self.publish_node(
                "SUBDOMAIN",
                self.target_domain,
                {
                    "name": self.target_domain,
                    "priority": 10,
                    "tag": "APEX_FALLBACK",
                    "category": "RECON",
                    "source": "safety_net",
                    "discovered_at": datetime.utcnow().isoformat()
                }
            )
            await self.publish_edge(self.target_domain, self.target_domain, "HAS_SUBDOMAIN")
            self.results["subdomains"].append(self.target_domain)

            # Inject www subdomain
            www_domain = f"www.{self.target_domain}"
            await self.publish_node(
                "SUBDOMAIN",
                www_domain,
                {
                    "name": www_domain,
                    "priority": 10,
                    "tag": "APEX_FALLBACK",
                    "category": "RECON",
                    "source": "safety_net",
                    "discovered_at": datetime.utcnow().isoformat()
                }
            )
            await self.publish_edge(self.target_domain, www_domain, "HAS_SUBDOMAIN")
            self.results["subdomains"].append(www_domain)

            logger.info("safety_net_injected", subdomains=[self.target_domain, www_domain])

        duration = (datetime.utcnow() - start_time).total_seconds()

        return {
            "phase": "osint",
            "status": "completed",
            "duration": duration,
            "tools_used": ["subfinder", "wayback"],
            "results": {
                "subdomains": len(self.results["subdomains"]),
                "endpoints": len(self.results["endpoints"]),
                "dns_records": len(self.results["dns_records"]),
                "errors": len(self.results["errors"])
            },
            "discovered": {
                "subdomains": self.results["subdomains"][:50],
                "endpoints": [e.get("path") for e in self.results["endpoints"][:30]]
            },
            "errors": self.results["errors"]
        }


@app.get("/health")
async def health():
    """Health check endpoint"""
    subfinder_available = shutil.which("subfinder") is not None or shutil.which("docker") is not None
    return {
        "status": "healthy",
        "service": "osint-runner",
        "version": "2.1.0",
        "tools": {
            "subfinder": subfinder_available,
            "wayback": True
        },
        "graph_service": GRAPH_SERVICE
    }


@app.get("/status")
async def status():
    """Detailed status check"""
    return {
        "service": "osint-runner",
        "version": "2.1.0",
        "subfinder_available": shutil.which("subfinder") is not None,
        "docker_available": shutil.which("docker") is not None,
        "graph_service": GRAPH_SERVICE,
        "ollama_url": OLLAMA_URL,
        "model": MODEL_NAME
    }


@app.post("/api/v1/execute")
async def execute(request: ExecuteRequest):
    """Execute OSINT phase with real tools"""
    logger.info("osint_execute_started",
                mission_id=request.mission_id,
                target=request.target_domain,
                mode=request.mode)

    runner = OsintRunner(
        target_domain=request.target_domain,
        mission_id=request.mission_id,
        mode=request.mode
    )

    result = await runner.run()

    logger.info("osint_execute_completed",
                mission_id=request.mission_id,
                subdomains=result["results"]["subdomains"],
                endpoints=result["results"]["endpoints"],
                duration=result["duration"])

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
