
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional
import json

class MyRobotsInput(BaseModel):
    base_url: str = Field(..., description="Base URL to check (e.g. 'https://example.com')")

class MyRobotsTool(BaseTool):
    name: str = "robots_check"
    description: str = "Fetches and analyzes robots.txt and checks for sitemap.xml."
    args_schema: Type[BaseModel] = MyRobotsInput

    def _run(self, base_url: str) -> str:
        base_url = base_url.rstrip("/")
        results = {
            "base_url": base_url,
            "robots_present": False,
            "sitemap_present": False,
            "disallow_count": 0,
            "sitemaps_found": [],
            "endpoints": []
        }

        # Check robots.txt
        try:
            robots_url = f"{base_url}/robots.txt"
            resp = requests.get(robots_url, timeout=5, verify=False)
            if resp.status_code == 200:
                results["robots_present"] = True
                content = resp.text
                
                for line in content.splitlines():
                    line = line.strip()
                    lower_line = line.lower()
                    
                    if lower_line.startswith("disallow:"):
                        results["disallow_count"] += 1
                        path = line.split(":", 1)[1].strip()
                        if path and path != "/":
                            results["endpoints"].append({
                                "path": path,
                                "method": "UNKNOWN", # Robots doesn't specify method
                                "source": "ROBOTS",
                                "origin": robots_url
                            })
                    
                    elif lower_line.startswith("sitemap:"):
                        results["sitemaps_found"].append(line.split(":", 1)[1].strip())
                        
        except Exception as e:
            pass

        # Check sitemap.xml
        try:
            sitemap_url = f"{base_url}/sitemap.xml"
            resp = requests.get(sitemap_url, timeout=5, verify=False)
            if resp.status_code == 200:
                results["sitemap_present"] = True
                if sitemap_url not in results["sitemaps_found"]:
                    results["sitemaps_found"].append(sitemap_url)
                
                # Bonus: Parse sitemap for endpoints if possible?
                import re
                locs = re.findall(r'<loc>(https?://[^<]+)</loc>', resp.text)
                for loc in locs:
                        # Filter for relevant paths?
                        if "/api/" in loc or "/wp-json/" in loc:
                            results["endpoints"].append({
                                "path": loc,
                                "method": "GET",
                                "source": "SITEMAP",
                                "origin": sitemap_url
                            })
        except Exception:
            pass
            
        return json.dumps(results, indent=2)
