"""
Recon Pipeline - Active Reconnaissance Phase
Orchestrates active probing: HTTPX, HTML Crawling, JS Mining (active)
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass

from recon_gotham.core.asset_graph import AssetGraph


@dataclass
class ReconPipelineResult:
    """Result of Recon pipeline execution."""
    http_services_found: int
    endpoints_crawled: int
    js_endpoints: int
    technologies_detected: List[str]
    errors: List[str]


class ReconPipeline:
    """
    Recon Pipeline - Active Reconnaissance.
    
    Orchestrates:
    - HTTPX probing (HTTP service detection)
    - HTML Crawling (link extraction)
    - JS Mining (active, from live pages)
    - Technology fingerprinting
    """
    
    def __init__(self, graph: AssetGraph, settings: Dict, run_id: str):
        self.graph = graph
        self.settings = settings
        self.run_id = run_id
        self.target_domain = settings.get("target_domain")
        self.mode = settings.get("mode", "AGGRESSIVE")
        self.max_workers = settings.get("http_max_workers", 5)
    
    def execute(self, subdomains: List[str]) -> ReconPipelineResult:
        """
        Execute the Recon pipeline on discovered subdomains.
        
        Args:
            subdomains: List of subdomains to probe
            
        Returns:
            ReconPipelineResult with statistics
        """
        errors = []
        http_services = 0
        endpoints = 0
        js_eps = 0
        technologies = set()
        
        # Step 1: HTTPX Probing
        scan_urls = self._httpx_probe(subdomains)
        http_services = len(scan_urls)
        
        # Step 2: HTML Crawling on live services
        for url in scan_urls[:self.settings.get("max_targets", 20)]:
            try:
                crawl_count = self._crawl_url(url)
                endpoints += crawl_count
            except Exception as e:
                errors.append(f"Crawl error on {url}: {str(e)[:100]}")
        
        # Step 3: JS Mining on live services
        for url in scan_urls[:10]:  # Limit JS mining
            try:
                js_count = self._mine_js(url)
                js_eps += js_count
            except Exception as e:
                errors.append(f"JS mining error on {url}: {str(e)[:100]}")
        
        # Collect technologies from graph
        for node in self.graph.nodes:
            if node.get("type") == "HTTP_SERVICE":
                techs = node.get("properties", {}).get("technologies", [])
                if isinstance(techs, list):
                    technologies.update(techs)
        
        return ReconPipelineResult(
            http_services_found=http_services,
            endpoints_crawled=endpoints,
            js_endpoints=js_eps,
            technologies_detected=list(technologies),
            errors=errors
        )
    
    def _httpx_probe(self, subdomains: List[str]) -> List[str]:
        """
        Probe subdomains with HTTPX.
        
        Returns:
            List of live HTTP service URLs
        """
        from recon_gotham.tools.httpx_tool import HttpxTool
        
        live_urls = []
        httpx_tool = HttpxTool()
        
        # Build URL list (https and http)
        urls_to_probe = []
        for sub in subdomains:
            if self.target_domain in sub:
                urls_to_probe.append(f"https://{sub}")
                urls_to_probe.append(f"http://{sub}")
        
        try:
            result = httpx_tool._run(urls=urls_to_probe)
            data = json.loads(self._extract_json(result) or "[]")
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        url = item.get("url")
                        if url and self.target_domain in url:
                            live_urls.append(url)
                            
                            # Add to graph
                            self.graph.add_subdomain_with_http(
                                subdomain_name=self._extract_host(url),
                                http_data={
                                    "url": url,
                                    "status_code": item.get("status_code"),
                                    "title": item.get("title"),
                                    "technologies": item.get("tech", []),
                                    "ip": item.get("ip")
                                }
                            )
        except Exception:
            pass
        
        return list(set(live_urls))
    
    def _crawl_url(self, url: str) -> int:
        """Crawl a URL for links."""
        from recon_gotham.tools.html_crawler_tool import HtmlCrawlerTool
        
        crawler = HtmlCrawlerTool()
        count = 0
        
        try:
            result = crawler._run(url=url)
            links = json.loads(self._extract_json(result) or "[]")
            
            for link in links:
                if self.target_domain in link:
                    self.graph.add_endpoint(
                        path=self._extract_path(link),
                        method="GET",
                        source="CRAWLER",
                        origin=link,
                        confidence=0.9
                    )
                    count += 1
        except Exception:
            pass
        
        return count
    
    def _mine_js(self, url: str) -> int:
        """Mine JavaScript for endpoints."""
        from recon_gotham.tools.js_miner_tool import JsMinerTool
        
        miner = JsMinerTool()
        count = 0
        
        try:
            result = miner._run(url=url)
            data = json.loads(self._extract_json(result) or "[]")
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        endpoint = item.get("match") or item.get("endpoint")
                        if endpoint and endpoint.startswith("/"):
                            self.graph.add_endpoint(
                                path=endpoint,
                                method="GET",
                                source="JS_MINER",
                                origin=url + endpoint,
                                confidence=0.7
                            )
                            count += 1
        except Exception:
            pass
        
        return count
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text."""
        import re
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            return match.group(0)
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)
        return None
    
    def _extract_host(self, url: str) -> str:
        """Extract hostname from URL."""
        from urllib.parse import urlparse
        return urlparse(url).netloc
    
    def _extract_path(self, url: str) -> str:
        """Extract path from URL."""
        from urllib.parse import urlparse
        return urlparse(url).path or "/"
