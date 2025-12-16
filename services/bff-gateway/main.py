"""
BFF Gateway - GraphQL API Gateway for Gotham UI
Aggregates data from backend services, handles caching
Supports GraphQL subscriptions for real-time updates

P0.5: Implements ring buffer for event replay and Last-Event-ID support
- Ring buffer stores last N events per mission for replay on reconnect
- SSE endpoint supports Last-Event-ID header for resuming from last seen event
- On reconnect, sends snapshot + missed deltas
"""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL
from typing import Optional, List, Dict, Any, AsyncGenerator
from enum import Enum
from datetime import datetime
from collections import deque
import httpx
import structlog
import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager

# Kafka consumer (aiokafka)
try:
    from aiokafka import AIOKafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    AIOKafkaConsumer = None

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Configuration
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://recon-orchestrator:8000")
GRAPH_SERVICE_URL = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
KAFKA_TOPIC_EVENTS = "graph.events"
KAFKA_TOPIC_LOGS = "logs.recon"

# Global Kafka consumer
kafka_consumer: Optional[AIOKafkaConsumer] = None

# Event queues per subscription (mission_id -> list of queues)
event_queues: Dict[str, List[asyncio.Queue]] = {}
log_queues: Dict[str, List[asyncio.Queue]] = {}

# P0.5: Ring buffer for event replay on reconnect
# Stores last N events per mission with unique event IDs
RING_BUFFER_SIZE = 1000  # Store last 1000 events per mission
event_ring_buffers: Dict[str, deque] = {}  # mission_id -> deque of events
event_id_counter: int = 0  # Global event counter for unique IDs

# P0.2: Event ID dedup - track seen event_ids to prevent duplicates
# Use combined set (for O(1) lookup) + deque (for LRU eviction) per mission
SEEN_EVENT_IDS_SIZE = 5000  # Track last 5000 event IDs per mission
seen_event_ids_set: Dict[str, set] = {}  # mission_id -> set of event_ids (O(1) lookup)
seen_event_ids_order: Dict[str, deque] = {}  # mission_id -> deque for LRU eviction


def is_event_duplicate(run_id: str, event_id: str) -> bool:
    """Check if event_id is duplicate and track it (P0.2)"""
    if not event_id or not run_id:
        return False

    if run_id not in seen_event_ids_set:
        seen_event_ids_set[run_id] = set()
        seen_event_ids_order[run_id] = deque(maxlen=SEEN_EVENT_IDS_SIZE)

    if event_id in seen_event_ids_set[run_id]:
        return True  # Duplicate

    # Add to tracking
    seen_event_ids_set[run_id].add(event_id)

    # Handle LRU eviction
    if len(seen_event_ids_order[run_id]) >= SEEN_EVENT_IDS_SIZE:
        evicted_id = seen_event_ids_order[run_id][0]  # Oldest
        seen_event_ids_set[run_id].discard(evicted_id)

    seen_event_ids_order[run_id].append(event_id)
    return False


def generate_sse_event_id() -> str:
    """Generate unique SSE event ID for Last-Event-ID tracking"""
    global event_id_counter
    event_id_counter += 1
    return f"evt_{event_id_counter}_{uuid.uuid4().hex[:8]}"


def add_event_to_ring_buffer(mission_id: str, event: dict) -> str:
    """Add event to ring buffer with unique SSE event ID"""
    if mission_id not in event_ring_buffers:
        event_ring_buffers[mission_id] = deque(maxlen=RING_BUFFER_SIZE)

    sse_event_id = generate_sse_event_id()
    event_with_id = {
        **event,
        "sse_event_id": sse_event_id
    }
    event_ring_buffers[mission_id].append(event_with_id)
    return sse_event_id


def get_events_after(mission_id: str, last_event_id: Optional[str]) -> List[dict]:
    """Get all events after the specified Last-Event-ID for replay"""
    if mission_id not in event_ring_buffers:
        return []

    if not last_event_id:
        # No last event ID - return all buffered events
        return list(event_ring_buffers[mission_id])

    # Find events after the last_event_id
    events = list(event_ring_buffers[mission_id])
    found_index = -1
    for i, event in enumerate(events):
        if event.get("sse_event_id") == last_event_id:
            found_index = i
            break

    if found_index >= 0:
        # Return events after the found index
        return events[found_index + 1:]
    else:
        # Last event ID not found in buffer - return all (might have been evicted)
        return events


async def get_snapshot_for_mission(mission_id: str) -> Optional[dict]:
    """Fetch current graph snapshot from graph-service"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{GRAPH_SERVICE_URL}/api/v1/missions/{mission_id}/export")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning("snapshot_fetch_failed", mission_id=mission_id, error=str(e))
    return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle"""
    global kafka_consumer

    # Start Kafka consumer task
    if KAFKA_AVAILABLE:
        asyncio.create_task(consume_kafka_events())

    yield

    # Cleanup
    if kafka_consumer:
        await kafka_consumer.stop()

async def consume_kafka_events():
    """Background task to consume Kafka events and dispatch to subscribers"""
    global kafka_consumer

    retry_count = 0
    max_retries = 10

    while retry_count < max_retries:
        try:
            kafka_consumer = AIOKafkaConsumer(
                KAFKA_TOPIC_EVENTS,
                KAFKA_TOPIC_LOGS,
                bootstrap_servers=KAFKA_BROKERS,
                group_id="bff-gateway-sse",
                auto_offset_reset="latest",
                value_deserializer=lambda v: json.loads(v.decode('utf-8'))
            )
            await kafka_consumer.start()
            logger.info("kafka_consumer_started", topics=[KAFKA_TOPIC_EVENTS, KAFKA_TOPIC_LOGS])
            retry_count = 0  # Reset on successful connection

            async for msg in kafka_consumer:
                event = msg.value

                # Support both run_id and mission_id keys
                run_id = event.get("run_id") or event.get("mission_id") or ""

                # Add run_id to event if missing (for consistency)
                if "run_id" not in event and "mission_id" in event:
                    event["run_id"] = event["mission_id"]

                # P0.2: Dedup by event_id from envelope v2
                event_id = event.get("event_id")
                if is_event_duplicate(run_id, event_id):
                    logger.debug("kafka_event_duplicate_skipped", run_id=run_id, event_id=event_id)
                    continue  # Skip duplicate event

                logger.debug(
                    "kafka_message_received",
                    topic=msg.topic,
                    run_id=run_id,
                    event_type=event.get("event_type", "unknown"),
                    event_id=event_id,
                    has_subscribers_events=run_id in event_queues,
                    has_subscribers_logs=run_id in log_queues
                )

                # P0.5: Add event to ring buffer for replay on reconnect
                if run_id:
                    sse_event_id = add_event_to_ring_buffer(run_id, event)
                    event["sse_event_id"] = sse_event_id

                if msg.topic == KAFKA_TOPIC_EVENTS:
                    # Dispatch to graph event subscribers
                    if run_id in event_queues:
                        for queue in event_queues[run_id]:
                            await queue.put(event)
                        logger.debug("kafka_event_dispatched", run_id=run_id, queue_count=len(event_queues[run_id]))
                elif msg.topic == KAFKA_TOPIC_LOGS:
                    # Dispatch to log subscribers
                    if run_id in log_queues:
                        for queue in log_queues[run_id]:
                            await queue.put(event)
                        logger.debug("kafka_log_dispatched", run_id=run_id, queue_count=len(log_queues[run_id]))

        except Exception as e:
            retry_count += 1
            logger.error("kafka_consumer_error", error=str(e), retry=retry_count)
            if kafka_consumer:
                try:
                    await kafka_consumer.stop()
                except Exception:
                    pass
                kafka_consumer = None
            await asyncio.sleep(5)  # Wait before retry

    logger.error("kafka_consumer_max_retries_reached")

# GraphQL Types
@strawberry.enum
class MissionMode(Enum):
    STEALTH = "stealth"
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"

@strawberry.enum
class MissionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@strawberry.enum
class NodeType(Enum):
    # Asset nodes
    DOMAIN = "DOMAIN"
    SUBDOMAIN = "SUBDOMAIN"
    HTTP_SERVICE = "HTTP_SERVICE"
    ENDPOINT = "ENDPOINT"
    PARAMETER = "PARAMETER"
    HYPOTHESIS = "HYPOTHESIS"
    VULNERABILITY = "VULNERABILITY"
    ATTACK_PATH = "ATTACK_PATH"
    IP_ADDRESS = "IP_ADDRESS"
    DNS_RECORD = "DNS_RECORD"
    # Workflow nodes
    AGENT_RUN = "AGENT_RUN"
    TOOL_CALL = "TOOL_CALL"
    LLM_REASONING = "LLM_REASONING"

@strawberry.enum
class EventType(Enum):
    # Graph events
    NODE_ADDED = "node_added"
    NODE_UPDATED = "node_updated"
    NODE_DELETED = "node_deleted"
    EDGE_ADDED = "edge_added"
    EDGE_DELETED = "edge_deleted"
    ATTACK_PATH_ADDED = "attack_path_added"
    # Workflow events
    AGENT_STARTED = "agent_started"
    AGENT_FINISHED = "agent_finished"
    TOOL_CALLED = "tool_called"
    TOOL_FINISHED = "tool_finished"
    ASSET_MUTATION = "asset_mutation"

@strawberry.type
class Node:
    id: str
    type: NodeType
    properties: strawberry.scalars.JSON

@strawberry.type
class Edge:
    from_node: str
    to_node: str
    relation: str

@strawberry.type
class GraphStats:
    mission_id: str
    total_nodes: int
    total_edges: int
    nodes_by_type: strawberry.scalars.JSON

@strawberry.type
class Mission:
    id: str
    target_domain: str
    mode: MissionMode
    status: MissionStatus
    current_phase: Optional[str]
    created_at: str
    progress: strawberry.scalars.JSON

@strawberry.type
class MissionConnection:
    items: List[Mission]  # Changed from 'missions' to 'items' to match UI expectations
    total: int

@strawberry.type
class AttackPath:
    target: str
    score: int
    actions: List[str]
    reasons: List[str]

@strawberry.type
class GraphEvent:
    run_id: str
    event_type: EventType
    source: str
    payload: strawberry.scalars.JSON
    timestamp: str

@strawberry.type
class LogEntry:
    run_id: str
    level: str
    phase: str
    message: str
    timestamp: str
    metadata: strawberry.scalars.JSON

@strawberry.input
class MissionInput:
    target_domain: str
    mode: MissionMode = MissionMode.AGGRESSIVE
    seed_subdomains: Optional[List[str]] = None

@strawberry.input
class NodeFilter:
    types: Optional[List[NodeType]] = None
    risk_score_min: Optional[int] = None

@strawberry.type
class Query:
    @strawberry.field
    async def mission(self, id: str) -> Optional[Mission]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{ORCHESTRATOR_URL}/api/v1/missions/{id}")
                if response.status_code == 200:
                    data = response.json()
                    # Convert string values to enum members
                    mode_value = str(data.get("mode", "balanced")).lower()
                    status_value = str(data.get("status", "pending")).lower()

                    mode = MissionMode._value2member_map_.get(mode_value, MissionMode.BALANCED)
                    status = MissionStatus._value2member_map_.get(status_value, MissionStatus.PENDING)

                    return Mission(
                        id=data["id"],
                        target_domain=data["target_domain"],
                        mode=mode,
                        status=status,
                        current_phase=data.get("current_phase"),
                        created_at=str(data.get("created_at", "")),
                        progress=data.get("progress", {})
                    )
                return None
            except Exception as e:
                print(f"[BFF] Error fetching mission {id}: {e}")
                return None

    @strawberry.field
    async def missions(self, limit: int = 20, offset: int = 0) -> MissionConnection:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{ORCHESTRATOR_URL}/api/v1/missions",
                    params={"limit": limit, "offset": offset}
                )
                if response.status_code == 200:
                    data = response.json()
                    missions = []
                    for m in data.get("missions", []):
                        try:
                            # Convert string values to enum members
                            mode_value = m.get("mode", "balanced").lower()
                            status_value = m.get("status", "pending").lower()

                            mode = MissionMode._value2member_map_.get(mode_value, MissionMode.BALANCED)
                            status = MissionStatus._value2member_map_.get(status_value, MissionStatus.PENDING)

                            missions.append(Mission(
                                id=m["id"],
                                target_domain=m["target_domain"],
                                mode=mode,
                                status=status,
                                current_phase=m.get("current_phase"),
                                created_at=str(m.get("created_at", "")),
                                progress=m.get("progress", {})
                            ))
                        except Exception as e:
                            print(f"[BFF] Error parsing mission {m.get('id')}: {e}")
                            continue
                    return MissionConnection(items=missions, total=data.get("total", 0))
                print(f"[BFF] Orchestrator returned status {response.status_code}")
                return MissionConnection(items=[], total=0)
            except Exception as e:
                print(f"[BFF] Error fetching missions: {e}")
                return MissionConnection(items=[], total=0)

    @strawberry.field
    async def nodes(self, mission_id: str, filter: Optional[NodeFilter] = None, limit: int = 100) -> List[Node]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {"mission_id": mission_id, "limit": limit}
            if filter and filter.types:
                payload["node_types"] = [t.value for t in filter.types]
            if filter and filter.risk_score_min:
                payload["risk_score_min"] = filter.risk_score_min

            response = await client.post(
                f"{GRAPH_SERVICE_URL}/api/v1/nodes/query",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                return [
                    Node(
                        id=n["id"],
                        type=NodeType(n["type"]),
                        properties=n.get("properties", {})
                    )
                    for n in data["nodes"]
                ]
            return []

    @strawberry.field
    async def edges(self, mission_id: str) -> List[Edge]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{GRAPH_SERVICE_URL}/api/v1/missions/{mission_id}/edges")
            if response.status_code == 200:
                data = response.json()
                return [
                    Edge(
                        from_node=e["from_node"],
                        to_node=e["to_node"],
                        relation=e["relation"]
                    )
                    for e in data["edges"]
                ]
            return []

    @strawberry.field
    async def graph_stats(self, mission_id: str) -> Optional[GraphStats]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{GRAPH_SERVICE_URL}/api/v1/missions/{mission_id}/stats")
            if response.status_code == 200:
                data = response.json()
                return GraphStats(
                    mission_id=data["mission_id"],
                    total_nodes=data["total_nodes"],
                    total_edges=data["total_edges"],
                    nodes_by_type=data["nodes_by_type"]
                )
            return None

    @strawberry.field
    async def attack_paths(self, mission_id: str, top: int = 5) -> List[AttackPath]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {"mission_id": mission_id, "node_types": ["ATTACK_PATH"], "limit": top}
            response = await client.post(f"{GRAPH_SERVICE_URL}/api/v1/nodes/query", json=payload)
            if response.status_code == 200:
                data = response.json()
                paths = []
                for n in data["nodes"]:
                    props = n.get("properties", {})
                    paths.append(AttackPath(
                        target=props.get("target", ""),
                        score=props.get("score", 0),
                        actions=props.get("actions", []),
                        reasons=props.get("reasons", [])
                    ))
                return sorted(paths, key=lambda x: x.score, reverse=True)[:top]
            return []

    @strawberry.field
    async def workflow_nodes(
        self,
        mission_id: str,
        types: Optional[List[NodeType]] = None
    ) -> List[Node]:
        """Query workflow-specific nodes (AGENT_RUN, TOOL_CALL, LLM_REASONING)"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Default to all workflow types if none specified
            workflow_types = ["AGENT_RUN", "TOOL_CALL", "LLM_REASONING"]
            if types:
                workflow_types = [t.value for t in types if t.value in workflow_types]

            payload = {
                "mission_id": mission_id,
                "node_types": workflow_types,
                "include_edges": True
            }
            response = await client.post(
                f"{GRAPH_SERVICE_URL}/api/v1/workflow/query",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                return [
                    Node(
                        id=n["id"],
                        type=NodeType(n["type"]),
                        properties=n.get("properties", {})
                    )
                    for n in data["nodes"]
                ]
            return []

    @strawberry.field
    async def workflow_layout(self, mission_id: str) -> strawberry.scalars.JSON:
        """Get saved workflow layout for a mission"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{GRAPH_SERVICE_URL}/api/v1/layouts/{mission_id}")
            if response.status_code == 200:
                return response.json()
            return {"positions": {}, "zoom": 1.0, "pan": {"x": 0, "y": 0}}

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def start_mission(self, input: MissionInput) -> Mission:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "target_domain": input.target_domain,
                "mode": input.mode.value,
                "seed_subdomains": input.seed_subdomains
            }
            response = await client.post(f"{ORCHESTRATOR_URL}/api/v1/missions", json=payload)
            data = response.json()
            return Mission(
                id=data["id"],
                target_domain=data["target_domain"],
                mode=MissionMode(data["mode"]),
                status=MissionStatus(data["status"]),
                current_phase=data.get("current_phase"),
                created_at=str(data["created_at"]),
                progress=data.get("progress", {})
            )

    @strawberry.mutation
    async def cancel_mission(self, id: str) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/api/v1/missions/{id}/cancel")
            return response.status_code == 200

    @strawberry.mutation
    async def save_workflow_layout(
        self,
        mission_id: str,
        positions: strawberry.scalars.JSON,
        zoom: float = 1.0,
        pan_x: float = 0,
        pan_y: float = 0
    ) -> bool:
        """Save workflow layout positions for a mission"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "positions": positions,
                "zoom": zoom,
                "pan": {"x": pan_x, "y": pan_y}
            }
            response = await client.post(
                f"{GRAPH_SERVICE_URL}/api/v1/layouts/{mission_id}",
                json=payload
            )
            return response.status_code == 200

    @strawberry.mutation
    async def delete_mission(self, mission_id: str) -> strawberry.scalars.JSON:
        """Delete a mission and all its associated data from all services"""
        results = {"mission_id": mission_id, "services": {}}

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Delete from graph-service
            try:
                graph_response = await client.delete(f"{GRAPH_SERVICE_URL}/api/v1/missions/{mission_id}")
                if graph_response.status_code == 200:
                    results["services"]["graph_service"] = graph_response.json()
                else:
                    results["services"]["graph_service"] = {"status": "error", "code": graph_response.status_code}
            except Exception as e:
                results["services"]["graph_service"] = {"status": "error", "detail": str(e)}

            # Delete from orchestrator
            try:
                orch_response = await client.delete(f"{ORCHESTRATOR_URL}/api/v1/missions/{mission_id}")
                if orch_response.status_code == 200:
                    results["services"]["orchestrator"] = orch_response.json()
                else:
                    results["services"]["orchestrator"] = {"status": "error", "code": orch_response.status_code}
            except Exception as e:
                results["services"]["orchestrator"] = {"status": "error", "detail": str(e)}

        results["status"] = "deleted"
        return results

    @strawberry.mutation
    async def delete_mission_history(self, mission_id: str) -> strawberry.scalars.JSON:
        """Delete only logs/history for a mission (keeps nodes and edges)"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(f"{GRAPH_SERVICE_URL}/api/v1/missions/{mission_id}/history")
            if response.status_code == 200:
                return response.json()
            return {"status": "error", "detail": response.text}

    @strawberry.mutation
    async def clear_all_data(self, confirm: str) -> strawberry.scalars.JSON:
        """Clear ALL data from all services. Pass confirm='YES' to proceed."""
        if confirm != "YES":
            return {"status": "error", "detail": "Confirmation required: pass confirm='YES'"}

        results = {"services": {}}

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Clear graph-service
            try:
                graph_response = await client.delete(
                    f"{GRAPH_SERVICE_URL}/api/v1/data/clear",
                    params={"confirm": confirm}
                )
                if graph_response.status_code == 200:
                    results["services"]["graph_service"] = graph_response.json()
                else:
                    results["services"]["graph_service"] = {"status": "error", "code": graph_response.status_code}
            except Exception as e:
                results["services"]["graph_service"] = {"status": "error", "detail": str(e)}

            # Clear orchestrator
            try:
                orch_response = await client.delete(
                    f"{ORCHESTRATOR_URL}/api/v1/data/clear",
                    params={"confirm": confirm}
                )
                if orch_response.status_code == 200:
                    results["services"]["orchestrator"] = orch_response.json()
                else:
                    results["services"]["orchestrator"] = {"status": "error", "code": orch_response.status_code}
            except Exception as e:
                results["services"]["orchestrator"] = {"status": "error", "detail": str(e)}

        results["status"] = "cleared"
        return results

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def graph_events(self, run_id: str) -> AsyncGenerator[GraphEvent, None]:
        """Subscribe to real-time graph events for a mission"""
        queue: asyncio.Queue = asyncio.Queue()

        # Register queue
        if run_id not in event_queues:
            event_queues[run_id] = []
        event_queues[run_id].append(queue)

        logger.info("subscription_started", type="graph_events", run_id=run_id)

        try:
            while True:
                event = await queue.get()
                yield GraphEvent(
                    run_id=event.get("run_id", ""),
                    event_type=EventType(event.get("event_type", "node_added")),
                    source=event.get("source", ""),
                    payload=event.get("payload", {}),
                    timestamp=event.get("timestamp", datetime.utcnow().isoformat())
                )
        finally:
            # Unregister queue
            if run_id in event_queues:
                event_queues[run_id].remove(queue)
            logger.info("subscription_ended", type="graph_events", run_id=run_id)

    @strawberry.subscription
    async def logs(self, run_id: str) -> AsyncGenerator[LogEntry, None]:
        """Subscribe to real-time logs for a mission"""
        queue: asyncio.Queue = asyncio.Queue()

        # Register queue
        if run_id not in log_queues:
            log_queues[run_id] = []
        log_queues[run_id].append(queue)

        logger.info("subscription_started", type="logs", run_id=run_id)

        try:
            while True:
                log = await queue.get()
                yield LogEntry(
                    run_id=log.get("run_id", ""),
                    level=log.get("level", "INFO"),
                    phase=log.get("phase", ""),
                    message=log.get("message", ""),
                    timestamp=log.get("timestamp", datetime.utcnow().isoformat()),
                    metadata=log.get("metadata", {})
                )
        finally:
            # Unregister queue
            if run_id in log_queues:
                log_queues[run_id].remove(queue)
            logger.info("subscription_ended", type="logs", run_id=run_id)

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription
)

graphql_app = GraphQLRouter(
    schema,
    subscription_protocols=[GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL]
)

app = FastAPI(
    title="BFF Gateway",
    description="GraphQL API Gateway for Gotham Recon Platform with real-time subscriptions",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graphql_app, prefix="/graphql")

@app.get("/health")
async def health():
    kafka_status = "connected" if kafka_consumer else "unavailable"

    # Show active missions with subscribers
    active_missions = list(set(list(event_queues.keys()) + list(log_queues.keys())))

    return {
        "status": "healthy",
        "service": "bff-gateway",
        "kafka": {
            "status": kafka_status,
            "brokers": KAFKA_BROKERS,
            "topics": [KAFKA_TOPIC_EVENTS, KAFKA_TOPIC_LOGS]
        },
        "active_subscriptions": {
            "graph_events": sum(len(q) for q in event_queues.values()),
            "logs": sum(len(q) for q in log_queues.values()),
            "missions": active_missions[:10]  # Show first 10
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/debug/subscriptions")
async def debug_subscriptions():
    """Debug endpoint to see active subscriptions"""
    return {
        "event_queues": {k: len(v) for k, v in event_queues.items()},
        "log_queues": {k: len(v) for k, v in log_queues.items()},
        "kafka_connected": kafka_consumer is not None
    }

# SSE endpoint as alternative to WebSocket subscriptions
@app.get("/api/v1/sse/events/{run_id}")
async def sse_events(
    run_id: str,
    request: Request,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    lastEventId: Optional[str] = None  # P0.5-FIX: Also accept as query param for clients that can't set headers
):
    """
    Server-Sent Events endpoint for graph updates and logs.
    P0.5: Supports Last-Event-ID for reconnection and missed event replay.

    On reconnect:
    1. If Last-Event-ID provided: replay missed events from ring buffer
    2. If no Last-Event-ID: send full snapshot first, then stream deltas
    """
    from starlette.responses import StreamingResponse

    async def event_generator():
        event_queue: asyncio.Queue = asyncio.Queue()
        log_queue: asyncio.Queue = asyncio.Queue()

        # Register for both events and logs
        if run_id not in event_queues:
            event_queues[run_id] = []
        event_queues[run_id].append(event_queue)

        if run_id not in log_queues:
            log_queues[run_id] = []
        log_queues[run_id].append(log_queue)

        # P0.5-FIX: Use header OR query param for last event ID
        effective_last_event_id = last_event_id or lastEventId
        logger.info("sse_connection_started", run_id=run_id, last_event_id=effective_last_event_id)

        try:
            # P0.5: Handle reconnection with Last-Event-ID
            if effective_last_event_id:
                # Replay missed events from ring buffer
                missed_events = get_events_after(run_id, effective_last_event_id)
                logger.info("sse_replaying_missed_events", run_id=run_id, count=len(missed_events))
                for event in missed_events:
                    sse_id = event.get("sse_event_id", "")
                    yield f"id: {sse_id}\ndata: {json.dumps(event)}\n\n"
            else:
                # First connection - send snapshot
                snapshot = await get_snapshot_for_mission(run_id)
                if snapshot:
                    snapshot_event = {
                        "type": "snapshot",
                        "event_type": "SNAPSHOT",
                        "run_id": run_id,
                        "payload": snapshot,
                        "sse_event_id": generate_sse_event_id()
                    }
                    yield f"id: {snapshot_event['sse_event_id']}\ndata: {json.dumps(snapshot_event)}\n\n"
                    logger.info("sse_snapshot_sent", run_id=run_id, nodes=len(snapshot.get("nodes", [])))

            # Stream live events
            while True:
                try:
                    # Check both queues with timeout
                    done, pending = await asyncio.wait(
                        [
                            asyncio.create_task(event_queue.get()),
                            asyncio.create_task(log_queue.get())
                        ],
                        timeout=15.0,
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Cancel pending tasks
                    for task in pending:
                        task.cancel()

                    if done:
                        for task in done:
                            try:
                                data = task.result()
                                sse_id = data.get("sse_event_id", "")
                                yield f"id: {sse_id}\ndata: {json.dumps(data)}\n\n"
                            except asyncio.CancelledError:
                                pass
                    else:
                        # Timeout - send keepalive with ID
                        keepalive_id = generate_sse_event_id()
                        yield f"id: {keepalive_id}\ndata: {json.dumps({'type': 'keepalive'})}\n\n"

                except asyncio.CancelledError:
                    break
        except GeneratorExit:
            pass
        finally:
            # Cleanup subscriptions
            if run_id in event_queues and event_queue in event_queues[run_id]:
                event_queues[run_id].remove(event_queue)
            if run_id in log_queues and log_queue in log_queues[run_id]:
                log_queues[run_id].remove(log_queue)
            logger.info("sse_connection_closed", run_id=run_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# P0.5: Endpoint to get current snapshot + buffer status
@app.get("/api/v1/sse/snapshot/{run_id}")
async def get_sse_snapshot(run_id: str):
    """Get current graph snapshot and ring buffer status for a mission"""
    snapshot = await get_snapshot_for_mission(run_id)
    buffer_size = len(event_ring_buffers.get(run_id, []))

    return {
        "run_id": run_id,
        "snapshot": snapshot,
        "buffer": {
            "size": buffer_size,
            "max_size": RING_BUFFER_SIZE,
            "oldest_event_id": event_ring_buffers.get(run_id, [{}])[0].get("sse_event_id") if buffer_size > 0 else None,
            "newest_event_id": event_ring_buffers.get(run_id, [{}])[-1].get("sse_event_id") if buffer_size > 0 else None
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
