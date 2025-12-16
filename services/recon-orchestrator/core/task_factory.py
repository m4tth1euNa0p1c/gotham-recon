"""
CrewAI Task Factory
Builds tasks from YAML configuration
"""
import yaml
from typing import Dict, List, Optional
from crewai import Task, Agent


def load_yaml(path: str) -> dict:
    """Load YAML configuration file"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_tasks(
    agents: Dict[str, Agent],
    config_path: str = "config/tasks.yaml",
    target_domain: str = "",
) -> Dict[str, Task]:
    """
    Build CrewAI tasks from YAML configuration

    Args:
        agents: Dictionary of Agent instances keyed by agent_id
        config_path: Path to tasks.yaml
        target_domain: Target domain to inject into prompts

    Returns:
        Dictionary of Task instances keyed by task_id
    """
    cfg = load_yaml(config_path)
    tasks = {}

    for task_id, data in cfg.items():
        if not isinstance(data, dict):
            continue

        agent_id = data.get("agent")
        if agent_id not in agents:
            print(f"[TaskFactory] Warning: Agent '{agent_id}' not found for task '{task_id}'")
            continue

        description = data.get("description", "").strip()
        expected_output = data.get("expected_output", "").strip()

        # Inject target domain
        if target_domain:
            description = description.replace("{target_domain}", target_domain)
            expected_output = expected_output.replace("{target_domain}", target_domain)

        tasks[task_id] = Task(
            description=description,
            agent=agents[agent_id],
            expected_output=expected_output,
        )

        print(f"[TaskFactory] Created task: {task_id} -> {agent_id}")

    return tasks


def build_task(
    description: str,
    agent: Agent,
    expected_output: str = "",
    context: List[Task] = None,
) -> Task:
    """
    Build a single CrewAI task programmatically

    Args:
        description: Task description/instructions
        agent: Agent to assign the task to
        expected_output: Expected output format
        context: List of tasks providing context

    Returns:
        Configured Task instance
    """
    return Task(
        description=description,
        agent=agent,
        expected_output=expected_output,
        context=context or [],
    )


# Pre-defined task builders for reconnaissance phases
def build_enumeration_task(pathfinder: Agent, target_domain: str) -> Task:
    """Build subdomain enumeration task"""
    return build_task(
        description=f"""Perform advanced passive reconnaissance on {target_domain}.

Operational steps:
1. Launch the Subfinder subdomain scanner with '-all' mode.
2. Disable smart filtering to capture all assets.
3. Limit results to a maximum of 50 items.
4. Return the results as STRICT JSON.

CRITICAL:
- If no subdomains found, return [].
- DO NOT INVENT subdomains.
- Return ONLY the JSON array from the tool.""",
        agent=pathfinder,
        expected_output="""A STRICT JSON array of discovered subdomains.
Example: ["sub1.domain.com", "sub2.domain.com"]
If none found, return: []""",
    )


def build_analysis_task(watchtower: Agent, target_domain: str, enumeration_task: Task = None) -> Task:
    """Build intelligence analysis task"""
    context = [enumeration_task] if enumeration_task else []
    return build_task(
        description=f"""Analyze the subdomain enumeration results for {target_domain}.

CRITICAL ANTI-HALLUCINATION RULES:
1. Use STRICTLY the subdomains from the enumeration task output.
2. If the list is empty, state it explicitly.
3. DO NOT guess subdomains that "should" exist.

For each CONFIRMED subdomain:
1. Infer its context (STAGING, PROD, VPN, ADMIN)
2. Assign attack priority (1-10)
3. Suggest technical category (APP_BACKEND, AUTH_PORTAL, STATIC_ASSET)
4. Suggest next action (nuclei_scan, httpx_probe)""",
        agent=watchtower,
        expected_output="""STRICT JSON array:
[
  {
    "subdomain": "api-dev.domain.com",
    "tag": "DEV_API",
    "priority": 9,
    "reason": "Exposed development API",
    "category": "APP_BACKEND",
    "next_action": "nuclei_scan"
  }
]""",
        context=context,
    )


def build_dns_task(dns_analyst: Agent, analysis_task: Task = None) -> Task:
    """Build DNS enrichment task"""
    context = [analysis_task] if analysis_task else []
    return build_task(
        description="""Resolve DNS records for all confirmed subdomains.

Steps:
1. Extract all 'subdomain' strings from the analysis task output.
2. Call the dns_resolver tool ONCE with this list.
3. Return the tool's output AS IS (STRICT JSON array).

Do NOT loop yourself. The tool handles the loop.""",
        agent=dns_analyst,
        expected_output="STRICT JSON array from valid tool output.",
        context=context,
    )


def build_fingerprint_task(tech_fingerprinter: Agent, analysis_task: Task = None) -> Task:
    """Build HTTP fingerprinting task"""
    context = [analysis_task] if analysis_task else []
    return build_task(
        description="""Fingerprint HTTP services on high-priority subdomains.

LOGIC:
1. FILTER: Keep subdomains where priority >= 7.
2. ACTION: Run httpx_probe on filtered subdomains.
3. FORMAT: Return results as RAW JSON ARRAY.

CRITICAL INSTRUCTIONS:
- DO NOT OUTPUT ANY TEXT, THOUGHTS, OR EXPLANATIONS.
- START OUTPUT WITH "[" AND END WITH "]".
- IF NO SUBDOMAINS MATCH, RETURN "[]".
- YOUR ENTIRE RESPONSE MUST BE VALID JSON.""",
        agent=tech_fingerprinter,
        expected_output="""A STRICT JSON array of enriched subdomains with HTTP data.
NO additional text.""",
        context=context,
    )


def build_js_mining_task(js_miner: Agent, fingerprint_task: Task = None) -> Task:
    """Build JavaScript mining task"""
    context = [fingerprint_task] if fingerprint_task else []
    return build_task(
        description="""Extract endpoints and secrets from JavaScript files.

Steps:
1. Extract HTTP service URLs from fingerprint task where http.url != null.
2. CHECK: If list is EMPTY, return "[]" immediately.
3. Call js_miner tool with the list of URLs.
4. Return STRICTLY a JSON array merging all results.

IMPORTANT:
- IF NO URLs: Return "[]". DO NOT call tool with empty list.
- NO extra text outside the final JSON output.""",
        agent=js_miner,
        expected_output="""STRICT JSON array containing JS analysis for each URL:
[
  {
    "url": "https://...",
    "js": {
      "js_files": ["..."],
      "endpoints": [{"path": "...", "method": "...", "source_js": "..."}],
      "secrets": [{"value": "...", "kind": "...", "source_js": "..."}]
    }
  }
]""",
        context=context,
    )


def build_endpoint_intel_task(endpoint_intel: Agent, target_domain: str, context_tasks: List[Task] = None) -> Task:
    """Build endpoint intelligence enrichment task"""
    # Filter out None values from context
    context = [t for t in (context_tasks or []) if t is not None]
    return build_task(
        description=f"""Analyze and enrich discovered endpoints for {target_domain}.

YOUR MISSION:
1. CONFIRM or ADJUST the 'category' (API, ADMIN, AUTH, PUBLIC, STATIC, LEGACY, HEALTHCHECK).
2. CONFIRM or ADJUST the 'likelihood_score' (0-10) and 'impact_score' (0-10).
3. COMPUTE the 'risk_score' (0-100) based on likelihood × impact.
4. SET 'auth_required' (true/false) if you can deduce it.
5. SET 'tech_stack_hint' if identifiable (e.g., "PHP", "Rails", "Node").
6. PROPOSE 0-3 attack hypotheses for high-risk endpoints.

CRITICAL CONSTRAINTS:
- You MUST NOT invent new endpoints or domains.
- You ONLY enrich the endpoints provided in the input.
- Maximum 3 hypotheses per endpoint.
- Scores must be: likelihood 0-10, impact 0-10, risk 0-100.

ATTACK_TYPE VALUES:
XXE, SQLI, XSS, IDOR, BOLA, AUTH_BYPASS, RATE_LIMIT, RCE, SSRF, LFI, RFI, CSRF, OPEN_REDIRECT, INFO_DISCLOSURE""",
        agent=endpoint_intel,
        expected_output="""STRICT JSON object:
{
  "endpoints": [
    {
      "endpoint_id": "endpoint:http:...",
      "category": "ADMIN",
      "likelihood_score": 7,
      "impact_score": 9,
      "risk_score": 63,
      "auth_required": true,
      "tech_stack_hint": "PHP",
      "hypotheses": [
        {"title": "...", "attack_type": "AUTH_BYPASS", "confidence": 0.7, "priority": 4}
      ]
    }
  ]
}""",
        context=context,
    )


def build_planning_task(planner: Agent, target_domain: str, context_tasks: List[Task] = None) -> Task:
    """Build attack planning task"""
    # Filter out None values from context
    context = [t for t in (context_tasks or []) if t is not None]
    return build_task(
        description=f"""Generate attack plan for {target_domain} based on reconnaissance data.

1. USE the provided context which contains all discovered assets.
2. For each high-value path, ANALYZE why it is interesting.
3. PROPOSE the next technical actions.

POSSIBLE ACTIONS:
- 'nuclei_scan': If the subdomain exposes a known tech stack.
- 'ffuf_api_fuzz': If an API endpoint is discovered.
- 'parameter_mining': If a complex JS file is found.
- 'manual_review': If a secret is leaked or critical infra found.

CRITICAL RULES:
- Do NOT invent subdomains. Only use the ones in the context.
- INCLUDE high-value targets EVEN IF they have no known HTTP URL.
- Return STRICT JSON.""",
        agent=planner,
        expected_output="""A STRICT JSON list of actionable attack plans:
[
  {
    "subdomain": "dev.domain.com",
    "score": 85,
    "reason": "Development API with Auth JS",
    "next_actions": ["nuclei_scan", "ffuf_api_fuzz"]
  }
]""",
        context=context,
    )


# ============================================================================
# DEEP VERIFICATION TASKS (Lot 2.2)
# Tasks for the 4 verification agents
# ============================================================================

def build_vuln_triage_task(
    vuln_triage: Agent,
    target_domain: str,
    vulnerabilities: List[dict] = None,
    mode: str = "BALANCED"
) -> Task:
    """Build vulnerability triage task for prioritizing verification targets."""
    vuln_summary = "No vulnerabilities provided in context."
    if vulnerabilities:
        vuln_summary = f"{len(vulnerabilities)} vulnerabilities to triage:\n"
        for v in vulnerabilities[:10]:
            vuln_summary += f"- {v.get('id', 'N/A')}: {v.get('attack_type', 'UNKNOWN')} on {v.get('target_id', 'N/A')} (status: {v.get('status', 'UNKNOWN')})\n"

    return build_task(
        description=f"""Triage vulnerabilities for {target_domain} and prioritize for verification.

ROE MODE: {mode}

VULNERABILITY CONTEXT:
{vuln_summary}

YOUR TASK:
1. Query the graph for vulnerabilities with status THEORETICAL or LIKELY.
2. Rank them by verification priority based on:
   - Risk score (higher = more urgent)
   - Attack complexity (simpler = faster ROI)
   - Target reachability (HTTP service accessible)
3. For each target, suggest appropriate check modules.
4. Output max 10 targets for verification in this batch.

CRITICAL:
- DO NOT invent vulnerabilities. Only work with graph data.
- Respect ROE mode restrictions.
- Output STRICT JSON.""",
        agent=vuln_triage,
        expected_output="""STRICT JSON array of prioritized targets:
[
  {
    "target_id": "endpoint:https://api.example.com/admin",
    "vuln_id": "vuln-abc123",
    "attack_type": "AUTH_BYPASS",
    "risk_score": 85,
    "priority": 1,
    "reason": "Admin endpoint with no auth check detected",
    "suggested_modules": ["security-headers-01", "config-exposure-01"]
  }
]""",
    )


def build_stack_policy_task(
    stack_policy: Agent,
    target_domain: str,
    targets: List[dict] = None,
    available_modules: List[str] = None,
    mode: str = "BALANCED"
) -> Task:
    """Build stack policy mapping task."""
    targets_summary = "No targets provided."
    if targets:
        targets_summary = f"{len(targets)} targets to map:\n"
        for t in targets[:10]:
            targets_summary += f"- {t.get('target_id', 'N/A')}: stack={t.get('tech_stack', 'unknown')}\n"

    modules_list = ", ".join(available_modules or ["security-headers-01", "server-info-disclosure-01", "config-exposure-01"])

    return build_task(
        description=f"""Map technology stacks to check modules for {target_domain}.

ROE MODE: {mode}
AVAILABLE MODULES: {modules_list}

TARGETS:
{targets_summary}

YOUR TASK:
1. Analyze each target's detected technology stack.
2. Map each stack to appropriate check modules from the registry.
3. Consider ROE restrictions:
   - STEALTH: Only passive checks (GET requests, header analysis)
   - BALANCED: Include active checks (POST with safe payloads)
   - AGGRESSIVE: Include intrusive checks
4. Output module assignments for each target.

CRITICAL:
- Only use modules from the AVAILABLE MODULES list.
- Match module capabilities to target vulnerabilities.
- Output STRICT JSON.""",
        agent=stack_policy,
        expected_output="""STRICT JSON mapping:
{
  "mappings": [
    {
      "target_id": "endpoint:https://api.example.com/admin",
      "tech_stack": "PHP/Apache",
      "assigned_modules": ["security-headers-01", "config-exposure-01"],
      "roe_compliant": true,
      "reason": "PHP stack → check for config exposure and security headers"
    }
  ]
}""",
    )


def build_validation_plan_task(
    validation_planner: Agent,
    target_domain: str,
    triage_results: dict = None,
    stack_mappings: dict = None,
    mode: str = "BALANCED"
) -> Task:
    """Build verification plan creation task."""
    return build_task(
        description=f"""Create a verification execution plan for {target_domain}.

ROE MODE: {mode}

TRIAGE RESULTS:
{triage_results or 'Use graph_query tool to get triage data'}

STACK MAPPINGS:
{stack_mappings or 'Use previous task context'}

YOUR TASK:
1. Combine triage priorities with stack module mappings.
2. Create an ordered execution plan with:
   - Deterministic plan_id (hash of inputs)
   - Ordered target list by priority
   - Module assignments with execution order
   - Estimated total duration
3. Group independent checks for parallel execution.
4. Ensure ROE compliance throughout.

CRITICAL:
- Plan must be IDEMPOTENT (same inputs = same plan_id).
- Respect rate limits between checks.
- Output STRICT JSON VerificationPlan.""",
        agent=validation_planner,
        expected_output="""STRICT JSON VerificationPlan:
{
  "plan_id": "plan-abc123def456",
  "mission_id": "mission-xyz",
  "roe_mode": "BALANCED",
  "estimated_duration_seconds": 120,
  "targets": [
    {
      "target_id": "endpoint:https://api.example.com/admin",
      "target_url": "https://api.example.com/admin",
      "target_type": "HTTP_SERVICE",
      "risk_score": 85,
      "priority": 1,
      "reason": "High-risk admin endpoint"
    }
  ],
  "assignments": [
    {
      "target_id": "endpoint:https://api.example.com/admin",
      "module_id": "security-headers-01",
      "order": 1
    }
  ]
}""",
    )


def build_evidence_curation_task(
    evidence_curator: Agent,
    target_domain: str,
    check_results: List[dict] = None,
) -> Task:
    """Build evidence curation and status determination task."""
    results_summary = "No check results provided."
    if check_results:
        results_summary = f"{len(check_results)} check results to curate:\n"
        for r in check_results[:10]:
            results_summary += f"- {r.get('module_id', 'N/A')}: status={r.get('status', 'UNKNOWN')}, evidence_count={len(r.get('evidence', []))}\n"

    return build_task(
        description=f"""Curate evidence and determine vulnerability statuses for {target_domain}.

CHECK RESULTS:
{results_summary}

YOUR TASK:
1. Review each check result's evidence.
2. Validate evidence hashes for integrity.
3. Apply secret redaction to any sensitive data.
4. Determine final vulnerability status:
   - CONFIRMED: Strong evidence, proof pattern matched
   - LIKELY: Partial evidence, needs more validation
   - FALSE_POSITIVE: Checked but not exploitable
   - MITIGATED: Was vulnerable but now fixed
5. Update the graph with final statuses and evidence.
6. Deduplicate evidence by hash.

CRITICAL:
- NEVER store unredacted secrets.
- Evidence must have valid SHA256 hashes.
- Update graph using graph_updater tool.
- Output summary of status changes.""",
        agent=evidence_curator,
        expected_output="""STRICT JSON curation result:
{
  "curated": [
    {
      "vuln_id": "vuln-abc123",
      "target_id": "endpoint:https://api.example.com/admin",
      "old_status": "THEORETICAL",
      "new_status": "CONFIRMED",
      "evidence_count": 2,
      "evidence_hashes": ["abc123...", "def456..."],
      "reason": "Security headers missing confirmed via HTTP response"
    }
  ],
  "summary": {
    "total_checked": 5,
    "confirmed": 2,
    "likely": 1,
    "false_positive": 2,
    "graph_updates": 3
  }
}""",
    )
