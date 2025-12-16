# Core modules for Recon Orchestrator
from .llm_client import LLMClient, get_llm_client, get_crewai_llm, CREWAI_LLM_AVAILABLE
from .events import (
    emit_event, get_producer, emit_log, emit_agent_started, emit_agent_finished,
    emit_phase_started, emit_phase_completed, emit_mission_status,
    emit_node_added, emit_nodes_batch, emit_llm_call, emit_tool_called, emit_tool_result
)

# CrewAI is optional - only import if available
CREWAI_AVAILABLE = False
try:
    from .agent_factory import (
        build_agents, build_agent, build_pathfinder, build_watchtower,
        build_dns_analyst, build_tech_fingerprinter, build_js_miner,
        build_endpoint_intel, build_planner, create_ollama_llm
    )
    from .task_factory import (
        build_tasks, build_task, build_enumeration_task, build_analysis_task,
        build_dns_task, build_fingerprint_task, build_js_mining_task,
        build_endpoint_intel_task, build_planning_task
    )
    from .crew_runner import run_crewai_mission, CrewMissionRunner
    CREWAI_AVAILABLE = True
except ImportError as e:
    print(f"[Core] CrewAI not available: {e}")

__all__ = [
    # LLM Client
    "LLMClient", "get_llm_client", "get_crewai_llm", "CREWAI_LLM_AVAILABLE",
    # Events
    "emit_event", "get_producer", "emit_log",
    "emit_agent_started", "emit_agent_finished",
    "emit_phase_started", "emit_phase_completed", "emit_mission_status",
    "emit_node_added", "emit_nodes_batch", "emit_llm_call",
    "emit_tool_called", "emit_tool_result",
    # CrewAI
    "CREWAI_AVAILABLE",
]
