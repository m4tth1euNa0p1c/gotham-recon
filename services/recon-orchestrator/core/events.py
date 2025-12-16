"""
Kafka Event Publisher
Publishes agent and graph events for real-time UI updates
Uses aiokafka with sync wrapper for compatibility
Also persists workflow nodes (AGENT_RUN, TOOL_CALL) to graph-service

Event Envelope v2 Schema:
{
  "schema_version": "v2",
  "event_id": "uuid",
  "event_type": "...",
  "ts": "ISO8601",
  "mission_id": "...",
  "phase": "...",
  "trace_id": "...",
  "span_id": "...",
  "task_id": "...",
  "tool_call_id": "...",
  "producer": "recon-orchestrator",
  "payload": {}
}
"""
import json
import time
import os
import asyncio
import uuid
import hashlib
import httpx
from typing import Optional, Any, List, Dict
from contextvars import ContextVar
from aiokafka import AIOKafkaProducer

# Schema version for event envelope
SCHEMA_VERSION = "v2"
PRODUCER_NAME = "recon-orchestrator"

# Context variables for distributed tracing
_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_span_id: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
_task_id: ContextVar[Optional[str]] = ContextVar("task_id", default=None)
_current_phase: ContextVar[Optional[str]] = ContextVar("current_phase", default=None)

# Topics
TOPIC_LOGS = "logs.recon"
TOPIC_GRAPH = "graph.events"


def generate_event_id() -> str:
    """Generate unique event ID using UUID4"""
    return str(uuid.uuid4())


def generate_trace_id() -> str:
    """Generate new trace ID for mission-level tracing"""
    return f"trc_{uuid.uuid4().hex[:16]}"


def generate_span_id() -> str:
    """Generate new span ID for operation-level tracing"""
    return f"spn_{uuid.uuid4().hex[:12]}"


def set_trace_context(trace_id: str = None, span_id: str = None, task_id: str = None, phase: str = None):
    """Set trace context for current async context"""
    if trace_id:
        _trace_id.set(trace_id)
    if span_id:
        _span_id.set(span_id)
    if task_id:
        _task_id.set(task_id)
    if phase:
        _current_phase.set(phase)


def get_trace_context() -> Dict[str, Optional[str]]:
    """Get current trace context"""
    return {
        "trace_id": _trace_id.get(),
        "span_id": _span_id.get(),
        "task_id": _task_id.get(),
        "phase": _current_phase.get(),
    }


def clear_trace_context():
    """Clear trace context"""
    _trace_id.set(None)
    _span_id.set(None)
    _task_id.set(None)
    _current_phase.set(None)


def make_json_safe(obj: Any) -> Any:
    """
    Recursively convert an object to be JSON-serializable.
    Handles bytes, sets, custom objects, and circular references.

    P0.3: Fix phantom FAILED by ensuring all payloads are serializable.
    """
    seen = set()

    def _convert(o, depth=0):
        if depth > 50:  # Prevent infinite recursion
            return "[max depth exceeded]"

        obj_id = id(o)
        if obj_id in seen:
            return "[circular reference]"

        if o is None:
            return None
        elif isinstance(o, (str, int, float, bool)):
            return o
        elif isinstance(o, bytes):
            try:
                return o.decode('utf-8', errors='replace')
            except:
                return f"[bytes:{len(o)}]"
        elif isinstance(o, (list, tuple)):
            seen.add(obj_id)
            result = [_convert(item, depth + 1) for item in o]
            seen.discard(obj_id)
            return result
        elif isinstance(o, set):
            seen.add(obj_id)
            result = [_convert(item, depth + 1) for item in sorted(o, key=str)]
            seen.discard(obj_id)
            return result
        elif isinstance(o, dict):
            seen.add(obj_id)
            result = {str(k): _convert(v, depth + 1) for k, v in o.items()}
            seen.discard(obj_id)
            return result
        elif hasattr(o, '__dict__'):
            seen.add(obj_id)
            result = {str(k): _convert(v, depth + 1) for k, v in o.__dict__.items() if not k.startswith('_')}
            seen.discard(obj_id)
            return result
        elif hasattr(o, 'isoformat'):  # datetime objects
            return o.isoformat()
        else:
            try:
                return str(o)
            except:
                return f"[unserializable:{type(o).__name__}]"

    return _convert(obj)


def build_event_envelope(
    event_type: str,
    mission_id: str,
    payload: dict,
    phase: str = None,
    tool_call_id: str = None,
) -> dict:
    """
    Build standardized event envelope v2.

    Args:
        event_type: Type of event (e.g., agent_started, NODE_ADDED)
        mission_id: Mission identifier
        payload: Event-specific data
        phase: Current phase (optional, uses context if not provided)
        tool_call_id: Tool call ID for tool-related events

    Returns:
        Complete event envelope ready for Kafka
    """
    ctx = get_trace_context()

    # Ensure payload is JSON-safe
    safe_payload = make_json_safe(payload)

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "event_id": generate_event_id(),
        "event_type": event_type,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "timestamp": time.time(),  # Keep for v1 compatibility
        "mission_id": mission_id,
        "run_id": mission_id,  # Alias for compatibility
        "phase": phase or ctx.get("phase") or "",
        "trace_id": ctx.get("trace_id") or generate_trace_id(),
        "span_id": ctx.get("span_id") or generate_span_id(),
        "task_id": ctx.get("task_id") or "",
        "tool_call_id": tool_call_id or "",
        "producer": PRODUCER_NAME,
        "payload": safe_payload,
    }

    return envelope


# Graph service URL for persisting workflow nodes
GRAPH_SERVICE_URL = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")

# Singleton producer (async)
_producer: Optional[AIOKafkaProducer] = None
_producer_lock = asyncio.Lock()

# HTTP client for graph-service
_http_client: Optional[httpx.AsyncClient] = None


async def _get_http_client() -> httpx.AsyncClient:
    """Get or create HTTP client for graph-service"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


async def _create_workflow_node(mission_id: str, node_type: str, node_id: str, properties: dict) -> bool:
    """Create a workflow node (AGENT_RUN or TOOL_CALL) in graph-service"""
    try:
        client = await _get_http_client()
        response = await client.post(
            f"{GRAPH_SERVICE_URL}/api/v1/nodes",
            json={
                "id": node_id,
                "type": node_type,
                "mission_id": mission_id,
                "properties": properties
            }
        )
        if response.status_code in (200, 201):
            return True
        else:
            print(f"[Events] Failed to create workflow node {node_id}: {response.status_code}")
            return False
    except Exception as e:
        print(f"[Events] Error creating workflow node: {e}")
        return False


def _create_workflow_node_sync(mission_id: str, node_type: str, node_id: str, properties: dict) -> bool:
    """Sync wrapper to create workflow node"""
    try:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(_create_workflow_node(mission_id, node_type, node_id, properties))
        return True  # Fire and forget in async context
    except RuntimeError:
        # No running loop, create one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_create_workflow_node(mission_id, node_type, node_id, properties))
        finally:
            loop.close()


def _get_or_create_event_loop():
    """Get the current event loop or create a new one"""
    try:
        loop = asyncio.get_running_loop()
        return loop, False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop, True


async def _get_producer_async() -> Optional[AIOKafkaProducer]:
    """Get or create Kafka producer singleton (async)"""
    global _producer
    async with _producer_lock:
        if _producer is None:
            bootstrap_servers = os.getenv("KAFKA_BROKERS", "kafka:9092")
            try:
                _producer = AIOKafkaProducer(
                    bootstrap_servers=bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    acks="all",
                )
                await _producer.start()
                print(f"[Kafka] Producer connected to {bootstrap_servers}")
            except Exception as e:
                print(f"[Kafka] Failed to connect: {e}")
                return None
    return _producer


def get_producer() -> Optional[AIOKafkaProducer]:
    """Get the Kafka producer (sync wrapper)"""
    global _producer
    return _producer


async def emit_event_async(
    topic: str,
    event_type: str,
    mission_id: str,
    payload: dict,
    phase: str = None,
    tool_call_id: str = None,
) -> bool:
    """
    Publish an event to Kafka topic (async) using v2 envelope.

    Args:
        topic: Kafka topic (logs.recon or graph.events)
        event_type: Type of event (AGENT_STARTED, NODE_ADDED, etc.)
        mission_id: Mission identifier
        payload: Event data
        phase: Current phase (optional)
        tool_call_id: Tool call ID (optional)

    Returns:
        True if published successfully
    """
    producer = await _get_producer_async()
    if producer is None:
        print(f"[Kafka] No producer available, event dropped: {event_type}")
        return False

    # Build v2 envelope with make_json_safe payload
    event = build_event_envelope(
        event_type=event_type,
        mission_id=mission_id,
        payload=payload,
        phase=phase,
        tool_call_id=tool_call_id,
    )

    try:
        await producer.send_and_wait(topic, event)
        return True
    except Exception as e:
        print(f"[Kafka] Failed to publish event: {e}")
        return False


def emit_event(
    topic: str,
    event_type: str,
    mission_id: str,
    payload: dict,
    phase: str = None,
    tool_call_id: str = None,
) -> bool:
    """
    Publish an event to Kafka topic (sync wrapper) using v2 envelope.

    Args:
        topic: Kafka topic (logs.recon or graph.events)
        event_type: Type of event (AGENT_STARTED, NODE_ADDED, etc.)
        mission_id: Mission identifier
        payload: Event data
        phase: Current phase (optional)
        tool_call_id: Tool call ID (optional)

    Returns:
        True if published successfully
    """
    try:
        loop = asyncio.get_running_loop()
        # If we're in an async context, schedule as task
        future = asyncio.ensure_future(
            emit_event_async(topic, event_type, mission_id, payload, phase, tool_call_id)
        )
        return True  # Fire and forget in async context
    except RuntimeError:
        # No running loop, create one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                emit_event_async(topic, event_type, mission_id, payload, phase, tool_call_id)
            )
        finally:
            loop.close()


def emit_log(mission_id: str, level: str, message: str, phase: str = "", metadata: dict = None):
    """
    Emit a log event

    Args:
        mission_id: Mission identifier
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        phase: Current mission phase
        metadata: Additional metadata
    """
    emit_event(
        TOPIC_LOGS,
        "LOG",
        mission_id,
        {
            "level": level.upper(),
            "message": message,
            "metadata": metadata or {},
        },
        phase=phase,  # Pass phase to envelope
    )


def emit_agent_started(mission_id: str, agent_id: str, task_description: str = "", phase: str = "OSINT"):
    """Emit agent started event - format matches UI workflow store expectations"""
    run_id = f"agent-{agent_id}-{int(time.time() * 1000)}"
    start_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    # Set trace context for this agent run
    set_trace_context(phase=phase, task_id=run_id)

    # Emit to Kafka for real-time SSE with phase in envelope
    emit_event(
        TOPIC_LOGS,
        "agent_started",  # lowercase for UI compatibility
        mission_id,
        {
            "run_id": run_id,
            "id": run_id,
            "agent_id": agent_id,
            "agent_name": agent_id,
            "task": task_description,
            "model": "crewai",
            "start_time": start_time,
        },
        phase=phase,
    )

    # Also persist as AGENT_RUN node in graph-service for historical queries
    _create_workflow_node_sync(
        mission_id,
        "AGENT_RUN",
        run_id,
        {
            "agent_id": agent_id,
            "agent_name": agent_id,
            "task": task_description,
            "phase": phase,
            "model": "crewai",
            "start_time": start_time,
            "status": "running",
        }
    )

    return run_id


def emit_agent_finished(mission_id: str, agent_id: str, result_summary: str = "", duration: float = 0, run_id: str = None):
    """Emit agent finished event - format matches UI workflow store expectations"""
    if not run_id:
        run_id = f"agent-{agent_id}"
    end_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    # Emit to Kafka for real-time SSE
    emit_event(
        TOPIC_LOGS,
        "agent_finished",  # lowercase for UI compatibility
        mission_id,
        {
            "run_id": run_id,
            "id": run_id,
            "agent_id": agent_id,
            "agent_name": agent_id,
            "result": result_summary,
            "status": "success",
            "duration": int(duration * 1000),  # convert to ms
            "end_time": end_time,
        }
    )

    # Update AGENT_RUN node in graph-service with completion data
    _create_workflow_node_sync(
        mission_id,
        "AGENT_RUN",
        run_id,
        {
            "agent_id": agent_id,
            "agent_name": agent_id,
            "result": result_summary,
            "status": "completed",
            "duration": int(duration * 1000),
            "end_time": end_time,
        }
    )


def emit_tool_called(mission_id: str, tool_name: str, agent_id: str = "", input_summary: str = "", phase: str = None):
    """Emit tool called event - format matches UI workflow store expectations"""
    call_id = f"tool-{tool_name}-{int(time.time() * 1000)}"
    start_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    # Emit to Kafka for real-time SSE with tool_call_id in envelope
    emit_event(
        TOPIC_LOGS,
        "tool_called",  # lowercase for UI compatibility
        mission_id,
        {
            "call_id": call_id,
            "id": call_id,
            "tool_name": tool_name,
            "tool": tool_name,
            "agent_id": agent_id,
            "arguments": {"input": input_summary[:200]},
            "start_time": start_time,
        },
        phase=phase,
        tool_call_id=call_id,
    )

    # Also persist as TOOL_CALL node in graph-service for historical queries
    _create_workflow_node_sync(
        mission_id,
        "TOOL_CALL",
        call_id,
        {
            "tool_name": tool_name,
            "tool": tool_name,
            "agent_id": agent_id,
            "args": {"input": input_summary[:200]},
            "start_time": start_time,
            "status": "running",
        }
    )

    return call_id


def emit_tool_result(mission_id: str, tool_name: str, result_count: int = 0, duration: float = 0, call_id: str = None, success: bool = True, phase: str = None):
    """Emit tool finished event - format matches UI workflow store expectations"""
    if not call_id:
        call_id = f"tool-{tool_name}"
    end_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    status = "completed" if success else "error"

    # Emit to Kafka for real-time SSE with tool_call_id in envelope
    emit_event(
        TOPIC_LOGS,
        "tool_finished",  # lowercase for UI compatibility
        mission_id,
        {
            "call_id": call_id,
            "id": call_id,
            "tool_name": tool_name,
            "tool": tool_name,
            "result": {"count": result_count},
            "status": "success" if success else "error",
            "duration": int(duration * 1000),  # convert to ms
            "end_time": end_time,
        },
        phase=phase,
        tool_call_id=call_id,
    )

    # Update TOOL_CALL node in graph-service with completion data
    _create_workflow_node_sync(
        mission_id,
        "TOOL_CALL",
        call_id,
        {
            "tool_name": tool_name,
            "tool": tool_name,
            "result": {"count": result_count},
            "status": status,
            "duration": int(duration * 1000),
            "end_time": end_time,
        }
    )


def emit_node_added(mission_id: str, node_type: str, node_id: str, properties: dict = None):
    """Emit node added event for graph updates"""
    emit_event(
        TOPIC_GRAPH,
        "NODE_ADDED",
        mission_id,
        {
            "node": {
                "id": node_id,
                "type": node_type,
                "properties": properties or {},
            }
        }
    )


def emit_nodes_batch(mission_id: str, nodes: list):
    """Emit batch of nodes added"""
    emit_event(
        TOPIC_GRAPH,
        "NODES_BATCH",
        mission_id,
        {
            "nodes": nodes,
            "count": len(nodes),
        }
    )


def emit_edge_added(mission_id: str, from_node: str, to_node: str, relation: str):
    """Emit edge added event for graph updates"""
    emit_event(
        TOPIC_GRAPH,
        "EDGE_ADDED",
        mission_id,
        {
            "edge": {
                "from_node": from_node,
                "to_node": to_node,
                "relation": relation,
            }
        }
    )


def emit_phase_started(mission_id: str, phase: str, phase_number: int, total_phases: int):
    """Emit phase started event"""
    emit_event(
        TOPIC_LOGS,
        "PHASE_STARTED",
        mission_id,
        {
            "phase": phase,
            "phase_number": phase_number,
            "total_phases": total_phases,
        }
    )


def emit_phase_completed(mission_id: str, phase: str, duration: float, stats: dict = None):
    """Emit phase completed event"""
    emit_event(
        TOPIC_LOGS,
        "PHASE_COMPLETED",
        mission_id,
        {
            "phase": phase,
            "duration_seconds": duration,
            "stats": stats or {},
        }
    )


# P1.1: Failure taxonomy - error codes and stages
class ErrorCode:
    """Standard error codes for failure taxonomy"""
    # Network errors (1xx)
    NETWORK_TIMEOUT = "E101"
    NETWORK_CONNECTION_REFUSED = "E102"
    NETWORK_DNS_FAILURE = "E103"
    NETWORK_SSL_ERROR = "E104"

    # Tool errors (2xx)
    TOOL_NOT_FOUND = "E201"
    TOOL_EXECUTION_FAILED = "E202"
    TOOL_TIMEOUT = "E203"
    TOOL_INVALID_OUTPUT = "E204"

    # Service errors (3xx)
    SERVICE_UNAVAILABLE = "E301"
    SERVICE_RATE_LIMITED = "E302"
    SERVICE_AUTH_FAILED = "E303"

    # Data errors (4xx)
    DATA_PARSE_ERROR = "E401"
    DATA_VALIDATION_ERROR = "E402"
    DATA_NOT_FOUND = "E403"

    # Internal errors (5xx)
    INTERNAL_ERROR = "E501"
    AGENT_ERROR = "E502"
    LLM_ERROR = "E503"
    SERIALIZATION_ERROR = "E504"


class Stage:
    """Mission stages for failure context"""
    INIT = "INIT"
    OSINT = "OSINT"
    ACTIVE_RECON = "ACTIVE_RECON"
    ENDPOINT_INTEL = "ENDPOINT_INTEL"
    VERIFICATION = "VERIFICATION"
    REPORTING = "REPORTING"


def emit_error(
    mission_id: str,
    error_code: str,
    message: str,
    stage: str = "",
    retryable: bool = False,
    recoverable: bool = True,
    details: dict = None,
    phase: str = None,
):
    """
    P1.1: Emit structured error event with failure taxonomy.

    Args:
        mission_id: Mission identifier
        error_code: Error code from ErrorCode class
        message: Human-readable error message
        stage: Current stage (from Stage class)
        retryable: Whether the operation can be retried
        recoverable: Whether the mission can continue
        details: Additional error details (stack trace, context)
        phase: Current phase (optional)
    """
    emit_event(
        TOPIC_LOGS,
        "ERROR",
        mission_id,
        {
            "error_code": error_code,
            "message": message,
            "stage": stage,
            "retryable": retryable,
            "recoverable": recoverable,
            "details": details or {},
            "level": "ERROR",
        },
        phase=phase or stage,
    )


def emit_mission_status(mission_id: str, status: str, message: str = "", error_code: str = None, stage: str = None):
    """
    Emit mission status change event.
    P1.1: Enhanced with optional error_code and stage for failure context.
    """
    payload = {
        "status": status,
        "message": message,
    }

    # Add failure taxonomy fields if this is a failure status
    if status.upper() == "FAILED" and error_code:
        payload["error_code"] = error_code
        payload["stage"] = stage or ""
        payload["retryable"] = False
        payload["recoverable"] = False

    emit_event(
        TOPIC_LOGS,
        "MISSION_STATUS",
        mission_id,
        payload,
        phase=stage,
    )


def emit_llm_call(mission_id: str, model: str, tokens_prompt: int = 0, tokens_response: int = 0):
    """Emit LLM call event for tracking"""
    emit_event(
        TOPIC_LOGS,
        "LLM_CALL",
        mission_id,
        {
            "model": model,
            "tokens_prompt": tokens_prompt,
            "tokens_response": tokens_response,
        }
    )


async def close_producer_async():
    """Close the Kafka producer and HTTP client (async)"""
    global _producer, _http_client
    if _producer:
        await _producer.stop()
        _producer = None
        print("[Kafka] Producer closed")
    if _http_client:
        await _http_client.aclose()
        _http_client = None
        print("[Events] HTTP client closed")


def close_producer():
    """Close the Kafka producer (sync wrapper)"""
    try:
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(close_producer_async())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(close_producer_async())
        finally:
            loop.close()
