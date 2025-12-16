from __future__ import annotations
import json
import re
import requests
from typing import List, Dict, Type
from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass

class HtmlCrawlerInput(BaseModel):
    """Schema for HtmlCrawlerTool arguments."""
    urls: List[str] = Field(
        ..., description="List of URLs to crawl for endpoints."
    )

class HtmlCrawlerTool(BaseTool):
    """
    Crawls HTML pages to extract endpoints from href, action, src attributes.
    Focuses on API, Auth, Admin, and Backend paths.
    """
    name: str = "html_crawler"
    description: str = (
        "Crawls a list of URLs to extract interesting endpoints (href, form actions). "
        "Returns a strict JSON list of discovered endpoints."
    )
    args_schema: Type[BaseModel] = HtmlCrawlerInput

    def _run(self, urls: List[str]) -> str:
        results = []
        
        # Ensure list
        if isinstance(urls, str):
            try:
                urls = json.loads(urls)
            except:
                urls = [urls]

        # Targets of interest
        INTERESTING_PREFIXES = ["/api", "/auth", "/admin", "/backend", "/graphql", "/ajax", "/v1", "/v2"]

        for url in urls:
            if not url or not url.startswith("http"):
                continue

            try:
                resp = requests.get(url, timeout=10, verify=False)
                html = resp.text
            except Exception as e:
                # Log error but continue
                continue

            found_endpoints = []

            # 1. Forms (Action + Method)
            # Regex to find <form ... action="..." ... method="...">
            # This is tricky with regex, simpler to find tags then attrs
            
            # Find all form tags roughly
            form_matches = re.finditer(r'<form\s+([^>]+)>', html, re.IGNORECASE)
            for fm in form_matches:
                attrs = fm.group(1)
                
                # Extract Action
                action_match = re.search(r'action=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
                action = action_match.group(1) if action_match else ""
                
                # Extract Method
                method_match = re.search(r'method=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
                method = method_match.group(1).upper() if method_match else "GET" # Default to GET if unspecified, or UNKNOWN? HTML default is GET.
                
                if action and self._is_interesting(action, INTERESTING_PREFIXES):
                    found_endpoints.append({
                        "path": action,
                        "method": method,
                        "source": "HTML_FORM",
                        "origin": url
                    })

            # 2. General Links (href, src) - Usually GET
            # Combine regex for href and src
            link_matches = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', html, re.IGNORECASE)
            for link in link_matches:
                if self._is_interesting(link, INTERESTING_PREFIXES):
                    found_endpoints.append({
                        "path": link,
                        "method": "GET",
                        "source": "HTML_LINK",
                        "origin": url
                    })

            # Add to results
            if found_endpoints:
                # Deduplicate
                unique_eps = {f"{ep['path']}:{ep['method']}": ep for ep in found_endpoints}.values()
                results.extend(list(unique_eps))

        return json.dumps(results, indent=2)

    def _is_interesting(self, path: str, prefixes: List[str]) -> bool:
        """Filter paths to keep only relevant ones."""
        if not path or len(path) < 2: return False
        
        # Normalize for check
        # Handle absolute URLs if they match target domain? 
        # For simplicity, we focus on paths. If strictly absolute "https://other.com/api", we might want it if same scope.
        # Let's assume the graph logic handles scope, here we extract everything interesting.
        
        # Check specific prefixes
        # Or checking if it contains keywords?
        # User said: "Garder uniquement les chemins pertinents : /api/..., /admin/..., etc."
        
        lower_path = path.lower()
        if any(prefix in lower_path for prefix in prefixes):
            return True
        
        # Also maybe file extensions? .php usually interesting
        if ".php" in lower_path or ".jsp" in lower_path:
             return True
             
        return False
