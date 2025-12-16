"""
CrewAI Tools for Recon Orchestrator
Provides reconnaissance tools for agents to use during missions.
"""
from .subfinder_tool import SubfinderTool, SubfinderInput
from .httpx_tool import HttpxTool, HttpxInput
from .dns_resolver_tool import DnsResolverTool, DNSResolveInput
from .wayback_tool import WaybackTool, WaybackInput
from .js_miner_tool import JsMinerTool, JsMinerInput
from .html_crawler_tool import HtmlCrawlerTool, HtmlCrawlerInput
from .asn_lookup_tool import ASNLookupTool, ASNLookupInput
# P0.6: Script executor for reflection-generated scripts
from .python_script_executor_tool import PythonScriptExecutorTool, PythonScriptInput

# Deep Verification Tools (Lot 2.3)
from .graph_query_tool import GraphQueryTool
from .check_runner_tool import CheckRunnerTool, BatchCheckRunnerTool
from .graph_updater_tool import GraphUpdaterTool, BulkGraphUpdaterTool


def get_all_tools():
    """
    Instantiate and return all reconnaissance tools.
    Returns a dictionary mapping tool names to tool instances.
    """
    return {
        "subfinder_enum": SubfinderTool(),
        "httpx_probe": HttpxTool(),
        "dns_resolver": DnsResolverTool(),
        "wayback_history": WaybackTool(),
        "js_miner": JsMinerTool(),
        "html_crawler": HtmlCrawlerTool(),
        "asn_lookup": ASNLookupTool(),
        "python_script_executor": PythonScriptExecutorTool(),  # P0.6
        # Deep Verification Tools (Lot 2.3)
        "graph_query": GraphQueryTool(),
        "check_runner": CheckRunnerTool(),
        "batch_check_runner": BatchCheckRunnerTool(),
        "graph_updater": GraphUpdaterTool(),
        "bulk_graph_updater": BulkGraphUpdaterTool(),
    }


def get_tools_for_agent(agent_type: str):
    """
    Get tools appropriate for a specific agent type.

    Args:
        agent_type: Type of agent (pathfinder, watchtower, tech_fingerprinter, etc.)

    Returns:
        List of tool instances for the agent
    """
    all_tools = get_all_tools()

    agent_tool_mapping = {
        "pathfinder": ["subfinder_enum"],
        "watchtower": [],  # Analysis agent, no tools needed
        "dns_analyst": ["dns_resolver"],
        "asn_analyst": ["asn_lookup"],
        "tech_fingerprinter": ["httpx_probe"],
        "js_miner": ["js_miner"],
        "endpoint_analyst": ["html_crawler", "wayback_history"],
        "endpoint_intel": [],  # Analysis agent
        "planner": [],  # Planning agent
        "reflector_agent": ["python_script_executor"],  # P0.6: Reflection agent
        "coder_agent": ["python_script_executor"],  # P0.6: Coder agent
        # Deep Verification Agents (Lot 2.2)
        "vuln_triage": ["graph_query"],
        "stack_policy": ["graph_query", "check_runner"],
        "validation_planner": ["graph_query", "check_runner"],
        "evidence_curator": ["graph_query", "graph_updater", "bulk_graph_updater"],
    }

    tool_names = agent_tool_mapping.get(agent_type, [])
    return [all_tools[name] for name in tool_names if name in all_tools]


__all__ = [
    "SubfinderTool", "SubfinderInput",
    "HttpxTool", "HttpxInput",
    "DnsResolverTool", "DNSResolveInput",
    "WaybackTool", "WaybackInput",
    "JsMinerTool", "JsMinerInput",
    "HtmlCrawlerTool", "HtmlCrawlerInput",
    "ASNLookupTool", "ASNLookupInput",
    "PythonScriptExecutorTool", "PythonScriptInput",  # P0.6
    # Deep Verification Tools (Lot 2.3)
    "GraphQueryTool",
    "CheckRunnerTool", "BatchCheckRunnerTool",
    "GraphUpdaterTool", "BulkGraphUpdaterTool",
    "get_all_tools",
    "get_tools_for_agent",
]
