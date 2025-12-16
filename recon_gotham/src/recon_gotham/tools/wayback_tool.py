from __future__ import annotations
import json
import requests
import time
from typing import List, Type
from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool:
        pass

class WaybackInput(BaseModel):
    """Schema for WaybackTool arguments."""
    domains: List[str] = Field(
        ..., description="List of domains to search in Wayback Machine (e.g. ['target.com'])."
    )

class WaybackTool(BaseTool):
    """
    Queries Wayback Machine CDX API for historical URLs matching specific patterns (API, Admin, PHP, etc.).
    """
    name: str = "wayback_history"
    description: str = (
        "Queries Wayback Machine for historical endpoints on a domain. "
        "Filters for interesting paths (API, Admin, PHP, Graphql). "
        "Returns a strict JSON list."
    )
    args_schema: Type[BaseModel] = WaybackInput

    def _run(self, domains: List[str]) -> str:
        results = []
        
        if isinstance(domains, str):
            try:
                domains = json.loads(domains)
            except:
                domains = [domains]

        # Filters
        INTERESTING_EXTENSIONS = [".php", ".asp", ".aspx", ".jsp", ".json", ".xml"]
        INTERESTING_KEYWORDS = ["/api/", "/admin/", "/graphql", "/wp-json/", "/auth/", "/v1/", "/v2/"]
        IGNORED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".svg", ".woff", ".ttf", ".ico"]

        for domain in domains:
            if not domain: continue
            
            # Use CDX API
            # url = *.domain/* to get subdomains too? 
            # Or just domain/*
            # Let's try to get everything for the domain scope
            api_url = f"http://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=json&fl=original&collapse=urlkey&limit=3000"
            
            try:
                # Add a pause to be polite
                time.sleep(1)
                resp = requests.get(api_url, timeout=20)
                
                if resp.status_code == 200:
                    data = resp.json()
                    # format: [["original"], ["http://..."], ...]
                    # Skip header row if present
                    if data and data[0][0] == "original":
                        data = data[1:]
                    
                    found_urls = set()
                    
                    for row in data:
                        raw_url = row[0]
                        lower_url = raw_url.lower()
                        
                        # 1. Extension Filter
                        if any(lower_url.endswith(ext) for ext in IGNORED_EXTENSIONS):
                            continue
                            
                        # 2. Interest Check
                        is_interesting = False
                        
                        # Check extensions
                        if any(ext in lower_url for ext in INTERESTING_EXTENSIONS):
                            is_interesting = True
                        # Check keywords
                        elif any(kw in lower_url for kw in INTERESTING_KEYWORDS):
                            is_interesting = True
                            
                        if is_interesting:
                            # Normalize: Path without query for deduplication?
                            # User said "Deduplicate par path sans query". 
                            # But we want to return the raw endpoint.
                            # Let's store the full URL, but check uniqueness by path.
                            
                            # Extract path
                            # Simple heuristic
                            if "?" in raw_url:
                                base_path = raw_url.split("?")[0]
                            else:
                                base_path = raw_url
                                
                            found_urls.add((raw_url, base_path))
                            
                    # Post-process unique paths
                    seen_paths = set()
                    for full_url, base_path in found_urls:
                        if base_path in seen_paths:
                            continue
                        seen_paths.add(base_path)
                        
                        results.append({
                            "path": full_url, # Return full URL as 'path' for the tool output, normalization happens in graph
                            "method": "GET", # Archive is usually GET
                            "source": "WAYBACK",
                            "origin": "archive.org"
                        })

            except Exception as e:
                # Network error or timeout
                continue

        return json.dumps(results, indent=2)
