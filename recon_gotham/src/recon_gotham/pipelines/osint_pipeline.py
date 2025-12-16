"""
OSINT Pipeline - Passive Discovery Phase
Orchestrates passive reconnaissance: Subfinder, DNS, Wayback, JS Mining (passive)
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass

from crewai import Agent, Task, Crew

from recon_gotham.core.asset_graph import AssetGraph


@dataclass
class OsintPipelineResult:
    """Result of OSINT pipeline execution."""
    subdomains_found: int
    dns_records_found: int
    wayback_endpoints: int
    js_endpoints: int
    errors: List[str]


class OsintPipeline:
    """
    OSINT Pipeline - Passive Discovery.
    
    Orchestrates:
    - Subfinder (subdomain enumeration)
    - DNS Resolution
    - Wayback Machine (historical endpoints)
    - JS Mining (passive, from CDN/archives)
    """
    
    def __init__(self, graph: AssetGraph, settings: Dict, run_id: str):
        self.graph = graph
        self.settings = settings
        self.run_id = run_id
        self.target_domain = settings.get("target_domain")
        self.mode = settings.get("mode", "AGGRESSIVE")
    
    def execute(self, agents: Dict[str, Agent], tasks: Dict[str, Task]) -> OsintPipelineResult:
        """
        Execute the OSINT pipeline.
        
        Args:
            agents: Dictionary of configured CrewAI agents
            tasks: Dictionary of configured CrewAI tasks
            
        Returns:
            OsintPipelineResult with statistics
        """
        errors = []
        
        # Select relevant agents and tasks for passive phase
        passive_agents = [
            agents.get("pathfinder"),
            agents.get("watchtower"),
        ]
        
        passive_tasks = [
            tasks.get("subdomain_discovery_task"),
            tasks.get("dns_context_task"),
        ]
        
        # Filter None values
        passive_agents = [a for a in passive_agents if a is not None]
        passive_tasks = [t for t in passive_tasks if t is not None]
        
        if not passive_agents or not passive_tasks:
            errors.append("Missing required agents or tasks for OSINT pipeline")
            return OsintPipelineResult(0, 0, 0, 0, errors)
        
        # Create and execute crew
        try:
            crew = Crew(
                agents=passive_agents,
                tasks=passive_tasks,
                verbose=True
            )
            result = crew.kickoff()
            
            # Process results
            stats = self._ingest_results(result)
            
            return OsintPipelineResult(
                subdomains_found=stats.get("subdomains", 0),
                dns_records_found=stats.get("dns_records", 0),
                wayback_endpoints=stats.get("wayback", 0),
                js_endpoints=stats.get("js", 0),
                errors=errors
            )
            
        except Exception as e:
            errors.append(f"OSINT Pipeline error: {str(e)}")
            return OsintPipelineResult(0, 0, 0, 0, errors)
    
    def _ingest_results(self, crew_result) -> Dict:
        """Ingest crew results into the AssetGraph."""
        stats = {"subdomains": 0, "dns_records": 0, "wayback": 0, "js": 0}
        
        # Process task outputs
        for task_output in crew_result.tasks_output if hasattr(crew_result, 'tasks_output') else []:
            try:
                raw = task_output.raw if hasattr(task_output, 'raw') else str(task_output)
                
                # Try to extract JSON
                json_match = self._extract_json(raw)
                if json_match:
                    data = json.loads(json_match)
                    
                    # Process subdomains
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, str) and self.target_domain in item:
                                self.graph.add_subdomain(item, source="OSINT_PIPELINE")
                                stats["subdomains"] += 1
                            elif isinstance(item, dict):
                                host = item.get("host") or item.get("subdomain")
                                if host and self.target_domain in host:
                                    self.graph.add_subdomain(host, source="OSINT_PIPELINE")
                                    stats["subdomains"] += 1
            except Exception:
                continue
        
        return stats
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text."""
        import re
        
        # Try to find JSON array
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            return match.group(0)
        
        # Try to find JSON object
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)
        
        return None
    
    def run_wayback(self, hosts: List[str]) -> int:
        """
        Run Wayback Machine historical scan.
        
        Args:
            hosts: List of hosts to query
            
        Returns:
            Number of endpoints found
        """
        from recon_gotham.tools.wayback_tool import WaybackTool
        
        wayback_tool = WaybackTool()
        count = 0
        
        try:
            result = wayback_tool._run(hosts=hosts)
            data = json.loads(result)
            
            if isinstance(data, list):
                for url in data:
                    if self.target_domain in url:
                        self.graph.add_endpoint(
                            path=self._extract_path(url),
                            method="GET",
                            source="WAYBACK",
                            origin=url,
                            confidence=0.6
                        )
                        count += 1
        except Exception:
            pass
        
        return count
    
    def _extract_path(self, url: str) -> str:
        """Extract path from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.path or "/"
