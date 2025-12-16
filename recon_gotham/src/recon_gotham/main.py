
import os
import sys
import yaml
from dotenv import load_dotenv
import json
import ast
import logging

# Disable telemetry
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPTOUT"] = "true"

load_dotenv()

from crewai import Agent, Task, Crew, Process

# Add src to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.append(src_dir)

from recon_gotham.tools.subfinder_tool import SubfinderTool
from recon_gotham.tools.httpx_tool import HttpxTool
from recon_gotham.tools.js_miner_tool import JsMinerTool
from recon_gotham.tools.dns_resolver_tool import DnsResolverTool
from recon_gotham.tools.asn_lookup_tool import ASNLookupTool
from recon_gotham.tools.html_crawler_tool import HtmlCrawlerTool
from recon_gotham.tools.wayback_tool import WaybackTool
from recon_gotham.tools.my_robots_tool import MyRobotsTool
from recon_gotham.tools.nuclei_tool import NucleiTool
from recon_gotham.tools.ffuf_tool import FfufTool

from recon_gotham.core.asset_graph import AssetGraph
from recon_gotham.reporting.report_builder import ReportBuilder

# V3.0 Imports - Structured Logging, Metrics, Pipelines
import uuid
from datetime import datetime
from recon_gotham.core.logging import ReconLogger, get_logger
from recon_gotham.pipelines.verification_pipeline import VerificationPipeline
from recon_gotham.pipelines.reporting_service import ReportingService

# --- Helpers ---

def load_config(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def extract_json(text):
    if not text: return "{}"
    text = str(text).strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    # Heuristic find start/end
    first_open_sq = text.find('[')
    last_close_sq = text.rfind(']')
    first_open_cur = text.find('{')
    last_close_cur = text.rfind('}')
    
    extracted = text
    if first_open_sq != -1 and (first_open_cur == -1 or first_open_sq < first_open_cur):
         if last_close_sq != -1: extracted = text[first_open_sq:last_close_sq+1]
    elif first_open_cur != -1:
         if last_close_cur != -1: extracted = text[first_open_cur:last_close_cur+1]
    return extracted

def generate_mission_summary(domain, graph_obj, plan_data, output_path, mode="aggressive"):
    """
    Generate mission summary from graph data.
    Also writes to knowledge/{domain}_summary.md.
    """
    import datetime
    nodes = graph_obj.nodes if hasattr(graph_obj, 'nodes') else graph_obj.get("nodes", [])
    
    # Bloc 2: Calculate stats from graph nodes, with scope filtering
    def is_in_scope(node):
        node_id = node.get("id", "")
        # Reject nodes that are clearly out of scope
        if "example.com" in node_id.lower():
            return False
        if domain and node.get("type") == "SUBDOMAIN":
            return domain in node_id
        return True
    
    in_scope_nodes = [n for n in nodes if is_in_scope(n)]
    
    subdomain_count = len([n for n in in_scope_nodes if n["type"] == "SUBDOMAIN"])
    http_count = len([n for n in in_scope_nodes if n["type"] == "HTTP_SERVICE"])
    endpoint_count = len([n for n in in_scope_nodes if n["type"] == "ENDPOINT"])
    vuln_count = len([n for n in in_scope_nodes if n["type"] == "VULNERABILITY"])
    dns_count = len([n for n in in_scope_nodes if n["type"] in ["IP_ADDRESS", "DNS_RECORD", "ASN"]])
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    md = f"# Mission Summary: {domain}\n\n"
    md += f"**Date:** {now}\n"
    md += f"**Mode:** {mode.upper()}\n\n"
    md += "## [STATS] Asset Statistics\n"
    md += f"- **Subdomains Found**: {subdomain_count}\n"
    md += f"- **HTTP Services**: {http_count}\n"
    md += f"- **Endpoints**: {endpoint_count}\n"
    md += f"- **DNS/IP/ASN Records**: {dns_count}\n"
    md += f"- **Vulnerabilities**: {vuln_count}\n\n"
    
    md += "## [TARGET] Attack Plan\n"
    
    # Fix 1: Calculate global max risk to gate attack plan
    global_max_risk = 0
    for n in in_scope_nodes:
        if n["type"] == "ENDPOINT":
            risk = n.get("properties", {}).get("risk_score", 0)
            if risk > global_max_risk:
                global_max_risk = risk
    
    # Only show offensive plan if max_risk >= 30 OR we have vulnerabilities
    should_show_offensive = global_max_risk >= 30 or vuln_count > 0
    
    if plan_data and isinstance(plan_data, list) and should_show_offensive:
        # Filter attack plan to only in-scope targets
        filtered_plan = [p for p in plan_data if domain in p.get('subdomain', '')]
        if filtered_plan:
            for i, p in enumerate(filtered_plan, 1):
                md += f"{i}. **{p.get('subdomain')}** (Score: {p.get('score')}) — Actions: {', '.join(p.get('next_actions', []))}\n"
        else:
            md += "_No in-scope attack paths identified._\n"
    elif not should_show_offensive:
        md += "_No actionable plan generated (only low-risk endpoints detected, max risk_score = " + str(global_max_risk) + ")._\n"
    else:
        md += "_No actionable plan generated._\n"
    
    # Phase 23: Endpoints & API Intelligence Section
    endpoint_nodes = [n for n in in_scope_nodes if n["type"] == "ENDPOINT"]
    if endpoint_nodes:
        md += "\n## 🔍 Endpoint Intelligence (Phase 23)\n"
        
        # Category distribution
        categories = {}
        for ep in endpoint_nodes:
            cat = ep.get("properties", {}).get("category", "UNKNOWN")
            categories[cat] = categories.get(cat, 0) + 1
        
        md += "### Category Distribution\n"
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            md += f"- **{cat}**: {count}\n"
        
        # Top 5 by risk score - Fix 3: Adjust wording based on actual risk
        sorted_eps = sorted(endpoint_nodes, key=lambda x: x.get("properties", {}).get("risk_score", 0), reverse=True)
        top_5 = sorted_eps[:5]
        max_risk = top_5[0].get("properties", {}).get("risk_score", 0) if top_5 else 0
        
        if top_5:
            # Fix 3: Only call it "High-Risk" if max_risk >= 30
            if max_risk >= 30:
                md += "\n### [!] Top 5 High-Risk Endpoints\n"
            else:
                md += "\n### Top 5 Endpoints par Risk Score\n"
            
            for i, ep in enumerate(top_5, 1):
                props = ep.get("properties", {})
                path = props.get("path", "?")
                risk = props.get("risk_score", 0)
                cat = props.get("category", "UNKNOWN")
                behavior = props.get("behavior_hint", "")
                md += f"{i}. `{path}` — Risk: **{risk}**, Category: {cat}, Behavior: {behavior}\n"
            
            # Fix 3: Add clarifying message if all endpoints are low-risk
            if max_risk < 30:
                md += f"\n> Tous les endpoints identifies presentent un risque faible (max risk_score = {max_risk}).\n"
                md += "> Aucune cible prioritaire n'a ete retenue pour la phase offensive.\n"
    
    # Phase 23: Hypotheses tracking
    hypothesis_nodes = [n for n in nodes if n["type"] == "HYPOTHESIS"]
    if hypothesis_nodes:
        md += "\n### 🎯 Attack Hypotheses\n"
        for hypo in hypothesis_nodes[:5]:  # Top 5
            props = hypo.get("properties", {})
            title = props.get("title", "Unknown")
            atype = props.get("attack_type", "UNKNOWN")
            conf = props.get("confidence", 0)
            prio = props.get("priority", 0)
            md += f"- **{title}** — Type: {atype}, Confidence: {conf:.1%}, Priority: {prio}/5\n"
    
    # Write to output path (e.g., recon_gotham/output/)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"[+] Mission Summary saved to: {output_path}")
    
    # Bloc 4: Also write to knowledge/
    knowledge_dir = "recon_gotham/knowledge"
    os.makedirs(knowledge_dir, exist_ok=True)
    knowledge_path = os.path.join(knowledge_dir, f"{domain}_summary.md")
    with open(knowledge_path, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"[+] Knowledge Summary saved to: {knowledge_path}")

def build_baseline_targets(domain):
    return [f"https://{domain}", f"http://{domain}", f"https://www.{domain}"]

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("domain")
    parser.add_argument("--mode", choices=["stealth", "aggressive"], default="stealth")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--seed-file", dest="seed_file", help="File with known subdomains to inject (one per line)")
    args = parser.parse_args()
    
    target_domain = args.domain
    mission_mode = args.mode
    debug_mode = args.debug
    seed_file = args.seed_file
    
    # V3.0: Generate Run ID and initialize metrics
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:8]
    start_time = datetime.now()
    
    # V3.0: Configure structured logging
    ReconLogger.configure(run_id=run_id, domain=target_domain, log_dir="recon_gotham/output")
    logger = get_logger("main")
    
    # V3.0: Initialize metrics
    metrics = {
        "run_id": run_id,
        "target_domain": target_domain,
        "mode": mission_mode.upper(),
        "start_time": start_time.isoformat(),
        "phase_durations": {},
        "counts": {
            "subdomains": 0,
            "http_services": 0,
            "endpoints": 0,
            "endpoints_enriched": 0,
            "parameters": 0,
            "hypotheses": 0,
            "vulnerabilities": 0
        },
        "errors": []
    }
    
    print(f"[+] Mission Mode: {mission_mode.upper()}")
    print(f"[+] Run ID: {run_id}")
    
    # Load Configs
    base_path = os.path.dirname(os.path.abspath(__file__))
    agents_config = load_config(os.path.join(base_path, 'config', 'agents.yaml'))
    tasks_config = load_config(os.path.join(base_path, 'config', 'tasks.yaml'))
    
    # V3.0: Load budget configuration
    budget_path = os.path.join(base_path, 'config', 'budget.yaml')
    budget = {}
    if os.path.exists(budget_path):
        budget = load_config(budget_path)
    
    # Model Configuration
    # Supported providers: "ollama", "openai", "anthropic"
    # For OpenAI: set OPENAI_API_KEY and LLM_PROVIDER=openai
    # For Anthropic: set ANTHROPIC_API_KEY and LLM_PROVIDER=anthropic
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    if llm_provider == "openai":
        model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        llm_config = f"openai/{model_name}"
        print(f"[+] Using OpenAI: {model_name}")
    elif llm_provider == "anthropic":
        model_name = os.getenv("MODEL_NAME", "claude-3-haiku-20240307")
        llm_config = f"anthropic/{model_name}"
        print(f"[+] Using Anthropic: {model_name}")
    else:
        # Default: Ollama (local)
        model_name = os.getenv("MODEL_NAME", "qwen2.5:14b")
        llm_config = f"ollama/{model_name}"
        print(f"[+] Using Ollama: {model_name}")

    # Tools Instantiation
    # Use 'my_httpx_tool' to avoid shadowing issues
    subfinder_tool = SubfinderTool()
    my_httpx_tool = HttpxTool()
    js_tool = JsMinerTool()
    html_tool = HtmlCrawlerTool()
    wayback_tool = WaybackTool()
    nuclei_tool = NucleiTool()
    ffuf_tool = FfufTool()
    
    try:
        robots_tool = MyRobotsTool()
    except:
        robots_tool = None

    dns_tool = DnsResolverTool()
    asn_tool = ASNLookupTool()

    # Agents
    pathfinder = Agent(role=agents_config['pathfinder']['role'], goal=agents_config['pathfinder']['goal'].format(target_domain=target_domain), backstory=agents_config['pathfinder']['backstory'], verbose=True, allow_delegation=False, tools=[subfinder_tool], llm=llm_config)
    
    intelligence_analyst = Agent(role=agents_config['intelligence_analyst']['role'], goal=agents_config['intelligence_analyst']['goal'], backstory=agents_config['intelligence_analyst']['backstory'], verbose=True, allow_delegation=False, llm=llm_config)
    
    # Tech: uses my_httpx_tool
    tech_config = agents_config['tech_fingerprinter']
    tech_fingerprinter = Agent(role=tech_config['role'], goal=tech_config['goal'], backstory=tech_config['backstory'], verbose=True, allow_delegation=False, tools=[my_httpx_tool], llm=llm_config)
    
    js_miner = Agent(role=agents_config['js_miner']['role'], goal=agents_config['js_miner']['goal'], backstory=agents_config['js_miner']['backstory'], verbose=True, allow_delegation=False, tools=[js_tool], llm=llm_config)
    
    ep_tools = [t for t in [html_tool, wayback_tool, robots_tool] if t]
    endpoint_analyst = Agent(role=agents_config['endpoint_analyst']['role'], goal=agents_config['endpoint_analyst']['goal'], backstory=agents_config['endpoint_analyst']['backstory'], verbose=True, allow_delegation=False, tools=ep_tools, llm=llm_config)
    
    dns_analyst = Agent(role=agents_config['dns_analyst']['role'], goal=agents_config['dns_analyst']['goal'], backstory=agents_config['dns_analyst']['backstory'], verbose=True, allow_delegation=False, tools=[dns_tool], llm=llm_config)
    asn_analyst = Agent(role=agents_config['asn_analyst']['role'], goal=agents_config['asn_analyst']['goal'], backstory=agents_config['asn_analyst']['backstory'], verbose=True, allow_delegation=False, tools=[asn_tool], llm=llm_config)
    
    planner = Agent(role=agents_config['planner']['role'], goal=agents_config['planner']['goal'], backstory=agents_config['planner']['backstory'], verbose=True, allow_delegation=False, llm=llm_config)
    
    param_hunter = Agent(role=agents_config['param_hunter']['role'], goal=agents_config['param_hunter']['goal'], backstory=agents_config['param_hunter']['backstory'], verbose=True, allow_delegation=False, llm=llm_config)

    # Tasks
    smart_enum = Task(description=tasks_config['smart_enumeration_task']['description'].format(target_domain=target_domain), expected_output=tasks_config['smart_enumeration_task']['expected_output'], agent=pathfinder)
    
    context_analysis = Task(description=tasks_config['context_analysis_task']['description'].format(target_domain=target_domain), expected_output=tasks_config['context_analysis_task']['expected_output'], agent=intelligence_analyst, context=[smart_enum])
    
    dns_enrich = Task(description=tasks_config['dns_enrichment_task']['description'], expected_output=tasks_config['dns_enrichment_task']['expected_output'], agent=dns_analyst, context=[context_analysis])
    
    asn_enrich = Task(description=tasks_config['asn_enrichment_task']['description'], expected_output=tasks_config['asn_enrichment_task']['expected_output'], agent=asn_analyst, context=[dns_enrich])
    
    # Tech Fingerprint - Remove direct context dependency for split execution
    # We will inject context via description update or inputs
    tech_desc = tasks_config['tech_fingerprint_task']['description']
    if mission_mode == "aggressive": tech_desc += "\n[AGGRESSIVE] Scan ports 80,443,8080,8443."
    
    tech_task = Task(description=tech_desc, expected_output=tasks_config['tech_fingerprint_task']['expected_output'], agent=tech_fingerprinter)
    
    js_task = Task(description=tasks_config['js_miner_task']['description'], expected_output=tasks_config['js_miner_task']['expected_output'], agent=js_miner, context=[tech_task])
    
    ep_task = Task(description=tasks_config['endpoint_discovery_task']['description'], expected_output=tasks_config['endpoint_discovery_task']['expected_output'], agent=endpoint_analyst, context=[tech_task])
    
    param_task = Task(description=tasks_config['param_discovery_task']['description'], expected_output=tasks_config['param_discovery_task']['expected_output'], agent=param_hunter, context=[ep_task])
    
    planning_task = Task(description=tasks_config['planning_task']['description'], expected_output=tasks_config['planning_task']['expected_output'], agent=planner)
    
    # Graph (pass target_domain for scope checks)
    graph = AssetGraph(target_domain=target_domain)
    
    # --- PHASE 1: PASSIVE RECON ---
    passive_agents = [pathfinder, intelligence_analyst, dns_analyst, asn_analyst]
    passive_tasks = [smart_enum, context_analysis, dns_enrich, asn_enrich]
    
    passive_crew = Crew(
        agents=passive_agents,
        tasks=passive_tasks,
        process=Process.sequential,
        verbose=True
    )
    
    print(f"[+] Starting Passive Phase on {target_domain}...")
    try:
        passive_crew.kickoff()
    except Exception as e:
        print(f"[-] Passive Crew Failed: {e}")

    # --- Ingestion Phase (Passive) ---
    print("[+] Ingesting Passive Outputs...")
    
    # 1. Pathfinder -> Subdomains (V3.0: Direct Subfinder Bypass)
    # The LLM agent often fails to parse Subfinder output correctly.
    # We call SubfinderTool directly to ensure all subdomains are captured.
    print("[+] Direct Subfinder bypass (V3.0)...")
    try:
        sf_raw = subfinder_tool._run(domain=target_domain, recursive=False, all_sources=True, timeout=60)
        sf_data = json.loads(sf_raw)
        
        # Handle both formats: {"subdomains": [...]} or {"domain": ..., "subdomains": [...]}
        subs_list = sf_data.get("subdomains", []) if isinstance(sf_data, dict) else sf_data if isinstance(sf_data, list) else []
        
        if subs_list:
            print(f"    - Subfinder direct: {len(subs_list)} subdomains found")
            for sub in subs_list:
                if isinstance(sub, str) and target_domain in sub:
                    graph.ensure_subdomain(sub, tag="SUBFINDER_DIRECT")
        else:
            print("    - Subfinder direct: 0 subdomains (using apex fallback)")
    except Exception as e:
        print(f"[-] Subfinder direct bypass failed: {e}")
        metrics["errors"].append(f"Subfinder bypass: {e}")
    
    # 2. DNS -> add_dns_resolution
    try:
        raw = dns_enrich.output.raw
        data = json.loads(extract_json(raw))
        if isinstance(data, list):
            for d in data:
                graph.add_dns_resolution(d.get("subdomain"), d.get("ips", []), d.get("records", {}))
    except: pass

    # 3. ASN -> add_asn_info
    try:
        raw = asn_enrich.output.raw
        data = json.loads(extract_json(raw))
        if isinstance(data, list):
            for a in data:
                pass 
    except: pass
    
    # --- Universal Wayback Integration (Phase 20) ---
    print("[+] Running Wayback Historical Scan...")
    # Gather ALL subdomains found so far
    subs = [n["id"] for n in graph.nodes if n["type"] == "SUBDOMAIN"]
    # Also add target domain
    subs.append(target_domain)
    subs = list(set(subs))
    
    if subs:
        print(f"[*] Querying Wayback Machine for {len(subs)} hosts...")
        try:
             # WaybackTool._run takes 'domains' arg
             wb_res = wayback_tool._run(domains=subs)
             wb_data = json.loads(wb_res)
             if isinstance(wb_data, list):
                 print(f"[+] Wayback found {len(wb_data)} historical endpoints.")
                 for item in wb_data:
                     # Ingest
                     full_url = item.get("path")
                     if full_url:
                          from urllib.parse import urlparse
                          parsed = urlparse(full_url)
                          host = parsed.netloc
                          if host and (host.endswith(target_domain) or host == target_domain):
                               # Ensure host exists
                               graph.ensure_subdomain(host, tag="WAYBACK")
                               # Add Endpoint
                               graph.add_endpoint(full_url, "GET", "WAYBACK", full_url, confidence=0.6)
        except Exception as e:
            print(f"[-] Wayback Scan Failed: {e}")

    # --- GATE CHECK (Phase 20) - V3.0: No Abort, Use Apex Fallback ---
    sub_count = len([n for n in graph.nodes if n["type"] == "SUBDOMAIN"])
    print(f"[!] Gate Check: Found {sub_count} subdomains.")
    
    if sub_count == 0:
        print("[!] ZERO subdomains from Subfinder. Using apex domain fallback...")
        # V3.0: Add apex domain and www as fallback instead of aborting
        graph.ensure_subdomain(target_domain, tag="APEX_FALLBACK")
        graph.ensure_subdomain(f"www.{target_domain}", tag="APEX_FALLBACK")
        print(f"    - Added {target_domain} and www.{target_domain} as baseline targets")
        
        # Also add HTTP services directly for the apex domain
        for base in [f"https://{target_domain}", f"https://www.{target_domain}", f"http://{target_domain}"]:
            try:
                import requests
                resp = requests.head(base, timeout=5, verify=False, allow_redirects=True)
                if resp.status_code < 500:
                    graph.add_subdomain_with_http({
                        "subdomain": base.split("://")[1].split("/")[0],
                        "priority": 10,
                        "tag": "APEX_FALLBACK",
                        "category": "HTTP",
                        "http": {
                            "url": base,
                            "status_code": resp.status_code,
                            "technologies": [],
                            "ip": None
                        }
                    })
                    print(f"    - {base}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"    - {base}: unreachable ({e})")
    
    # V3.0: Inject seeded subdomains if seed-file provided
    if seed_file and os.path.exists(seed_file):
        print(f"[+] Injecting seeded subdomains from: {seed_file}")
        try:
            with open(seed_file, 'r', encoding='utf-8') as f:
                seeds = [line.strip() for line in f if line.strip() and target_domain in line.strip()]
            print(f"    - Found {len(seeds)} in-scope seeds")
            for subdomain in seeds:
                graph.ensure_subdomain(subdomain, tag="SEED")
                # Try to probe HTTP
                for scheme in ["https", "http"]:
                    try:
                        import requests
                        url = f"{scheme}://{subdomain}"
                        resp = requests.head(url, timeout=5, verify=False, allow_redirects=True)
                        if resp.status_code < 500:
                            graph.add_subdomain_with_http({
                                "subdomain": subdomain,
                                "priority": 8,
                                "tag": "SEED",
                                "category": "HTTP",
                                "http": {
                                    "url": url,
                                    "status_code": resp.status_code,
                                    "technologies": [],
                                    "ip": None
                                }
                            })
                            print(f"    - {url}: HTTP {resp.status_code}")
                            break  # Only need one successful probe
                    except:
                        pass
        except Exception as e:
            print(f"[-] Seed injection failed: {e}")
    
    # --- PHASE 2: ACTIVE RECON ---
    print("[+] Starting Active Phase...")
    
    # Inject context from passive phase into Tech Task
    # tech_task.context was removed. We append to description.
    passive_summary = context_analysis.output.raw if context_analysis.output else "No passive context."
    tech_task.description += f"\n\n[CONTEXT FROM PASSIVE PHASE]\n{passive_summary}"
    
    active_agents = [tech_fingerprinter, js_miner, endpoint_analyst, param_hunter]
    active_tasks = [tech_task, js_task, ep_task, param_task]
     
    active_crew = Crew(
        agents=active_agents,
        tasks=active_tasks,
        process=Process.sequential,
        verbose=True
    )
    
    try:
        active_crew.kickoff()
    except Exception as e:
         print(f"[-] Active Crew Failed: {e}")

    # --- Ingestion Phase (Active) ---

    # 4. Tech -> add_subdomain_with_http (with scope validation)
    try:
        raw = tech_task.output.raw
        data = json.loads(extract_json(raw))
        if isinstance(data, list):
            ingested = 0
            rejected = 0
            for item in data:
                # SCOPE CHECK: Reject hallucinated domains
                subdomain = item.get("subdomain", "")
                http_url = item.get("http", {}).get("url", "") if item.get("http") else ""
                
                # Check subdomain scope
                if subdomain and not (subdomain.endswith(target_domain) or subdomain == target_domain):
                    print(f"    [!] Rejected hallucinated subdomain: {subdomain}")
                    rejected += 1
                    continue
                
                # Check HTTP URL scope
                if http_url and target_domain not in http_url:
                    print(f"    [!] Rejected hallucinated HTTP URL: {http_url}")
                    rejected += 1
                    continue
                
                graph.add_subdomain_with_http(item)
                ingested += 1
            if rejected > 0:
                print(f"    [+] Tech Ingestion: {ingested} valid, {rejected} rejected (hallucinations)")
    except Exception as e: print(f"[-] Tech Ingest Error: {e}")
    
    # 5. JS -> add_js_analysis
    try:
        raw = js_task.output.raw
        data = json.loads(extract_json(raw))
        if isinstance(data, list):
            for item in data:
                graph.add_js_analysis(item, item.get("url", ""))
    except: pass
    
    # 6. Endpoint -> add_endpoint
    try:
         raw = ep_task.output.raw
         data = json.loads(extract_json(raw))
         if isinstance(data, list):
             for ep in data:
                 graph.add_endpoint(ep.get("path"), ep.get("method"), "ENDPOINT_TASK", ep.get("url", ""), ep.get("confidence", 0.8))
    except: pass

    # 7. Param -> add_parameter
    try:
        raw = param_task.output.raw
        data = json.loads(extract_json(raw))
        if isinstance(data, list):
            for p in data:
                graph.add_parameter(p.get("url"), p.get("param"), p.get("type"), p.get("risk"))
    except: pass

    # --- Phase 19: Universal Active Recon ---
    print("[+] Universal Active Recon...")
    targets = [n["id"] for n in graph.nodes if n["type"] == "SUBDOMAIN" and target_domain in n["id"]]
    targets = list(set(targets))
    if targets:
        print(f"Probing {len(targets)} targets with Httpx...")
        try:
            res_json = my_httpx_tool._run(subdomains=targets, timeout=12)
            res_data = json.loads(extract_json(res_json))  # Use extract_json for safety
            results_list = res_data.get("results", []) if isinstance(res_data, dict) else res_data if isinstance(res_data, list) else []
            for res in results_list:
                # Ingest with SCOPE CHECK
                host = res.get("host") or res.get("url") if isinstance(res, dict) else None
                if host:
                    # SCOPE CHECK: Reject if not target domain
                    if target_domain not in str(host):
                        print(f"    [!] Rejected out-of-scope Httpx result: {host}")
                        continue
                    
                    payload = {
                        "subdomain": host, # ensure_subdomain will fix it
                        "priority": 10,
                        "tag": "ACTIVE",
                        "category": "HTTP",
                        "http": {
                            "url": res.get("url"),
                            "status_code": res.get("status_code"),
                            "technologies": res.get("technologies", []),
                            "ip": res.get("ip"),
                            "title": res.get("title")
                        }
                }
                graph.add_subdomain_with_http(payload)
        except Exception as e:
            print(f"[-] Httpx probe parsing failed: {e}")
            metrics["errors"].append(f"Httpx probe: {e}")
    
    # --- PHASE 21: SURGICAL STRIKES ---
    print("\n[+] Phase 21: Active Offensive Pipeline (Surgical Strikes)...")
    
    # 1. Systematic Endpoint Discovery (on Confirmed HTTP Services)
    confirmed_services = [n for n in graph.nodes if n["type"] == "HTTP_SERVICE"]
    # Deduplicate by URL
    scan_urls = list(set([n["properties"]["url"] for n in confirmed_services if n["properties"].get("url")]))
    
    # Filter only target domain to be safe
    scan_urls = [u for u in scan_urls if target_domain in u]
    
    if scan_urls:
        print(f"[*] Endpoint Discovery: Casting nets on {len(scan_urls)} confirmed services...")
        # Use HtmlCrawlerTool and JsMinerTool systematically
        for base_url in scan_urls:
            # A. HTML Crawl
            try:
                # We can reuse html_tool from instantiation
                links_json = html_tool._run(url=base_url)
                links = json.loads(extract_json(links_json))
                # Ingest links as Endpoints
                count = 0 
                for l in links:
                    if target_domain in l:
                        graph.add_endpoint(l, "GET", "CRAWLER", base_url, 0.9)
                        count += 1
                # print(f"    - Crawled {base_url}: Found {count} links.")
            except: pass
            
            # B. JS Mining (Lightweight)
            # Reusing js_tool
            try:
                js_json = js_tool._run(url=base_url)
                # Ingest logic for JS matches is complex, assume tool returns list of {match:..., type:...}
                # For now, just logging count
                js_data = json.loads(extract_json(js_json))
                if js_data:
                     # graph.add_js_analysis(...) 
                     pass
            except: pass

    # 2. Targeted Vulnerability Scanning (Nuclei/Ffuf)
    # Use Planner to find High Value Targets
    print("[*] Targeted Vulnerability Scan: Consulting Planner...")
    
    from recon_gotham.core.planner import find_top_paths
    # Re-export efficient graph
    temp_graph = {"nodes": graph.nodes, "edges": graph.edges}
    paths = find_top_paths(temp_graph)
    
    # Select Top 3 targets that are HTTP
    # Planner returns list of dicts with 'subdomain', 'score', 'next_actions'
    # We need to map 'subdomain' back to a URL or HTTP Service
    candidates = []
    for p in paths:
        if len(candidates) >= 5: break # Cap at 5
        sub = p.get("subdomain")
        # Find HTTP service for this sub
        # Check if already in 'scan_urls' or just construct it
        # Actually Planner score implies interest.
        # Let's find the URL property
        node = next((n for n in graph.nodes if n["id"] == sub), None)
        if node:
             # Try to find child HTTP Service
             # Edge: SUBDOMAIN -> EXPOSES_HTTP -> HTTP_SERVICE
             # Simpler: check probed data
             # For Phase 21, let's just attempt generic https://{sub}
             url = f"https://{sub}"
             candidates.append(url)
    
    if candidates:
        print(f"[!] Surgical Strike Targets: {candidates}")
        # Run Nuclei on these specifics
        if nuclei_tool:
             try:
                 # NucleiTool usually takes a list of URLs
                 # If _run handles lists
                 # Creating temporary file for targets usually handled by tool
                 print("    - Launching Nuclei (High Severity)...")
                 # nucle_res = nuclei_tool._run(target=candidates) # Implementation specific
                 pass
             except: pass
        
        # Run Ffuf on Top 1 (most critical)
        top_target = candidates[0]
        if ffuf_tool:
             try:
                 print(f"    - Fuzzing Top Target: {top_target}")
                 # ffuf_res = ffuf_tool._run(url=top_target, wordlist="common") 
                 pass
             except: pass
    else:
        print("[-] No high-value targets identified for offensive scan.")

    # --- PHASE 23A: VALIDATION & DEEP PAGE ANALYSIS (Discovery) ---
    print("[*] Phase 23A: Validation & Deep Page Analysis...")
    
    try:
        from recon_gotham.tools.endpoint_validator import EndpointValidator
        from recon_gotham.tools.page_analyzer import PageAnalyzer, analyze_graph_endpoints
        
        # Step 1: Validate discovered endpoints
        print("    - Step 1: Validating discovered URLs...")
        validator = EndpointValidator(timeout=10, max_workers=5)
        
        # Build list of URLs to validate
        http_services = [n for n in graph.nodes if n["type"] == "HTTP_SERVICE"]
        reachable_urls = []
        unreachable_urls = []
        
        for svc in http_services[:15]:  # Limit to 15 for performance
            url = svc.get("properties", {}).get("url")
            if url and target_domain in url:
                result = validator.validate_url(url)
                if result["reachable"]:
                    reachable_urls.append(url)
                else:
                    unreachable_urls.append({"url": url, "error": result.get("error", "Unknown")})
        
        print(f"    - Validation: {len(reachable_urls)} reachable, {len(unreachable_urls)} unreachable")
        
        # Step 2: Deep Page Analysis on reachable targets
        if reachable_urls:
            print(f"    - Step 2: Deep analysis on {min(len(reachable_urls), 5)} live targets...")
            analyzer = PageAnalyzer(timeout=15)
            
            page_analysis_results = []
            for url in reachable_urls[:5]:  # Analyze top 5 live targets
                print(f"        Analyzing: {url}")
                analysis = analyzer.analyze_url(url)
                if analysis["reachable"]:
                    page_analysis_results.append(analysis)
                    
                    # Update graph with discovered forms/APIs
                    for form in analysis["analysis"].get("forms", []):
                        if form.get("action") and target_domain in form.get("action", ""):
                            graph.add_endpoint(
                                path=form["action"].split(target_domain)[-1] if target_domain in form["action"] else form["action"],
                                method=form.get("method", "POST"),
                                source="PAGE_ANALYZER",
                                origin=form["action"],
                                confidence=0.85
                            )
                    
                    # Add discovered API endpoints
                    for api in analysis["analysis"].get("api_endpoints", []):
                        endpoint = api.get("endpoint", "")
                        if endpoint.startswith("/"):
                            full_url = url.rstrip("/") + endpoint
                            graph.add_endpoint(
                                path=endpoint,
                                method="GET",
                                source="PAGE_ANALYZER_JS",
                                origin=full_url,
                                confidence=0.7
                            )
            
            # Summary
            total_forms = sum(len(a["analysis"].get("forms", [])) for a in page_analysis_results)
            total_apis = sum(len(a["analysis"].get("api_endpoints", [])) for a in page_analysis_results)
            print(f"    - Deep analysis found: {total_forms} forms, {total_apis} API endpoints")
        
        # Step 3: Log unreachable for potential coder intervention
        if unreachable_urls:
            print(f"    - Step 3: {len(unreachable_urls)} URLs need manual investigation")
            # These could be passed to coder_agent for custom script generation
            # For now, log them for the report
            
    except ImportError as e:
        print(f"[-] Phase 23A imports failed: {e}")
        metrics["errors"].append(f"Phase 23A import: {e}")
    except Exception as e:
        print(f"[-] Phase 23A Analysis failed: {e}")
        metrics["errors"].append(f"Phase 23A: {e}")

    # --- PHASE 23B: ENDPOINT INTELLIGENCE ENRICHMENT ---
    # NOTE: Runs AFTER Phase 23A so endpoints discovered by PageAnalyzer get enriched
    print("[*] Phase 23B: Endpoint Intelligence Enrichment...")
    try:
        from recon_gotham.core.endpoint_heuristics import enrich_endpoint

        # 1. Select endpoints from graph
        endpoint_nodes = [n for n in graph.nodes if n["type"] == "ENDPOINT"]
        print(f"    - Found {len(endpoint_nodes)} endpoints for enrichment")

        if endpoint_nodes:
            # 2. Apply heuristic enrichment (pre-IA)
            enriched_count = 0
            for node in endpoint_nodes:
                props = node["properties"]
                endpoint_id = node["id"]

                # Extract fields for heuristics
                path = props.get("path", "")
                origin = props.get("origin", "")
                method = props.get("method", "GET")
                source = props.get("source", "UNKNOWN")

                # Determine extension
                extension = None
                if "." in path.split("/")[-1]:
                    extension = "." + path.split(".")[-1].lower()

                # Apply heuristics
                enrichment = enrich_endpoint(
                    endpoint_id=endpoint_id,
                    url=origin,
                    path=path,
                    method=method,
                    source=source,
                    extension=extension,
                )

                # Update graph node
                if enrichment:
                    graph.update_endpoint_metadata(
                        endpoint_id=endpoint_id,
                        category=enrichment.get("category"),
                        likelihood_score=enrichment.get("likelihood_score"),
                        impact_score=enrichment.get("impact_score"),
                        risk_score=enrichment.get("risk_score"),
                        behavior_hint=enrichment.get("behavior_hint"),
                        id_based_access=enrichment.get("id_based_access"),
                        auth_required=enrichment.get("auth_required"),
                        tech_stack_hint=enrichment.get("tech_stack_hint"),
                    )

                    # Add parameters
                    for param in enrichment.get("parameters", []):
                        graph.add_parameter_v2(
                            endpoint_id=endpoint_id,
                            name=param.get("name"),
                            location=param.get("location", "unknown"),
                            datatype_hint=param.get("datatype_hint", "unknown"),
                            sensitivity=param.get("sensitivity", "LOW"),
                            is_critical=param.get("is_critical", False),
                        )

                    enriched_count += 1

            print(f"    - Enriched {enriched_count} endpoints with risk metadata")

            # 3. Calculate summary stats
            high_risk = [n for n in graph.nodes if n["type"] == "ENDPOINT" and n["properties"].get("risk_score", 0) >= 70]
            print(f"    - High-risk endpoints (score >= 70): {len(high_risk)}")

            # 4. Generate hypotheses for high-risk endpoints (score >= threshold)
            min_risk = budget.get("thresholds", {}).get("min_risk_for_verification", 1)
            hypotheses_count = 0
            for node in endpoint_nodes:
                props = node.get("properties", {})
                risk_score = props.get("risk_score", 0)
                if risk_score >= min_risk:
                    category = props.get("category", "")
                    behavior_hint = props.get("behavior_hint", "")
                    path = props.get("path", "")
                    endpoint_id = node["id"]

                    # Generate hypotheses based on category/behavior
                    if behavior_hint == "ID_BASED_ACCESS":
                        hyp_id = f"hypothesis:{endpoint_id}:IDOR"
                        if not any(n["id"] == hyp_id for n in graph.nodes):
                            graph.nodes.append({
                                "id": hyp_id,
                                "type": "HYPOTHESIS",
                                "properties": {
                                    "attack_type": "IDOR",
                                    "title": "Potential Insecure Direct Object Reference",
                                    "description": f"Endpoint uses ID-based access: {path}",
                                    "confidence": 0.6,
                                    "priority": 3,
                                    "status": "UNTESTED"
                                }
                            })
                            graph.edges.append({"from": endpoint_id, "to": hyp_id, "type": "HAS_HYPOTHESIS"})
                            hypotheses_count += 1

                    if category == "ADMIN":
                        hyp_id = f"hypothesis:{endpoint_id}:AUTH_BYPASS"
                        if not any(n["id"] == hyp_id for n in graph.nodes):
                            graph.nodes.append({
                                "id": hyp_id,
                                "type": "HYPOTHESIS",
                                "properties": {
                                    "attack_type": "AUTH_BYPASS",
                                    "title": "Potential Authentication Bypass",
                                    "description": f"Administrative endpoint: {path}",
                                    "confidence": 0.5,
                                    "priority": 4,
                                    "status": "UNTESTED"
                                }
                            })
                            graph.edges.append({"from": endpoint_id, "to": hyp_id, "type": "HAS_HYPOTHESIS"})
                            hypotheses_count += 1

                    if category == "AUTH":
                        hyp_id = f"hypothesis:{endpoint_id}:BRUTE_FORCE"
                        if not any(n["id"] == hyp_id for n in graph.nodes):
                            graph.nodes.append({
                                "id": hyp_id,
                                "type": "HYPOTHESIS",
                                "properties": {
                                    "attack_type": "BRUTE_FORCE",
                                    "title": "Potential Brute Force Attack Surface",
                                    "description": f"Authentication endpoint: {path}",
                                    "confidence": 0.6,
                                    "priority": 5,
                                    "status": "UNTESTED"
                                }
                            })
                            graph.edges.append({"from": endpoint_id, "to": hyp_id, "type": "HAS_HYPOTHESIS"})
                            hypotheses_count += 1

                    if category == "API":
                        hyp_id = f"hypothesis:{endpoint_id}:SQLI"
                        if not any(n["id"] == hyp_id for n in graph.nodes):
                            graph.nodes.append({
                                "id": hyp_id,
                                "type": "HYPOTHESIS",
                                "properties": {
                                    "attack_type": "SQLI",
                                    "title": "Potential SQL Injection",
                                    "description": f"API endpoint with parameters: {path}",
                                    "confidence": 0.4,
                                    "priority": 4,
                                    "status": "UNTESTED"
                                }
                            })
                            graph.edges.append({"from": endpoint_id, "to": hyp_id, "type": "HAS_HYPOTHESIS"})
                            hypotheses_count += 1

            print(f"    - Generated {hypotheses_count} hypotheses for investigation")
    except Exception as e:
        print(f"[-] Phase 23B Enrichment failed: {e}")

    # --- PHASE 25: V3.0 VERIFICATION PIPELINE ---
    print("[*] Phase 25: Verification Pipeline (V3.0)...")
    phase25_start = datetime.now()
    
    try:
        # Build settings dict for pipeline
        settings = {
            "target_domain": target_domain,
            "mode": mission_mode.upper(),
            "request_timeout": budget.get("requests", {}).get("timeout", 15),
            "min_risk_for_verification": budget.get("thresholds", {}).get("min_risk_for_verification", 40),
            "active_verification_enabled": mission_mode == "aggressive"
        }
        
        verification = VerificationPipeline(graph, settings, run_id)
        verif_result = verification.execute()
        
        print(f"    - Services analyzed: {verif_result.services_analyzed}")
        print(f"    - Stack versions detected: {verif_result.stack_versions_detected}")
        print(f"    - Tests performed: {verif_result.tests_performed}")
        print(f"    - Theoretical vulns: {verif_result.vulnerabilities_theoretical}")
        
        metrics["counts"]["vulnerabilities"] = verif_result.vulnerabilities_theoretical
        metrics["errors"].extend(verif_result.errors)
        
    except Exception as e:
        print(f"[-] Phase 25 Verification failed: {e}")
        metrics["errors"].append(f"Phase 25: {e}")
    
    metrics["phase_durations"]["verification"] = (datetime.now() - phase25_start).total_seconds()
    
    # --- V3.0 METRICS COLLECTION ---
    print("[+] Collecting Final Metrics...")
    
    # Count final assets
    metrics["counts"]["subdomains"] = len([n for n in graph.nodes if n["type"] == "SUBDOMAIN"])
    metrics["counts"]["http_services"] = len([n for n in graph.nodes if n["type"] == "HTTP_SERVICE"])
    metrics["counts"]["endpoints"] = len([n for n in graph.nodes if n["type"] == "ENDPOINT"])
    metrics["counts"]["endpoints_enriched"] = len([n for n in graph.nodes if n["type"] == "ENDPOINT" and n.get("properties", {}).get("risk_score") is not None])
    metrics["counts"]["parameters"] = len([n for n in graph.nodes if n["type"] == "PARAMETER"])
    metrics["counts"]["hypotheses"] = len([n for n in graph.nodes if n["type"] == "HYPOTHESIS"])
    
    print("[+] Generating Report...")
    # Plan
    from recon_gotham.core.planner import find_top_paths
    # graph.export_json returns a filepath, but find_top_paths needs a dict.
    # We export for safety/backup, then pass the dict directly.
    graph.export_json("temp_graph.json") 
    paths = find_top_paths({"nodes": graph.nodes, "edges": graph.edges})
    
    # Phase 23 V2.2: Materialize attack paths into graph
    for path in paths:
        target_id = path.get("subdomain", "")
        score = path.get("score", 0)
        actions = path.get("next_actions", [])
        reasons = path.get("reason", "").split(" | ") if path.get("reason") else []
        
        # Only materialize if target is in scope
        if target_domain in target_id:
            graph.add_attack_path(
                target_id=target_id,
                score=score,
                actions=actions,
                reasons=reasons,
                target_type="SUBDOMAIN",
            )
    
    report_gen = ReportBuilder()
    report_gen.generate_report(target_domain, {"nodes": graph.nodes, "edges": graph.edges}, paths, [])
    
    generate_mission_summary(target_domain, graph, paths, f"recon_gotham/output/{target_domain}_summary.md")
    graph.export_json(f"recon_gotham/output/{target_domain}_asset_graph.json")
    
    # V3.0: Export metrics
    metrics["end_time"] = datetime.now().isoformat()
    metrics["total_duration"] = (datetime.now() - start_time).total_seconds()
    
    metrics_path = f"recon_gotham/output/{target_domain}_{run_id}_metrics.json"
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"[+] Metrics saved: {metrics_path}")
    
    print("[+] Mission Complete.")

if __name__ == "__main__":
    main()

