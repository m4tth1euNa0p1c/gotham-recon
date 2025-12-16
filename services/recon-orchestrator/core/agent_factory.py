"""
CrewAI Agent Factory
Builds agents from YAML configuration with LLM integration
"""
import yaml
import os
from typing import Dict, Any, Optional, Callable
from crewai import Agent
from .llm_client import get_crewai_llm, get_llm_client


def load_yaml(path: str) -> dict:
    """Load YAML configuration file"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def create_ollama_llm(model_name: str = None):
    """Create LangChain ChatOpenAI instance for Ollama (CrewAI compatible)"""
    return get_crewai_llm()


def build_agents(
    config_path: str = "config/agents.yaml",
    target_domain: str = "",
    tools: Dict[str, Any] = None
) -> Dict[str, Agent]:
    """
    Build CrewAI agents from YAML configuration

    Args:
        config_path: Path to agents.yaml
        target_domain: Target domain to inject into prompts
        tools: Dictionary of tool instances by name

    Returns:
        Dictionary of Agent instances keyed by agent_id
    """
    cfg = load_yaml(config_path)
    llm = create_ollama_llm()
    tools = tools or {}

    agents = {}

    for agent_id, data in cfg.items():
        if not isinstance(data, dict):
            continue

        # Extract agent configuration
        role = data.get("role", agent_id).strip()
        goal = data.get("goal", "").strip()
        backstory = data.get("backstory", "").strip()
        verbose = data.get("verbose", True)

        # Inject target domain into prompts
        if target_domain:
            role = role.replace("{target_domain}", target_domain)
            goal = goal.replace("{target_domain}", target_domain)
            backstory = backstory.replace("{target_domain}", target_domain)

        # Get tools for this agent
        agent_tools = []
        tool_names = data.get("tools", [])
        for tool_name in tool_names:
            if tool_name in tools:
                agent_tools.append(tools[tool_name])

        # Create agent
        agents[agent_id] = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm,
            tools=agent_tools,
            verbose=verbose,
            allow_delegation=data.get("allow_delegation", False),
            max_iter=data.get("max_iter", 15),
            max_rpm=data.get("max_rpm", 10),
        )

        print(f"[AgentFactory] Created agent: {agent_id}")

    return agents


def build_agent(
    agent_id: str,
    role: str,
    goal: str,
    backstory: str,
    tools: list = None,
    verbose: bool = True,
) -> Agent:
    """
    Build a single CrewAI agent programmatically

    Args:
        agent_id: Unique identifier for the agent
        role: Agent's role description
        goal: Agent's goal
        backstory: Agent's backstory/context
        tools: List of tool instances
        verbose: Enable verbose output

    Returns:
        Configured Agent instance
    """
    llm = create_ollama_llm()

    return Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        llm=llm,
        tools=tools or [],
        verbose=verbose,
        allow_delegation=False,
        max_iter=15,
    )


# Pre-defined agent builders for common reconnaissance agents
def build_pathfinder(target_domain: str, tools: list = None) -> Agent:
    """Build the Pathfinder (subdomain enumeration) agent"""
    return build_agent(
        agent_id="pathfinder",
        role="Lead Reconnaissance Orchestrator (Code Name: Pathfinder)",
        goal=f"""Map the entire attack surface of {target_domain} and identify
critical environments (dev, staging, api) to prepare the following attack phases.""",
        backstory="""You are the elite scout. Your job is not to make noise, but to understand the target.
Your strategic objectives are:
1. EXHAUSTIVENESS: Miss no active subdomain using multi-source passive enumeration.
2. CONTEXT AWARENESS: Provide context for each subdomain (test, staging, prod, etc.)
3. CLEAN OUTPUT: Produce structured JSON data for the next agents.
4. RESILIENCE: If a tool fails, report it cleanly without crashing the pipeline.""",
        tools=tools,
    )


def build_watchtower(target_domain: str, tools: list = None) -> Agent:
    """Build the Watchtower (intelligence analysis) agent"""
    return build_agent(
        agent_id="watchtower",
        role="Senior Intelligence Analyst (Code Name: Watchtower)",
        goal=f"""Transform raw reconnaissance data from {target_domain} into actionable intelligence.
Identify high-value targets and assign tags based on their criticality.""",
        backstory="""You are the brain of the operation. Pathfinder sees everything,
but you understand everything. Your role is to filter the noise.
You know that a subdomain like "dev-api" is a goldmine, while "www" is often a fortress.
You analyze naming patterns to infer each server's purpose and assess its risk level.""",
        tools=tools,
    )


def build_dns_analyst(tools: list = None) -> Agent:
    """Build the DNS Analyst agent"""
    return build_agent(
        agent_id="dns_analyst",
        role="DNS Resolution Specialist",
        goal="Resolve DNS records for all confirmed subdomains and extract actionable infrastructure intelligence.",
        backstory="You specialize in DNS reconnaissance and infrastructure mapping.",
        tools=tools,
        verbose=False,
    )


def build_tech_fingerprinter(target_domain: str, tools: list = None) -> Agent:
    """Build the Tech Fingerprinter (StackTrace) agent"""
    return build_agent(
        agent_id="tech_fingerprinter",
        role="Senior Tech Fingerprinter (Code Name: StackTrace)",
        goal=f"""Enrich high-priority subdomains of {target_domain} with technical information:
HTTP status, server/client technologies, IP address, potential WAF/CDN.""",
        backstory="""You are the engineer who transforms a simple list of subdomains into actionable technical profiles.
You use httpx in a precise and targeted manner.
You DO NOT scan everything: only the most critical subdomains provided by Watchtower.""",
        tools=tools,
    )


def build_js_miner(tools: list = None) -> Agent:
    """Build the JS Miner (DeepScript) agent"""
    return build_agent(
        agent_id="js_miner",
        role="JavaScript Intelligence Miner (Code Name: DeepScript)",
        goal="Extract hidden endpoints and secrets from JavaScript files belonging to high-value subdomains.",
        backstory="""You are an expert JS security analyst. You look for API keys, hardcoded credentials,
and internal endpoints in JavaScript files.
You read JavaScript like a novel and reconstruct internal API structures from frontend calls.""",
        tools=tools,
    )


def build_endpoint_intel(target_domain: str, tools: list = None) -> Agent:
    """Build the Endpoint Intelligence agent"""
    return build_agent(
        agent_id="endpoint_intel",
        role="Endpoint Risk Intelligence Analyst (Code Name: RiskAware)",
        goal=f"""Analyze and enrich discovered endpoints on {target_domain} with offensive intelligence:
Confirm or adjust category (API/ADMIN/AUTH/LEGACY), likelihood/impact/risk scores,
and propose attack hypotheses for Red Team prioritization.""",
        backstory="""You are an expert in web application security assessment.
You analyze endpoints to identify attack surfaces, potential vulnerabilities,
and exploitation opportunities.

CRITICAL CONSTRAINTS:
1. You MUST NOT invent new endpoints or domains.
2. You ONLY enrich the endpoints you are given.
3. You stay strictly within the target domain scope.
4. Your output MUST be valid JSON only, no preamble.
5. Maximum 3 hypotheses per endpoint.""",
        tools=tools,
    )


def build_planner(target_domain: str, tools: list = None) -> Agent:
    """Build the Planner (Overwatch) agent"""
    return build_agent(
        agent_id="planner",
        role="Reconnaissance Planner Brain (Code Name: Overwatch)",
        goal=f"""Select the most profitable attack paths from the AssetGraph of {target_domain}
and decide which tools and tasks to run next.""",
        backstory="""You are the strategic brain of the operation.
You DO NOT invent assets or subdomains.
You only reason on the validated Graph provided by your field agents.
Your job is to connect the dots: A high-priority subdomain + An exposed API + A sensitive JS file = Critical Attack Vector.""",
        tools=tools,
    )


# ============================================================================
# DEEP VERIFICATION AGENTS (Lot 2.2)
# 4 specialized agents for vulnerability validation and evidence collection
# ============================================================================

def build_vuln_triage(target_domain: str, tools: list = None) -> Agent:
    """
    Build the VulnTriage agent (Step 1 of Deep Verification).
    Prioritizes targets from the graph for verification.
    """
    return build_agent(
        agent_id="vuln_triage",
        role="Vulnerability Triage Specialist (Code Name: Triage)",
        goal=f"""Identify and prioritize THEORETICAL/LIKELY vulnerabilities in the {target_domain} graph
that should be verified with active checks. Output a ranked list of targets for validation.""",
        backstory="""You are the vulnerability triage expert.
You analyze the knowledge graph to find vulnerabilities that are still THEORETICAL or LIKELY
and determine which ones should be actively verified.

Your prioritization criteria:
1. CVSS score / risk_score - higher scores first
2. Attack complexity - easier attacks first
3. Target accessibility - reachable HTTP services first
4. Evidence gaps - vulns with missing evidence need verification

You produce a JSON list of targets ranked by priority.
Each target includes: target_id, vuln_id, risk_score, reason, check_modules_suggested.""",
        tools=tools,
    )


def build_stack_policy(target_domain: str, tools: list = None) -> Agent:
    """
    Build the StackPolicy agent (Step 2 of Deep Verification).
    Maps technology stacks to appropriate check modules.
    """
    return build_agent(
        agent_id="stack_policy",
        role="Technology Stack Policy Mapper (Code Name: StackMap)",
        goal=f"""For each target in {target_domain}, map its technology stack to the appropriate
check modules from the registry. Ensure ROE compliance and proper module selection.""",
        backstory="""You are the technology stack expert.
You understand that different tech stacks require different verification approaches.

Your knowledge:
- PHP: Check for LFI, RCE, config exposure
- Node.js/Express: Check for prototype pollution, SSRF
- Java/Spring: Check for deserialization, XXE
- .NET: Check for viewstate issues, path traversal
- WordPress: Check for plugin vulns, xmlrpc abuse
- Generic: Security headers, server disclosure, config files

You map each target's detected stack to appropriate check modules.
You also consider ROE mode (STEALTH/BALANCED/AGGRESSIVE) when selecting modules.
Output a JSON mapping of target_id -> [check_module_ids].""",
        tools=tools,
    )


def build_validation_planner(target_domain: str, tools: list = None) -> Agent:
    """
    Build the ValidationPlanner agent (Step 3 of Deep Verification).
    Creates an execution plan for verification checks.
    """
    return build_agent(
        agent_id="validation_planner",
        role="Verification Plan Orchestrator (Code Name: Validator)",
        goal=f"""Create a comprehensive verification plan for {target_domain} that sequences
check module executions while respecting ROE constraints and optimizing for coverage.""",
        backstory="""You are the verification orchestrator.
You take the triage priorities and stack mappings to create an execution plan.

Your planning principles:
1. IDEMPOTENCY: Same plan inputs = same plan outputs (use deterministic ordering)
2. ROE COMPLIANCE: Respect mode restrictions (STEALTH = GET only, etc.)
3. RATE LIMITING: Space out checks to avoid detection
4. DEPENDENCY ORDERING: Some checks depend on others (e.g., auth before admin)
5. PARALLEL SAFETY: Group independent checks for parallel execution

Your output is a VerificationPlan JSON:
- plan_id: Deterministic hash of inputs
- targets: Ordered list of targets with priority
- assignments: Module-to-target mappings with execution order
- estimated_duration: Based on module timeouts
- roe_mode: The active ROE mode""",
        tools=tools,
    )


def build_evidence_curator(target_domain: str, tools: list = None) -> Agent:
    """
    Build the EvidenceCurator agent (Step 4 of Deep Verification).
    Reviews and stores evidence from check results.
    """
    return build_agent(
        agent_id="evidence_curator",
        role="Evidence Curator and Status Arbiter (Code Name: Curator)",
        goal=f"""Review check results for {target_domain}, curate evidence with proper hashing,
determine final vulnerability status, and update the graph with proof.""",
        backstory="""You are the evidence curator and final arbiter of vulnerability status.
You review all check results and make the final determination.

Your responsibilities:
1. EVIDENCE VALIDATION: Verify evidence hash integrity
2. SECRET REDACTION: Ensure no sensitive data in stored evidence
3. STATUS DETERMINATION: Based on proof quality:
   - CONFIRMED: Has verified evidence with matching proof patterns
   - LIKELY: Has partial evidence, needs more validation
   - FALSE_POSITIVE: Checked but not exploitable
   - MITIGATED: Was vulnerable but now fixed
4. GRAPH UPDATE: Write final status and evidence to graph
5. DEDUPLICATION: Use evidence hashes to prevent duplicate storage

Your output includes:
- Updated vulnerability statuses
- Curated evidence records with hashes
- Summary of confirmed vs rejected findings""",
        tools=tools,
    )
