"""
CrewAI Mission Runner - V2.0
Implements the same hybrid approach as the original recon_gotham/main.py:
1. Direct tool calls for reliable data collection (Subfinder, Wayback, HTTPX)
2. LLM agents for analysis and enrichment
3. Proper ingestion into graph-service
"""
import asyncio
import json
import time
import re
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from crewai import Crew, Process

from .agent_factory import (
    build_pathfinder,
    build_watchtower,
    build_dns_analyst,
    build_tech_fingerprinter,
    build_js_miner,
    build_endpoint_intel,
    build_planner,
    # Deep Verification Agents (Lot 2.2)
    build_vuln_triage,
    build_stack_policy,
    build_validation_planner,
    build_evidence_curator,
)
from .task_factory import (
    build_enumeration_task,
    build_analysis_task,
    build_dns_task,
    build_fingerprint_task,
    build_js_mining_task,
    build_endpoint_intel_task,
    build_planning_task,
    # Deep Verification Tasks (Lot 2.2)
    build_vuln_triage_task,
    build_stack_policy_task,
    build_validation_plan_task,
    build_evidence_curation_task,
)
from .events import (
    emit_agent_started,
    emit_agent_finished,
    emit_phase_started,
    emit_phase_completed,
    emit_mission_status,
    emit_log,
    emit_node_added,
    emit_nodes_batch,
    emit_llm_call,
    emit_tool_called,
    emit_tool_result,
)
from .llm_client import get_llm_client
from .graph_client import GraphClient, publish_discovered_assets

# Import CrewAI tools
from tools import (
    SubfinderTool,
    HttpxTool,
    DnsResolverTool,
    WaybackTool,
    JsMinerTool,
    HtmlCrawlerTool,
    ASNLookupTool,
    get_tools_for_agent,
    # Deep Verification Tools (Lot 2.3)
    GraphQueryTool,
    CheckRunnerTool,
    BatchCheckRunnerTool,
    GraphUpdaterTool,
    BulkGraphUpdaterTool,
)

# P0.6: Import reflection module for result validation and enrichment
try:
    from .reflection import reflect_and_enrich, ReflectionLoop, ScriptGenerator
    REFLECTION_AVAILABLE = True
except ImportError:
    REFLECTION_AVAILABLE = False

# P0.6: Import PythonScriptExecutorTool for running generated scripts
try:
    from tools.python_script_executor_tool import PythonScriptExecutorTool
    SCRIPT_EXECUTOR_AVAILABLE = True
except ImportError:
    SCRIPT_EXECUTOR_AVAILABLE = False


def extract_json(text: str) -> str:
    """Extract JSON from text that may contain markdown or other content"""
    if not text:
        return "{}"
    text = str(text).strip()

    # Remove markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find JSON boundaries
    first_open_sq = text.find('[')
    last_close_sq = text.rfind(']')
    first_open_cur = text.find('{')
    last_close_cur = text.rfind('}')

    extracted = text
    if first_open_sq != -1 and (first_open_cur == -1 or first_open_sq < first_open_cur):
        if last_close_sq != -1:
            extracted = text[first_open_sq:last_close_sq+1]
    elif first_open_cur != -1:
        if last_close_cur != -1:
            extracted = text[first_open_cur:last_close_cur+1]

    return extracted


class CrewMissionRunner:
    """
    Runs CrewAI reconnaissance missions with the SAME logic as original recon_gotham.
    Key difference: Uses direct tool calls + LLM analysis (hybrid approach)
    """

    def __init__(self, mission_id: str, target_domain: str, mode: str = "aggressive"):
        self.mission_id = mission_id
        self.target_domain = target_domain
        self.mode = mode
        self.llm_client = get_llm_client()
        self.results: Dict[str, Any] = {}
        self.start_time = 0

        # Initialize GraphClient for publishing to graph-service
        self.graph_client = GraphClient(mission_id, target_domain)

        # Collected data (like AssetGraph in original)
        self.subdomains: List[str] = []
        self.http_services: List[Dict] = []
        self.endpoints: List[Dict] = []
        self.dns_records: List[Dict] = []
        self.js_intel: List[Dict] = []

        # Instantiate all tools once
        self.tools = {
            "subfinder": SubfinderTool(),
            "httpx": HttpxTool(),
            "dns_resolver": DnsResolverTool(),
            "wayback": WaybackTool(),
            "js_miner": JsMinerTool(),
            "html_crawler": HtmlCrawlerTool(),
            "asn_lookup": ASNLookupTool(),
            # Deep Verification Tools (Lot 2.3)
            "graph_query": GraphQueryTool(),
            "check_runner": CheckRunnerTool(),
            "batch_check_runner": BatchCheckRunnerTool(),
            "graph_updater": GraphUpdaterTool(),
            "bulk_graph_updater": BulkGraphUpdaterTool(),
        }

        # Verification-specific data
        self.verification_results: List[Dict] = []
        self.check_results: List[Dict] = []

        # P0.6: Initialize script executor for reflection-generated scripts
        self.script_executor = None
        if SCRIPT_EXECUTOR_AVAILABLE:
            self.script_executor = PythonScriptExecutorTool()
            emit_log(self.mission_id, "INFO", "PythonScriptExecutorTool available for reflection scripts", "init")

        # P0.6: Reflection metrics
        self.reflection_stats = {
            "reflections_run": 0,
            "scripts_executed": 0,
            "enrichments_added": 0,
            "issues_found": 0
        }

        emit_log(self.mission_id, "INFO", f"CrewAI Mission Runner V2.1 initialized for {target_domain}", "init")
        emit_log(self.mission_id, "INFO", f"Tools available: {list(self.tools.keys())}", "init")
        emit_log(self.mission_id, "INFO", f"Reflection enabled: {REFLECTION_AVAILABLE}", "init")

    def check_llm_available(self) -> bool:
        """Check if LLM is available"""
        available = self.llm_client.is_available()
        if not available:
            emit_log(self.mission_id, "WARNING", "LLM not available - will use tool-only mode", "init")
        else:
            emit_log(self.mission_id, "INFO", f"LLM available: {self.llm_client.model_name}", "init")
        return available

    async def run_reflection(self, tool_name: str, result: Any, context: Optional[Dict] = None) -> Dict:
        """
        P0.6: Run reflection on tool results to validate and enrich.

        Args:
            tool_name: Name of the tool that produced the result
            result: The tool's output
            context: Additional context for analysis

        Returns:
            Reflection summary with findings and enrichments
        """
        if not REFLECTION_AVAILABLE:
            return {"skipped": True, "reason": "Reflection module not available"}

        emit_log(self.mission_id, "INFO", f"Running reflection on {tool_name} results...", "reflection")
        emit_agent_started(self.mission_id, "reflector", f"Analyzing {tool_name} results")

        try:
            # Build context with target domain
            full_context = {"target_domain": self.target_domain}
            if context:
                full_context.update(context)

            # Run reflection
            reflection_result = await reflect_and_enrich(
                tool_name=tool_name,
                result=result,
                mission_id=self.mission_id,
                context=full_context,
                script_executor=self.script_executor,
                graph_service_url="http://graph-service:8001"
            )

            # Update stats
            self.reflection_stats["reflections_run"] += 1
            self.reflection_stats["issues_found"] += reflection_result.get("findings_count", 0)
            self.reflection_stats["scripts_executed"] += reflection_result.get("scripts_executed", 0)
            self.reflection_stats["enrichments_added"] += reflection_result.get("graph_updates", {}).get("nodes_added", 0)

            # Log findings
            if reflection_result.get("findings_count", 0) > 0:
                emit_log(
                    self.mission_id, "INFO",
                    f"Reflection found {reflection_result['findings_count']} issues/opportunities",
                    "reflection"
                )

            if reflection_result.get("scripts_executed", 0) > 0:
                emit_log(
                    self.mission_id, "INFO",
                    f"Executed {reflection_result['scripts_executed']} enrichment scripts",
                    "reflection"
                )

            emit_agent_finished(self.mission_id, "reflector", "Completed", 0)
            return reflection_result

        except Exception as e:
            emit_log(self.mission_id, "WARNING", f"Reflection failed: {e}", "reflection")
            emit_agent_finished(self.mission_id, "reflector", "Failed", 0)
            return {"error": str(e), "skipped": True}

    async def run_subfinder_direct(self) -> List[str]:
        """
        Direct Subfinder bypass (like V3.0 in original main.py)
        Calls SubfinderTool directly to ensure all subdomains are captured.
        """
        emit_log(self.mission_id, "INFO", "Running direct Subfinder bypass...", "passive_recon")
        emit_tool_called(self.mission_id, "subfinder", "subfinder_enum", f"domain={self.target_domain}")

        try:
            sf_raw = self.tools["subfinder"]._run(
                domain=self.target_domain,
                recursive=False,
                all_sources=True,
                timeout=120
            )

            sf_data = json.loads(sf_raw)
            subs_list = sf_data.get("subdomains", []) if isinstance(sf_data, dict) else sf_data if isinstance(sf_data, list) else []

            # Filter to in-scope subdomains
            valid_subs = [s for s in subs_list if isinstance(s, str) and self.target_domain in s]

            emit_log(self.mission_id, "INFO", f"Subfinder direct: {len(valid_subs)} subdomains found", "passive_recon")
            emit_tool_result(self.mission_id, "subfinder", result_count=len(valid_subs), success=True)

            # Publish to graph-service
            for sub in valid_subs:
                await self.graph_client.add_subdomain(sub, source="subfinder")

            return valid_subs

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Subfinder direct bypass failed: {e}", "passive_recon")
            emit_tool_result(self.mission_id, "subfinder", result_count=0, success=False)
            return []

    async def run_wayback_scan(self, hosts: List[str]) -> List[Dict]:
        """
        Universal Wayback Integration (like Phase 20 in original)
        Queries Wayback Machine for historical endpoints.
        """
        if not hosts:
            hosts = [self.target_domain]

        # Add target domain to list
        hosts = list(set(hosts + [self.target_domain]))

        emit_log(self.mission_id, "INFO", f"Running Wayback scan for {len(hosts)} hosts...", "passive_recon")
        emit_tool_called(self.mission_id, "wayback", "wayback_history", f"domains={hosts[:10]}")

        try:
            wb_raw = self.tools["wayback"]._run(domains=hosts[:10])
            wb_data = json.loads(wb_raw)

            if not isinstance(wb_data, list):
                wb_data = []

            emit_log(self.mission_id, "INFO", f"Wayback found {len(wb_data)} historical endpoints", "passive_recon")
            emit_tool_result(self.mission_id, "wayback", result_count=len(wb_data), success=True)

            # Publish endpoints to graph-service
            endpoints_added = 0
            for item in wb_data:
                full_url = item.get("path") or item.get("url")
                if full_url:
                    parsed = urlparse(full_url)
                    host = parsed.netloc
                    path = parsed.path or "/"

                    if host and (host.endswith(self.target_domain) or host == self.target_domain):
                        # Ensure subdomain exists
                        await self.graph_client.add_subdomain(host, source="wayback")
                        # Add endpoint
                        await self.graph_client.add_endpoint(path, method="GET", category="WAYBACK")
                        endpoints_added += 1

            emit_log(self.mission_id, "INFO", f"Published {endpoints_added} Wayback endpoints to graph", "passive_recon")
            return wb_data

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Wayback scan failed: {e}", "passive_recon")
            emit_tool_result(self.mission_id, "wayback", result_count=0, success=False)
            return []

    async def run_dns_resolution(self, subdomains: List[str]) -> List[Dict]:
        """
        DNS Resolution for all confirmed subdomains
        """
        if not subdomains:
            return []

        emit_log(self.mission_id, "INFO", f"Running DNS resolution for {len(subdomains)} subdomains...", "passive_recon")
        emit_tool_called(self.mission_id, "dns_resolver", "dns_resolve", f"subdomains={len(subdomains)} items")

        try:
            dns_raw = self.tools["dns_resolver"]._run(subdomains=subdomains[:20])
            dns_data = json.loads(dns_raw)

            if not isinstance(dns_data, list):
                dns_data = []

            emit_log(self.mission_id, "INFO", f"DNS resolved {len(dns_data)} records", "passive_recon")
            emit_tool_result(self.mission_id, "dns_resolver", result_count=len(dns_data), success=True)

            return dns_data

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"DNS resolution failed: {e}", "passive_recon")
            emit_tool_result(self.mission_id, "dns_resolver", result_count=0, success=False)
            return []

    async def run_httpx_probe(self, subdomains: List[str]) -> List[Dict]:
        """
        HTTPX probing for HTTP services
        """
        if not subdomains:
            return []

        # Build target URLs
        targets = []
        for sub in subdomains[:30]:  # Limit
            targets.append(f"https://{sub}")
            targets.append(f"http://{sub}")

        emit_log(self.mission_id, "INFO", f"Running HTTPX probe for {len(targets)} targets...", "active_recon")
        emit_tool_called(self.mission_id, "httpx", "httpx_probe", f"targets={len(targets)} URLs")

        try:
            httpx_raw = self.tools["httpx"]._run(subdomains=targets[:30])
            httpx_response = json.loads(httpx_raw)

            # HttpxTool returns {"results": [...], "target_count": N, "result_count": N}
            if isinstance(httpx_response, dict):
                httpx_data = httpx_response.get("results", [])
            elif isinstance(httpx_response, list):
                httpx_data = httpx_response
            else:
                httpx_data = []

            emit_log(self.mission_id, "INFO", f"HTTPX found {len(httpx_data)} live services", "active_recon")
            emit_tool_result(self.mission_id, "httpx", result_count=len(httpx_data), success=True)

            # Publish HTTP services to graph
            for svc in httpx_data:
                url = svc.get("url")
                status = svc.get("status_code")
                tech = svc.get("technologies", [])
                if url:
                    await self.graph_client.add_http_service(url, status_code=status, tech=str(tech))

            return httpx_data

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"HTTPX probe failed: {e}", "active_recon")
            emit_tool_result(self.mission_id, "httpx", result_count=0, success=False)
            return []

    async def run_js_mining(self, urls: List[str]) -> List[Dict]:
        """
        JavaScript mining for hidden endpoints and secrets
        """
        if not urls:
            return []

        emit_log(self.mission_id, "INFO", f"Running JS mining for {len(urls)} URLs...", "active_recon")
        emit_tool_called(self.mission_id, "js_miner", "js_mine", f"urls={len(urls)} items")

        try:
            js_raw = self.tools["js_miner"]._run(urls=urls[:10])
            js_data = json.loads(js_raw)

            if not isinstance(js_data, list):
                js_data = []

            # Count endpoints found in JS
            js_endpoints = 0
            for item in js_data:
                js_info = item.get("js", {})
                endpoints = js_info.get("endpoints", [])
                js_endpoints += len(endpoints)

                # Publish JS-discovered endpoints
                for ep in endpoints:
                    path = ep.get("path")
                    method = ep.get("method", "GET")
                    if path:
                        await self.graph_client.add_endpoint(path, method=method, category="JS_INTEL")

            emit_log(self.mission_id, "INFO", f"JS mining found {js_endpoints} endpoints", "active_recon")
            emit_tool_result(self.mission_id, "js_miner", result_count=js_endpoints, success=True)

            return js_data

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"JS mining failed: {e}", "active_recon")
            emit_tool_result(self.mission_id, "js_miner", result_count=0, success=False)
            return []

    async def run_html_crawl(self, urls: List[str]) -> List[Dict]:
        """
        HTML crawling for endpoints in page content
        """
        if not urls:
            return []

        emit_log(self.mission_id, "INFO", f"Running HTML crawl for {len(urls)} URLs...", "active_recon")
        emit_tool_called(self.mission_id, "html_crawler", "html_crawl", f"urls={len(urls)} items")

        try:
            html_raw = self.tools["html_crawler"]._run(urls=urls[:10])
            html_data = json.loads(html_raw)

            if not isinstance(html_data, list):
                html_data = []

            # Publish crawled endpoints
            endpoints_added = 0
            for item in html_data:
                path = item.get("path") or item.get("url")
                if path:
                    await self.graph_client.add_endpoint(path, method="GET", category="HTML_CRAWL")
                    endpoints_added += 1

            emit_log(self.mission_id, "INFO", f"HTML crawl found {endpoints_added} endpoints", "active_recon")
            emit_tool_result(self.mission_id, "html_crawler", result_count=endpoints_added, success=True)

            return html_data

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"HTML crawl failed: {e}", "active_recon")
            emit_tool_result(self.mission_id, "html_crawler", result_count=0, success=False)
            return []

    async def run_passive_phase(self) -> Dict:
        """
        Phase 1: Passive Reconnaissance
        Direct tool calls for reliable data collection + P0.6 Reflection
        """
        phase_start = time.time()
        emit_phase_started(self.mission_id, "passive_recon", 1, 5)
        emit_log(self.mission_id, "INFO", "=== PHASE 1: PASSIVE RECON (Direct Tool Calls + Reflection) ===", "passive_recon")

        # Step 1: Direct Subfinder bypass
        emit_agent_started(self.mission_id, "pathfinder", "Subdomain enumeration via Subfinder")
        self.subdomains = await self.run_subfinder_direct()
        emit_agent_finished(self.mission_id, "pathfinder", "Completed", time.time() - phase_start)

        # P0.6: Reflect on Subfinder results
        await self.run_reflection("subfinder", {"subdomains": self.subdomains})

        # Step 2: Wayback historical scan
        emit_agent_started(self.mission_id, "wayback_scanner", "Historical endpoint discovery")
        wayback_data = await self.run_wayback_scan(self.subdomains)
        emit_agent_finished(self.mission_id, "wayback_scanner", "Completed", time.time() - phase_start)

        # P0.6: Reflect on Wayback results
        await self.run_reflection("wayback", {"urls": wayback_data})

        # Step 3: DNS Resolution
        emit_agent_started(self.mission_id, "dns_analyst", "DNS resolution")
        self.dns_records = await self.run_dns_resolution(self.subdomains)
        emit_agent_finished(self.mission_id, "dns_analyst", "Completed", time.time() - phase_start)

        # P0.6: Reflect on DNS results
        await self.run_reflection("dns_resolver", {"records": self.dns_records})

        # Gate check: If no subdomains, use apex fallback
        if not self.subdomains:
            emit_log(self.mission_id, "WARNING", "ZERO subdomains found. Using apex domain fallback...", "passive_recon")
            self.subdomains = [self.target_domain, f"www.{self.target_domain}"]
            for sub in self.subdomains:
                await self.graph_client.add_subdomain(sub, source="apex_fallback")

        duration = time.time() - phase_start
        emit_phase_completed(self.mission_id, "passive_recon", duration, {
            "subdomains": len(self.subdomains),
            "wayback_endpoints": len(wayback_data),
            "dns_records": len(self.dns_records)
        })

        self.results["passive"] = {
            "subdomains": self.subdomains,
            "wayback": wayback_data,
            "dns": self.dns_records
        }
        return {"phase": "passive_recon", "duration": duration, "result": self.results["passive"]}

    async def run_active_phase(self) -> Dict:
        """
        Phase 2: Active Reconnaissance
        HTTPX probing, JS mining, HTML crawling + P0.6 Reflection
        """
        phase_start = time.time()
        emit_phase_started(self.mission_id, "active_recon", 2, 5)
        emit_log(self.mission_id, "INFO", "=== PHASE 2: ACTIVE RECON (Direct Tool Calls + Reflection) ===", "active_recon")

        # Step 1: HTTPX Probe
        emit_agent_started(self.mission_id, "tech_fingerprinter", "HTTP service probing")
        self.http_services = await self.run_httpx_probe(self.subdomains)
        emit_agent_finished(self.mission_id, "tech_fingerprinter", "Completed", time.time() - phase_start)

        # P0.6: Reflect on HTTPX results
        await self.run_reflection("httpx", {"services": self.http_services})

        # Extract live URLs for further scanning
        live_urls = [svc.get("url") for svc in self.http_services if svc.get("url")]

        # Step 2: JS Mining
        emit_agent_started(self.mission_id, "js_miner", "JavaScript analysis")
        self.js_intel = await self.run_js_mining(live_urls)
        emit_agent_finished(self.mission_id, "js_miner", "Completed", time.time() - phase_start)

        # Step 3: HTML Crawling
        emit_agent_started(self.mission_id, "html_crawler", "HTML endpoint extraction")
        html_data = await self.run_html_crawl(live_urls)
        emit_agent_finished(self.mission_id, "html_crawler", "Completed", time.time() - phase_start)

        duration = time.time() - phase_start
        emit_phase_completed(self.mission_id, "active_recon", duration, {
            "http_services": len(self.http_services),
            "js_intel": len(self.js_intel),
            "html_endpoints": len(html_data)
        })

        self.results["active"] = {
            "http_services": self.http_services,
            "js_intel": self.js_intel,
            "html": html_data
        }
        return {"phase": "active_recon", "duration": duration, "result": self.results["active"]}

    async def run_intel_phase(self) -> Dict:
        """
        Phase 3: Endpoint Intelligence (LLM Analysis)
        Uses CrewAI agent for risk scoring and hypothesis generation
        """
        phase_start = time.time()
        emit_phase_started(self.mission_id, "endpoint_intel", 3, 5)
        emit_log(self.mission_id, "INFO", "=== PHASE 3: ENDPOINT INTELLIGENCE (LLM Analysis) ===", "endpoint_intel")

        # Build agent
        endpoint_intel = build_endpoint_intel(self.target_domain, [])

        # Build context from collected data
        context_str = f"""
Target Domain: {self.target_domain}
Subdomains Found: {len(self.subdomains)}
HTTP Services: {len(self.http_services)}
JS Intel Items: {len(self.js_intel)}

Sample Subdomains: {self.subdomains[:10]}
Sample HTTP Services: {json.dumps(self.http_services[:5], indent=2) if self.http_services else '[]'}
"""

        intel_task = build_endpoint_intel_task(endpoint_intel, self.target_domain, [])
        intel_task.description = f"""Context from reconnaissance:
{context_str}

{intel_task.description}"""

        # Create and run crew
        intel_crew = Crew(
            agents=[endpoint_intel],
            tasks=[intel_task],
            process=Process.sequential,
            verbose=True,
        )

        emit_agent_started(self.mission_id, "endpoint_intel", "Risk analysis and hypothesis generation")

        try:
            result = await asyncio.to_thread(intel_crew.kickoff)
            emit_agent_finished(self.mission_id, "endpoint_intel", "Completed", time.time() - phase_start)

            # Parse result and create hypotheses
            result_str = str(result)
            try:
                intel_data = json.loads(extract_json(result_str))
                if isinstance(intel_data, dict) and "endpoints" in intel_data:
                    for ep in intel_data["endpoints"]:
                        # Create hypotheses
                        for hyp in ep.get("hypotheses", []):
                            await self.graph_client.add_hypothesis(
                                title=hyp.get("title", "Unknown"),
                                attack_type=hyp.get("attack_type", "UNKNOWN"),
                                target_id=ep.get("endpoint_id", "unknown"),
                                confidence=hyp.get("confidence", 0.5)
                            )
            except:
                pass

        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Intel phase failed: {e}", "endpoint_intel")
            result = None

        duration = time.time() - phase_start
        emit_phase_completed(self.mission_id, "endpoint_intel", duration, {"result": str(result)[:500] if result else None})

        self.results["intel"] = result
        return {"phase": "endpoint_intel", "duration": duration, "result": result}

    async def run_planning_phase(self) -> Dict:
        """
        Phase 4: Attack Planning (LLM Analysis)
        Uses CrewAI agent for attack path identification
        """
        phase_start = time.time()
        emit_phase_started(self.mission_id, "planning", 4, 5)
        emit_log(self.mission_id, "INFO", "=== PHASE 4: ATTACK PLANNING (LLM Analysis) ===", "planning")

        # Build agent
        planner = build_planner(self.target_domain, [])

        # Build context
        context_str = f"""
Target: {self.target_domain}
Subdomains: {len(self.subdomains)}
HTTP Services: {len(self.http_services)}
Mode: {self.mode.upper()}

High-value targets (HTTP services):
{json.dumps(self.http_services[:10], indent=2) if self.http_services else 'None'}
"""

        plan_task = build_planning_task(planner, self.target_domain, [])
        plan_task.description = f"""Reconnaissance context:
{context_str}

{plan_task.description}"""

        plan_crew = Crew(
            agents=[planner],
            tasks=[plan_task],
            process=Process.sequential,
            verbose=True,
        )

        emit_agent_started(self.mission_id, "planner", "Attack path analysis")

        try:
            result = await asyncio.to_thread(plan_crew.kickoff)
            emit_agent_finished(self.mission_id, "planner", "Completed", time.time() - phase_start)
        except Exception as e:
            emit_log(self.mission_id, "ERROR", f"Planning phase failed: {e}", "planning")
            result = None

        duration = time.time() - phase_start
        emit_phase_completed(self.mission_id, "planning", duration, {"result": str(result)[:500] if result else None})

        self.results["planning"] = result
        return {"phase": "planning", "duration": duration, "result": result}

    async def run_deep_verification_phase(self) -> Dict:
        """
        Phase 5: Deep Verification (Lot 2.1)
        Uses 4 specialized agents to validate vulnerabilities with evidence collection.

        Agent sequence:
        1. VulnTriage - Prioritize targets from graph
        2. StackPolicy - Map tech stacks to check modules
        3. ValidationPlanner - Create verification execution plan
        4. EvidenceCurator - Review results and update graph
        """
        phase_start = time.time()
        emit_phase_started(self.mission_id, "deep_verification", 5, 6)
        emit_log(self.mission_id, "INFO", "=== PHASE 5: DEEP VERIFICATION (CrewAI Agents) ===", "deep_verification")

        # Get verification tools
        verification_tools = [
            self.tools["graph_query"],
            self.tools["check_runner"],
            self.tools["graph_updater"],
        ]

        # Get mode from self
        mode_upper = self.mode.upper()

        # ============================================================
        # Step 1: VulnTriage Agent - Prioritize targets
        # ============================================================
        emit_agent_started(self.mission_id, "vuln_triage", "Prioritizing verification targets")
        emit_log(self.mission_id, "INFO", "[1/4] VulnTriage: Analyzing graph for verification targets...", "deep_verification")

        vuln_triage_agent = build_vuln_triage(self.target_domain, [self.tools["graph_query"]])
        triage_task = build_vuln_triage_task(
            vuln_triage_agent,
            self.target_domain,
            vulnerabilities=None,  # Agent will query graph
            mode=mode_upper
        )

        triage_crew = Crew(
            agents=[vuln_triage_agent],
            tasks=[triage_task],
            process=Process.sequential,
            verbose=True,
        )

        triage_result = None
        try:
            triage_result = await asyncio.to_thread(triage_crew.kickoff)
            emit_log(self.mission_id, "INFO", f"VulnTriage completed: {str(triage_result)[:200]}", "deep_verification")
        except Exception as e:
            emit_log(self.mission_id, "WARNING", f"VulnTriage failed: {e}", "deep_verification")
            triage_result = {"targets": []}

        emit_agent_finished(self.mission_id, "vuln_triage", "Completed", time.time() - phase_start)

        # Parse triage results
        triage_data = self._parse_verification_result(triage_result)
        targets = triage_data.get("targets", triage_data) if isinstance(triage_data, dict) else []

        if not targets:
            emit_log(self.mission_id, "INFO", "No targets found for verification - using HTTP services as fallback", "deep_verification")
            # Fallback: Use HTTP services as targets
            targets = [
                {
                    "target_id": f"http_service:{svc.get('url')}",
                    "target_url": svc.get("url"),
                    "tech_stack": svc.get("technologies", "unknown"),
                    "risk_score": 50,
                }
                for svc in self.http_services[:5]
                if svc.get("url")
            ]

        emit_log(self.mission_id, "INFO", f"VulnTriage identified {len(targets)} targets for verification", "deep_verification")

        # ============================================================
        # Step 2: StackPolicy Agent - Map stacks to modules
        # ============================================================
        emit_agent_started(self.mission_id, "stack_policy", "Mapping tech stacks to check modules")
        emit_log(self.mission_id, "INFO", "[2/4] StackPolicy: Mapping technology stacks to check modules...", "deep_verification")

        # Get available modules from check runner
        try:
            modules_raw = self.tools["check_runner"]._run(action="list_modules")
            modules_data = json.loads(modules_raw)
            available_modules = [m["id"] for m in modules_data.get("modules", [])]
        except:
            available_modules = ["security-headers-01", "server-info-disclosure-01", "config-exposure-01"]

        stack_policy_agent = build_stack_policy(
            self.target_domain,
            [self.tools["graph_query"], self.tools["check_runner"]]
        )
        stack_task = build_stack_policy_task(
            stack_policy_agent,
            self.target_domain,
            targets=targets if isinstance(targets, list) else [],
            available_modules=available_modules,
            mode=mode_upper
        )

        stack_crew = Crew(
            agents=[stack_policy_agent],
            tasks=[stack_task],
            process=Process.sequential,
            verbose=True,
        )

        stack_result = None
        try:
            stack_result = await asyncio.to_thread(stack_crew.kickoff)
            emit_log(self.mission_id, "INFO", f"StackPolicy completed: {str(stack_result)[:200]}", "deep_verification")
        except Exception as e:
            emit_log(self.mission_id, "WARNING", f"StackPolicy failed: {e}", "deep_verification")

        emit_agent_finished(self.mission_id, "stack_policy", "Completed", time.time() - phase_start)

        # Parse stack mappings
        stack_data = self._parse_verification_result(stack_result)
        mappings = stack_data.get("mappings", []) if isinstance(stack_data, dict) else []

        # If no mappings, create default ones
        if not mappings and targets:
            emit_log(self.mission_id, "INFO", "Using default module mappings", "deep_verification")
            mappings = [
                {
                    "target_id": t.get("target_id") or t.get("target_url"),
                    "target_url": t.get("target_url"),
                    "assigned_modules": ["security-headers-01", "server-info-disclosure-01"],
                }
                for t in (targets if isinstance(targets, list) else [])[:5]
            ]

        # ============================================================
        # Step 3: Execute Checks (Direct tool calls for reliability)
        # ============================================================
        emit_log(self.mission_id, "INFO", "[3/4] Executing verification checks...", "deep_verification")

        check_results = []
        for mapping in mappings[:10]:  # Limit to 10 targets
            target_url = mapping.get("target_url")
            target_id = mapping.get("target_id", f"endpoint:{target_url}")
            modules = mapping.get("assigned_modules", [])

            for module_id in modules[:3]:  # Limit to 3 modules per target
                emit_log(self.mission_id, "INFO", f"Running {module_id} against {target_url}", "deep_verification")

                try:
                    result_raw = self.tools["check_runner"]._run(
                        action="run",
                        module_id=module_id,
                        target_url=target_url,
                        target_id=target_id,
                        mission_id=self.mission_id,
                        mode=mode_upper
                    )
                    result = json.loads(result_raw)
                    check_result = result.get("check_result", result)
                    check_results.append(check_result)

                    # Log result
                    status = check_result.get("status", "unknown")
                    vuln_status = check_result.get("vuln_status", "unknown")
                    emit_log(
                        self.mission_id, "INFO",
                        f"Check {module_id}: status={status}, vuln={vuln_status}, evidence={check_result.get('evidence_count', 0)}",
                        "deep_verification"
                    )

                except Exception as e:
                    emit_log(self.mission_id, "WARNING", f"Check {module_id} failed: {e}", "deep_verification")

        self.check_results = check_results
        emit_log(self.mission_id, "INFO", f"Executed {len(check_results)} verification checks", "deep_verification")

        # ============================================================
        # Step 4: EvidenceCurator Agent - Review and store results
        # ============================================================
        emit_agent_started(self.mission_id, "evidence_curator", "Curating evidence and updating graph")
        emit_log(self.mission_id, "INFO", "[4/4] EvidenceCurator: Processing verification results...", "deep_verification")

        evidence_curator_agent = build_evidence_curator(
            self.target_domain,
            [self.tools["graph_query"], self.tools["graph_updater"], self.tools["bulk_graph_updater"]]
        )
        curation_task = build_evidence_curation_task(
            evidence_curator_agent,
            self.target_domain,
            check_results=check_results
        )

        curation_crew = Crew(
            agents=[evidence_curator_agent],
            tasks=[curation_task],
            process=Process.sequential,
            verbose=True,
        )

        curation_result = None
        try:
            curation_result = await asyncio.to_thread(curation_crew.kickoff)
            emit_log(self.mission_id, "INFO", f"EvidenceCurator completed: {str(curation_result)[:200]}", "deep_verification")
        except Exception as e:
            emit_log(self.mission_id, "WARNING", f"EvidenceCurator failed: {e}", "deep_verification")

        emit_agent_finished(self.mission_id, "evidence_curator", "Completed", time.time() - phase_start)

        # Parse curation results
        curation_data = self._parse_verification_result(curation_result)

        # Store results
        self.verification_results = {
            "triage": triage_data,
            "stack_mappings": stack_data,
            "check_results": check_results,
            "curation": curation_data,
        }

        # Compile summary
        summary = curation_data.get("summary", {}) if isinstance(curation_data, dict) else {}
        confirmed_count = summary.get("confirmed", 0)
        total_checks = len(check_results)

        duration = time.time() - phase_start
        emit_phase_completed(self.mission_id, "deep_verification", duration, {
            "targets_analyzed": len(targets) if isinstance(targets, list) else 0,
            "checks_executed": total_checks,
            "vulns_confirmed": confirmed_count,
        })

        emit_log(
            self.mission_id, "INFO",
            f"Deep Verification completed: {total_checks} checks, {confirmed_count} confirmed vulns",
            "deep_verification"
        )

        self.results["deep_verification"] = self.verification_results
        return {
            "phase": "deep_verification",
            "duration": duration,
            "targets_analyzed": len(targets) if isinstance(targets, list) else 0,
            "checks_executed": total_checks,
            "vulns_confirmed": confirmed_count,
            "result": self.verification_results,
        }

    def _parse_verification_result(self, result: Any) -> Dict:
        """Parse verification agent result to dict."""
        if result is None:
            return {}

        result_str = str(result)

        try:
            # Try to extract JSON
            extracted = extract_json(result_str)
            return json.loads(extracted)
        except:
            pass

        # Return as-is if already dict
        if isinstance(result, dict):
            return result

        # Wrap string in dict
        return {"raw": result_str[:1000]}

    async def run_full_mission(self) -> Dict:
        """
        Run complete reconnaissance mission with hybrid approach:
        - Direct tool calls for data collection
        - LLM agents for analysis
        """
        self.start_time = time.time()

        emit_mission_status(self.mission_id, "running", f"Starting hybrid mission on {self.target_domain}")
        emit_log(self.mission_id, "INFO", f"Mission {self.mission_id} starting in {self.mode} mode (V2.0 Hybrid)", "mission")

        # Check LLM availability (not required for tool-only phases)
        llm_available = self.check_llm_available()

        try:
            # Phase 1: Passive Recon (Direct tool calls)
            emit_log(self.mission_id, "INFO", "=== PHASE 1: PASSIVE RECON ===", "mission")
            passive_result = await self.run_passive_phase()

            # Phase 2: Active Recon (Direct tool calls)
            emit_log(self.mission_id, "INFO", "=== PHASE 2: ACTIVE RECON ===", "mission")
            active_result = await self.run_active_phase()

            # Phase 3: Endpoint Intel (LLM analysis - optional)
            if llm_available:
                emit_log(self.mission_id, "INFO", "=== PHASE 3: ENDPOINT INTEL ===", "mission")
                intel_result = await self.run_intel_phase()
            else:
                emit_log(self.mission_id, "WARNING", "Skipping LLM phases - Ollama not available", "mission")
                intel_result = {"phase": "endpoint_intel", "skipped": True}

            # Phase 4: Planning (LLM analysis - optional)
            if llm_available:
                emit_log(self.mission_id, "INFO", "=== PHASE 4: ATTACK PLANNING ===", "mission")
                planning_result = await self.run_planning_phase()
            else:
                planning_result = {"phase": "planning", "skipped": True}

            # Phase 5: Deep Verification (Lot 2.1 - requires LLM for agent reasoning)
            deep_verification_result = {"phase": "deep_verification", "skipped": True}
            if llm_available and self.http_services:
                emit_log(self.mission_id, "INFO", "=== PHASE 5: DEEP VERIFICATION ===", "mission")
                try:
                    deep_verification_result = await self.run_deep_verification_phase()
                except Exception as e:
                    emit_log(self.mission_id, "WARNING", f"Deep Verification phase failed: {e}", "mission")
                    deep_verification_result = {"phase": "deep_verification", "error": str(e)}
            else:
                if not llm_available:
                    emit_log(self.mission_id, "INFO", "Skipping Deep Verification - LLM not available", "mission")
                elif not self.http_services:
                    emit_log(self.mission_id, "INFO", "Skipping Deep Verification - no HTTP services found", "mission")

            # Close graph client
            await self.graph_client.close()

            # Mission complete
            total_duration = time.time() - self.start_time

            # Build verification summary
            verification_summary = {}
            if isinstance(deep_verification_result, dict) and not deep_verification_result.get("skipped"):
                verification_summary = {
                    "checks_executed": deep_verification_result.get("checks_executed", 0),
                    "vulns_confirmed": deep_verification_result.get("vulns_confirmed", 0),
                }

            summary = {
                "subdomains": len(self.subdomains),
                "http_services": len(self.http_services),
                "endpoints": len(self.endpoints),
                "dns_records": len(self.dns_records),
                "verification": verification_summary,  # Lot 2.1
            }

            # P0.6: Log reflection stats
            if self.reflection_stats["reflections_run"] > 0:
                emit_log(
                    self.mission_id, "INFO",
                    f"Reflection stats: {self.reflection_stats['reflections_run']} runs, "
                    f"{self.reflection_stats['scripts_executed']} scripts, "
                    f"{self.reflection_stats['enrichments_added']} enrichments",
                    "reflection"
                )

            emit_log(self.mission_id, "INFO", f"Mission completed in {total_duration:.2f}s - {summary}", "mission")
            emit_mission_status(self.mission_id, "completed", f"Mission completed: {summary}")

            return {
                "mission_id": self.mission_id,
                "target_domain": self.target_domain,
                "status": "completed",
                "duration": total_duration,
                "summary": summary,
                "reflection_stats": self.reflection_stats,  # P0.6: Include reflection metrics
                "phases": {
                    "passive": passive_result,
                    "active": active_result,
                    "intel": intel_result,
                    "planning": planning_result,
                    "deep_verification": deep_verification_result,  # Lot 2.1
                },
                "results": self.results,
            }

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            emit_mission_status(self.mission_id, "failed", str(e))
            emit_log(self.mission_id, "ERROR", f"Mission failed: {e}", "mission")
            emit_log(self.mission_id, "ERROR", error_trace, "mission")

            try:
                await self.graph_client.close()
            except:
                pass

            return {
                "mission_id": self.mission_id,
                "target_domain": self.target_domain,
                "status": "failed",
                "error": str(e),
                "traceback": error_trace,
                "duration": time.time() - self.start_time,
            }


async def run_crewai_mission(
    mission_id: str,
    target_domain: str,
    mode: str = "aggressive"
) -> Dict:
    """
    Entry point to run a CrewAI reconnaissance mission (V2.0 Hybrid)
    """
    emit_log(mission_id, "INFO", f"run_crewai_mission() V2.0 called for {target_domain}", "init")
    runner = CrewMissionRunner(mission_id, target_domain, mode)
    return await runner.run_full_mission()
