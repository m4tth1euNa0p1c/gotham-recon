"""
HTML Crawler tool for CrewAI agents.
Extracts endpoints from HTML pages (forms, links, etc.).
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


class HtmlCrawlerInput(BaseModel):
    """Schema for HtmlCrawlerTool arguments."""
    urls: List[str] = Field(..., description="List of URLs to crawl for endpoints.")


class HtmlCrawlerTool(BaseTool):
    """Crawls HTML pages to extract endpoints from forms and links."""
    name: str = "html_crawler"
    description: str = (
        "Crawls a list of URLs to extract interesting endpoints (href, form actions). "
        "Returns a strict JSON list of discovered endpoints."
    )
    args_schema: Type[BaseModel] = HtmlCrawlerInput

    def _run(self, urls: List[str]) -> str:
        """Crawl URLs for endpoints."""
        results = []

        if isinstance(urls, str):
            try:
                urls = json.loads(urls)
            except:
                urls = [urls]

        INTERESTING_PREFIXES = ["/api", "/auth", "/admin", "/backend", "/graphql", "/ajax", "/v1", "/v2"]

        for url in urls:
            if not url or not url.startswith("http"):
                continue

            try:
                resp = requests.get(url, timeout=10, verify=False)
                html = resp.text
            except Exception:
                continue

            found_endpoints = []

            # Extract forms
            form_matches = re.finditer(r'<form\s+([^>]+)>', html, re.IGNORECASE)
            for fm in form_matches:
                attrs = fm.group(1)
                action_match = re.search(r'action=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
                action = action_match.group(1) if action_match else ""
                method_match = re.search(r'method=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
                method = method_match.group(1).upper() if method_match else "GET"

                if action and self._is_interesting(action, INTERESTING_PREFIXES):
                    found_endpoints.append({
                        "path": action,
                        "method": method,
                        "source": "HTML_FORM",
                        "origin": url
                    })

            # Extract links
            link_matches = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', html, re.IGNORECASE)
            for link in link_matches:
                if self._is_interesting(link, INTERESTING_PREFIXES):
                    found_endpoints.append({
                        "path": link,
                        "method": "GET",
                        "source": "HTML_LINK",
                        "origin": url
                    })

            if found_endpoints:
                unique_eps = {f"{ep['path']}:{ep['method']}": ep for ep in found_endpoints}.values()
                results.extend(list(unique_eps))

        return json.dumps(results, indent=2)

    def _is_interesting(self, path: str, prefixes: List[str]) -> bool:
        """Filter paths to keep only relevant ones."""
        if not path or len(path) < 2:
            return False
        lower_path = path.lower()
        if any(prefix in lower_path for prefix in prefixes):
            return True
        if ".php" in lower_path or ".jsp" in lower_path:
            return True
        return False
