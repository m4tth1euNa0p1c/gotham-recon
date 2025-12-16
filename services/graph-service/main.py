"""
Graph Service - CQRS Read/Write for Asset Graph
Handles all graph operations: nodes, edges, queries
Publishes events to Kafka for real-time sync
Persists data to SQLite database
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Set
from enum import Enum
from datetime import datetime
import structlog
import os
import sys
import json
import asyncio
from contextlib import asynccontextmanager

# Import local database module
from database import db as database
from database.db import generate_edge_id

# Kafka producer (aiokafka)
try:
    from aiokafka import AIOKafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    AIOKafkaProducer = None

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# Configuration
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
KAFKA_TOPIC_EVENTS = "graph.events"
KAFKA_TOPIC_LOGS = "logs.recon"

# Event Envelope v2 constants
SCHEMA_VERSION = "v2"
PRODUCER_NAME = "graph-service"

import uuid
import time

def generate_event_id() -> str:
    """Generate unique event ID"""
    return str(uuid.uuid4())

def generate_trace_id() -> str:
    """Generate trace ID"""
    return f"trc_{uuid.uuid4().hex[:16]}"

def generate_span_id() -> str:
    """Generate span ID"""
    return f"spn_{uuid.uuid4().hex[:12]}"

def build_event_envelope_v2(event_type: str, mission_id: str, payload: dict, phase: str = "") -> dict:
    """
    Build Event Envelope v2 for Kafka publishing.
    P0.1: All events must use standardized envelope.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": generate_event_id(),
        "event_type": event_type,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "timestamp": time.time(),
        "mission_id": mission_id,
        "run_id": mission_id,
        "phase": phase,
        "trace_id": generate_trace_id(),
        "span_id": generate_span_id(),
        "task_id": "",
        "tool_call_id": "",
        "producer": PRODUCER_NAME,
        "payload": payload,
    }

# Global producer
kafka_producer: Optional[AIOKafkaProducer] = None

# WebSocket connections for real-time updates
ws_connections: Dict[str, Set[WebSocket]] = {}  # mission_id -> connections

async def close_all_websockets():
    """Close all WebSocket connections gracefully"""
    for mission_id, connections in ws_connections.items():
        for ws in list(connections):
            try:
                await ws.close(code=1001, reason="Server shutdown")
            except Exception:
                pass
    ws_connections.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle"""
    global kafka_producer

    # Initialize database
    await database.init_db()
    logger.info("database_initialized")

    # Load existing data from database into memory cache
    await load_from_database()

    # Startup: Initialize Kafka producer
    if KAFKA_AVAILABLE:
        try:
            kafka_producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BROKERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
            )
            await kafka_producer.start()
            logger.info("kafka_connected", brokers=KAFKA_BROKERS)
        except Exception as e:
            logger.warning("kafka_connection_failed", error=str(e))
            kafka_producer = None

    yield

    # Shutdown: Close WebSocket connections and Kafka producer
    logger.info("shutdown_started")
    await close_all_websockets()

    if kafka_producer:
        await kafka_producer.stop()
    logger.info("shutdown_complete")

async def load_from_database():
    """Load existing nodes and edges from database into memory"""
    # Load all missions and their nodes/edges
    missions, _ = await database.list_missions(limit=1000)
    for mission in missions:
        nodes, _ = await database.query_nodes(mission["id"], limit=10000)
        for node in nodes:
            nodes_store[node["id"]] = node
        edges = await database.get_edges(mission["id"])
        edges_store.extend(edges)
    logger.info("data_loaded_from_db", nodes=len(nodes_store), edges=len(edges_store))

app = FastAPI(
    title="Graph Service",
    description="CQRS service for Asset Graph management with real-time events",
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

# Enums
class NodeType(str, Enum):
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
    ASN = "ASN"
    ORG = "ORG"
    # Workflow nodes
    AGENT_RUN = "AGENT_RUN"         # mission_id, agent_name, phase, status, latency, tokens
    TOOL_CALL = "TOOL_CALL"         # tool, input_hash, duration, outcome
    LLM_REASONING = "LLM_REASONING" # prompt/trace redacted

class EdgeType(str, Enum):
    # Asset relationships - Discovery
    HAS_SUBDOMAIN = "HAS_SUBDOMAIN"       # domain → subdomain
    RESOLVES_TO = "RESOLVES_TO"           # subdomain → IP
    SERVES = "SERVES"                     # IP → service
    EXPOSES_HTTP = "EXPOSES_HTTP"         # subdomain → HTTP_SERVICE
    EXPOSES_ENDPOINT = "EXPOSES_ENDPOINT" # HTTP_SERVICE → ENDPOINT
    HAS_PARAM = "HAS_PARAM"               # ENDPOINT → PARAMETER
    HAS_PARAMETER = "HAS_PARAMETER"       # Alias for HAS_PARAM (compatibility)
    # DNS/Infrastructure relationships
    HAS_RECORD = "HAS_RECORD"             # subdomain → DNS_RECORD
    BELONGS_TO = "BELONGS_TO"             # IP → ASN/ORG
    # Asset relationships - Analysis
    HAS_HYPOTHESIS = "HAS_HYPOTHESIS"     # ENDPOINT → HYPOTHESIS
    HAS_VULNERABILITY = "HAS_VULNERABILITY" # ENDPOINT → VULNERABILITY
    AFFECTS_ENDPOINT = "AFFECTS_ENDPOINT" # VULNERABILITY → ENDPOINT (reverse)
    TARGETS = "TARGETS"                   # ATTACK_PATH → target node
    # Asset relationships - JS/Secrets
    LOADS_JS = "LOADS_JS"                 # HTTP_SERVICE → JS_FILE
    LEAKS_SECRET = "LEAKS_SECRET"         # HTTP_SERVICE → SECRET
    CONTAINS_SECRET = "CONTAINS_SECRET"   # JS_FILE → SECRET
    # Report relationships
    HAS_REPORT = "HAS_REPORT"             # domain/mission → REPORT
    # Workflow relationships
    TRIGGERS = "TRIGGERS"           # agent → agent
    USES_TOOL = "USES_TOOL"         # agent → tool_call
    PRODUCES = "PRODUCES"           # tool_call → asset_node
    REFINES = "REFINES"             # agent → asset_node (update)
    LINKS_TO = "LINKS_TO"           # agent_run → llm_reasoning

class EventType(str, Enum):
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
    # Deep Verification events (Lot 3)
    VULN_STATUS_CHANGED = "vuln_status_changed"
    EVIDENCE_ADDED = "evidence_added"


# Deep Verification: Vulnerability Status (Lot 3)
class VulnStatus(str, Enum):
    """Normalized vulnerability statuses for Deep Verification"""
    THEORETICAL = "THEORETICAL"  # Hypothesized from analysis
    LIKELY = "LIKELY"            # Partial evidence, needs verification
    CONFIRMED = "CONFIRMED"      # Verified with proof
    FALSE_POSITIVE = "FALSE_POSITIVE"  # Checked but not exploitable
    MITIGATED = "MITIGATED"      # Was vulnerable but now fixed

# Models
class NodeCreate(BaseModel):
    id: str
    type: NodeType
    mission_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class NodeUpdate(BaseModel):
    properties: Dict[str, Any]

class NodeResponse(BaseModel):
    id: str
    type: NodeType
    mission_id: str
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class EdgeCreate(BaseModel):
    # Core fields - accept both naming conventions
    from_node: Optional[str] = Field(None, alias="source_id")
    to_node: Optional[str] = Field(None, alias="target_id")
    relation: Optional[str] = Field(None, alias="type")  # Accept string, validate later
    mission_id: str
    # Properties for tracking origin
    properties: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True  # Allow both field name and alias

    def get_from_node(self) -> str:
        return self.from_node or ""

    def get_to_node(self) -> str:
        return self.to_node or ""

    def get_relation(self) -> str:
        return self.relation or "UNKNOWN"

class GraphQuery(BaseModel):
    mission_id: str
    node_types: Optional[List[NodeType]] = None
    risk_score_min: Optional[int] = None
    limit: int = 100
    offset: int = 0

class GraphStats(BaseModel):
    mission_id: str
    total_nodes: int
    total_edges: int
    nodes_by_type: Dict[str, int]

class GraphEvent(BaseModel):
    run_id: str
    event_type: EventType
    source: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# In-memory store (replace with PostgreSQL in production)
nodes_store: Dict[str, Dict] = {}
edges_store: List[Dict] = []

# Event publishing
async def publish_event(event: GraphEvent):
    """Publish event to Kafka and WebSocket clients using Event Envelope v2"""
    # Build Event Envelope v2 (P0.1)
    event_envelope = build_event_envelope_v2(
        event_type=event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
        mission_id=event.run_id,
        payload={
            "source": event.source,
            **serialize_for_json(event.payload),
        },
    )

    # Publish to Kafka
    if kafka_producer:
        try:
            await kafka_producer.send_and_wait(
                KAFKA_TOPIC_EVENTS,
                value=event_envelope,
                key=event.run_id.encode('utf-8')
            )
        except Exception as e:
            logger.warning("kafka_publish_failed", error=str(e))

    # Broadcast to WebSocket clients (use envelope for consistency)
    mission_id = event.run_id
    if mission_id in ws_connections:
        dead_connections = set()
        for ws in ws_connections[mission_id]:
            try:
                await ws.send_json(event_envelope)
            except Exception:
                dead_connections.add(ws)

        # Clean up dead connections
        ws_connections[mission_id] -= dead_connections

# WebSocket endpoint for real-time graph events
@app.websocket("/ws/graph/{mission_id}")
async def websocket_graph_events(websocket: WebSocket, mission_id: str):
    """WebSocket endpoint for real-time graph updates"""
    await websocket.accept()

    # Register connection
    if mission_id not in ws_connections:
        ws_connections[mission_id] = set()
    ws_connections[mission_id].add(websocket)

    logger.info("ws_connected", mission_id=mission_id)

    try:
        # Send initial snapshot
        snapshot = await get_mission_snapshot(mission_id)
        await websocket.send_json({"type": "snapshot", "data": snapshot})

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong or client commands
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("ws_disconnected", mission_id=mission_id)
    finally:
        if mission_id in ws_connections:
            ws_connections[mission_id].discard(websocket)

def serialize_for_json(obj):
    """Recursively serialize objects for JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif hasattr(obj, 'value'):  # Enum
        return obj.value
    return obj

async def get_mission_snapshot(mission_id: str) -> Dict:
    """Get current graph state for a mission"""
    mission_nodes = [serialize_for_json(n) for n in nodes_store.values() if n["mission_id"] == mission_id]
    mission_edges = [serialize_for_json(e) for e in edges_store if e["mission_id"] == mission_id]
    return {
        "mission_id": mission_id,
        "nodes": mission_nodes,
        "edges": mission_edges,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health():
    kafka_status = "connected" if kafka_producer else "unavailable"
    return {
        "status": "healthy",
        "service": "graph-service",
        "kafka": kafka_status,
        "ws_connections": sum(len(conns) for conns in ws_connections.values()),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/v1/nodes", response_model=NodeResponse)
async def create_node(node: NodeCreate, source: str = "api"):
    """Create a new node in the graph"""
    logger.info("creating_node", node_id=node.id, node_type=node.type, mission_id=node.mission_id)

    now = datetime.utcnow()
    is_update = node.id in nodes_store

    node_data = {
        "id": node.id,
        "type": node.type.value if hasattr(node.type, 'value') else node.type,
        "mission_id": node.mission_id,
        "properties": node.properties,
        "created_at": nodes_store.get(node.id, {}).get("created_at", now.isoformat()),
        "updated_at": now.isoformat()
    }
    nodes_store[node.id] = node_data

    # Persist to database
    await database.create_node(node_data)

    # Publish event
    event = GraphEvent(
        run_id=node.mission_id,
        event_type=EventType.NODE_UPDATED if is_update else EventType.NODE_ADDED,
        source=source,
        payload={"node": node_data}
    )
    await publish_event(event)

    return NodeResponse(**node_data)

@app.put("/api/v1/nodes/{node_id}")
async def update_node(node_id: str, update: NodeUpdate, source: str = "api"):
    """Update node properties"""
    if node_id not in nodes_store:
        raise HTTPException(status_code=404, detail="Node not found")

    node = nodes_store[node_id]
    node["properties"].update(update.properties)
    node["updated_at"] = datetime.utcnow()

    # Publish event
    event = GraphEvent(
        run_id=node["mission_id"],
        event_type=EventType.NODE_UPDATED,
        source=source,
        payload={"node": node}
    )
    await publish_event(event)

    return NodeResponse(**node)


@app.patch("/api/v1/nodes/{node_id}")
async def patch_node(node_id: str, update: NodeUpdate, source: str = "api"):
    """
    Partial update of node properties (Lot 3: Deep Verification support).
    Used by graph_updater_tool for updating vulnerability status and evidence.
    """
    if node_id not in nodes_store:
        raise HTTPException(status_code=404, detail="Node not found")

    node = nodes_store[node_id]
    old_status = node["properties"].get("status")

    # Merge properties (deep merge for nested objects)
    for key, value in update.properties.items():
        if key == "evidence" and isinstance(value, list):
            # Append evidence, don't replace (with deduplication by hash)
            existing_evidence = node["properties"].get("evidence", [])
            existing_hashes = {e.get("hash") for e in existing_evidence if e.get("hash")}
            new_evidence = [e for e in value if e.get("hash") not in existing_hashes]
            node["properties"]["evidence"] = existing_evidence + new_evidence
        else:
            node["properties"][key] = value

    node["updated_at"] = datetime.utcnow().isoformat()

    # Persist to database
    await database.update_node(node_id, node)

    # Determine event type
    new_status = node["properties"].get("status")
    if old_status != new_status and node["type"] == "VULNERABILITY":
        event_type = EventType.VULN_STATUS_CHANGED
    else:
        event_type = EventType.NODE_UPDATED

    # Publish event
    event = GraphEvent(
        run_id=node["mission_id"],
        event_type=event_type,
        source=source,
        payload={
            "node": serialize_for_json(node),
            "old_status": old_status,
            "new_status": new_status
        }
    )
    await publish_event(event)

    return serialize_for_json(node)

@app.get("/api/v1/nodes")
async def list_nodes(mission_id: Optional[str] = None, type: Optional[str] = None, limit: int = 1000):
    """List nodes with optional mission_id and type filters"""
    results = []
    for node in nodes_store.values():
        if mission_id and node.get("mission_id") != mission_id:
            continue
        if type and node.get("type") != type:
            continue
        results.append(node)
    return {"nodes": results[:limit], "total": len(results)}

@app.get("/api/v1/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str):
    """Get a node by ID"""
    if node_id not in nodes_store:
        raise HTTPException(status_code=404, detail="Node not found")
    return NodeResponse(**nodes_store[node_id])

@app.delete("/api/v1/nodes/{node_id}")
async def delete_node(node_id: str, source: str = "api"):
    """Delete a node"""
    if node_id not in nodes_store:
        raise HTTPException(status_code=404, detail="Node not found")

    node = nodes_store.pop(node_id)

    # Publish event
    event = GraphEvent(
        run_id=node["mission_id"],
        event_type=EventType.NODE_DELETED,
        source=source,
        payload={"node_id": node_id}
    )
    await publish_event(event)

    return {"status": "deleted", "node_id": node_id}

@app.post("/api/v1/nodes/query")
async def query_nodes(query: GraphQuery):
    """Query nodes with filters"""
    results = []
    for node in nodes_store.values():
        if node["mission_id"] != query.mission_id:
            continue
        if query.node_types and node["type"] not in query.node_types:
            continue
        if query.risk_score_min:
            risk = node.get("properties", {}).get("risk_score", 0)
            if risk < query.risk_score_min:
                continue
        results.append(node)

    total = len(results)
    results = results[query.offset:query.offset + query.limit]

    return {
        "nodes": results,
        "total": total,
        "limit": query.limit,
        "offset": query.offset
    }

def validate_edge_type(relation: str) -> str:
    """Validate and normalize edge type against EdgeType enum"""
    if not relation:
        raise HTTPException(status_code=400, detail="Edge relation/type is required")

    # Normalize: uppercase, strip whitespace
    normalized = relation.strip().upper()

    # Check if it's a valid EdgeType
    valid_types = {e.value for e in EdgeType}
    if normalized not in valid_types:
        logger.warning("invalid_edge_type", relation=relation, valid_types=list(valid_types))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid edge type: '{relation}'. Valid types: {sorted(valid_types)}"
        )
    return normalized

@app.post("/api/v1/edges")
async def create_edge(edge: EdgeCreate, source: str = "api"):
    """
    Create an edge between nodes with strict type validation.
    P0.2: Uses deterministic edge ID for idempotent upserts.
    """
    # Get normalized field values (supports both naming conventions)
    from_node = edge.from_node
    to_node = edge.to_node
    relation = edge.relation

    # Validate required fields
    if not from_node:
        raise HTTPException(status_code=400, detail="from_node (or source_id) is required")
    if not to_node:
        raise HTTPException(status_code=400, detail="to_node (or target_id) is required")

    # Validate and normalize edge type
    validated_relation = validate_edge_type(relation)

    # P0.2: Generate deterministic edge ID
    edge_id = generate_edge_id(from_node, to_node, validated_relation, edge.mission_id)

    logger.info("creating_edge", edge_id=edge_id, from_node=from_node, to_node=to_node, relation=validated_relation, source=source)

    edge_data = {
        "id": edge_id,
        "from_node": from_node,
        "to_node": to_node,
        "relation": validated_relation,
        "mission_id": edge.mission_id,
        "properties": edge.properties,
        "created_at": datetime.utcnow().isoformat()
    }

    # Check if edge already exists in memory (idempotent check)
    existing = next((e for e in edges_store if e.get("id") == edge_id), None)
    if not existing:
        edges_store.append(edge_data)

    # Persist to database (uses INSERT OR IGNORE)
    await database.create_edge(edge_data)

    # Publish event
    event = GraphEvent(
        run_id=edge.mission_id,
        event_type=EventType.EDGE_ADDED,
        source=source,
        payload={"edge": edge_data}
    )
    await publish_event(event)

    return {"status": "created", "edge": edge_data}

@app.get("/api/v1/missions/{mission_id}/edges")
async def get_mission_edges(mission_id: str):
    """Get all edges for a mission"""
    mission_edges = [e for e in edges_store if e["mission_id"] == mission_id]
    return {"edges": mission_edges, "total": len(mission_edges)}

@app.get("/api/v1/missions/{mission_id}/stats", response_model=GraphStats)
async def get_mission_stats(mission_id: str):
    """Get statistics for a mission's graph"""
    mission_nodes = [n for n in nodes_store.values() if n["mission_id"] == mission_id]
    mission_edges = [e for e in edges_store if e["mission_id"] == mission_id]

    nodes_by_type = {}
    for node in mission_nodes:
        t = node["type"]
        nodes_by_type[t] = nodes_by_type.get(t, 0) + 1

    return GraphStats(
        mission_id=mission_id,
        total_nodes=len(mission_nodes),
        total_edges=len(mission_edges),
        nodes_by_type=nodes_by_type
    )

@app.get("/api/v1/missions/{mission_id}/export")
async def export_graph(mission_id: str):
    """Export full graph as JSON"""
    return await get_mission_snapshot(mission_id)

# Batch operations for performance
@app.post("/api/v1/nodes/batch")
async def create_nodes_batch(nodes: List[NodeCreate], source: str = "batch"):
    """Create multiple nodes in one request"""
    created = []
    now = datetime.utcnow()

    for node in nodes:
        node_data = {
            "id": node.id,
            "type": node.type,
            "mission_id": node.mission_id,
            "properties": node.properties,
            "created_at": now,
            "updated_at": now
        }
        nodes_store[node.id] = node_data
        created.append(node_data)

    # Publish single batch event
    if nodes:
        event = GraphEvent(
            run_id=nodes[0].mission_id,
            event_type=EventType.NODE_ADDED,
            source=source,
            payload={"nodes": created, "count": len(created)}
        )
        await publish_event(event)

    return {"created": len(created), "nodes": created}

@app.post("/api/v1/edges/batch")
async def create_edges_batch(edges: List[EdgeCreate], source: str = "batch"):
    """
    Create multiple edges in one request with strict type validation.
    P0.2: Uses deterministic edge IDs for idempotent upserts.
    """
    created = []
    errors = []
    now = datetime.utcnow().isoformat()

    for i, edge in enumerate(edges):
        # Get field values
        from_node = edge.from_node
        to_node = edge.to_node
        relation = edge.relation

        # Validate required fields
        if not from_node or not to_node:
            errors.append({"index": i, "error": "from_node and to_node are required"})
            continue

        # Validate edge type
        try:
            validated_relation = validate_edge_type(relation)
        except HTTPException as e:
            errors.append({"index": i, "error": e.detail})
            continue

        # P0.2: Generate deterministic edge ID
        edge_id = generate_edge_id(from_node, to_node, validated_relation, edge.mission_id)

        edge_data = {
            "id": edge_id,
            "from_node": from_node,
            "to_node": to_node,
            "relation": validated_relation,
            "mission_id": edge.mission_id,
            "properties": edge.properties,
            "created_at": now
        }

        # Check if edge already exists in memory (idempotent check)
        existing = next((e for e in edges_store if e.get("id") == edge_id), None)
        if not existing:
            edges_store.append(edge_data)
        created.append(edge_data)

    # Persist to database using batch function (atomic transaction)
    if created:
        await database.create_edges_batch(created)

    # Publish single batch event
    if created:
        event = GraphEvent(
            run_id=edges[0].mission_id,
            event_type=EventType.EDGE_ADDED,
            source=source,
            payload={"edges": created, "count": len(created)}
        )
        await publish_event(event)

    result = {"created": len(created), "edges": created}
    if errors:
        result["errors"] = errors
        logger.warning("batch_edges_partial_failure", errors=len(errors), created=len(created))
    return result


# P0.4: Atomic batch graph endpoint for nodes AND edges together
class BatchUpsertRequest(BaseModel):
    """Request model for atomic batch upsert of nodes and edges"""
    mission_id: str
    nodes: List[NodeCreate] = []
    edges: List[EdgeCreate] = []


@app.post("/api/v1/graph/batchUpsert")
async def batch_upsert_graph(request: BatchUpsertRequest, source: str = "batch"):
    """
    P0.4: Atomic batch upsert of nodes and edges in a single transaction.
    All-or-nothing: if any operation fails, the entire batch is rolled back.

    P0.4-FIX: In-memory state is only updated AFTER successful DB commit.
    """
    logger.info("batch_upsert_start", mission_id=request.mission_id, nodes=len(request.nodes), edges=len(request.edges))

    now = datetime.utcnow()
    prepared_nodes = []  # Prepared data, NOT yet in memory
    prepared_edges = []  # Prepared data, NOT yet in memory
    errors = []

    # Process nodes (prepare data only, don't modify in-memory yet)
    for i, node in enumerate(request.nodes):
        try:
            node_data = {
                "id": node.id,
                "type": node.type.value if hasattr(node.type, 'value') else node.type,
                "mission_id": node.mission_id or request.mission_id,
                "properties": node.properties,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            prepared_nodes.append(node_data)
        except Exception as e:
            errors.append({"type": "node", "index": i, "error": str(e)})

    # Process edges with deterministic IDs (prepare data only)
    for i, edge in enumerate(request.edges):
        from_node = edge.from_node
        to_node = edge.to_node
        relation = edge.relation

        if not from_node or not to_node:
            errors.append({"type": "edge", "index": i, "error": "from_node and to_node are required"})
            continue

        try:
            validated_relation = validate_edge_type(relation)
        except HTTPException as e:
            errors.append({"type": "edge", "index": i, "error": e.detail})
            continue

        edge_id = generate_edge_id(from_node, to_node, validated_relation, edge.mission_id or request.mission_id)
        edge_data = {
            "id": edge_id,
            "from_node": from_node,
            "to_node": to_node,
            "relation": validated_relation,
            "mission_id": edge.mission_id or request.mission_id,
            "properties": edge.properties,
            "created_at": now.isoformat()
        }
        prepared_edges.append(edge_data)

    # P0.4-FIX: Persist to database FIRST (atomic transaction)
    # In-memory is only updated after successful commit
    if prepared_nodes or prepared_edges:
        try:
            await database.batch_upsert(prepared_nodes, prepared_edges)
        except Exception as e:
            # DB failed - don't update in-memory, propagate error
            logger.error("batch_upsert_db_failed", mission_id=request.mission_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Batch upsert failed: {str(e)}")

    # DB commit successful - now update in-memory state
    for node_data in prepared_nodes:
        nodes_store[node_data["id"]] = node_data

    for edge_data in prepared_edges:
        existing = next((e for e in edges_store if e.get("id") == edge_data["id"]), None)
        if not existing:
            edges_store.append(edge_data)

    # Publish batch events (only after successful commit)
    if prepared_nodes:
        event = GraphEvent(
            run_id=request.mission_id,
            event_type=EventType.NODE_ADDED,
            source=source,
            payload={"nodes": prepared_nodes, "count": len(prepared_nodes)}
        )
        await publish_event(event)

    if prepared_edges:
        event = GraphEvent(
            run_id=request.mission_id,
            event_type=EventType.EDGE_ADDED,
            source=source,
            payload={"edges": prepared_edges, "count": len(prepared_edges)}
        )
        await publish_event(event)

    result = {
        "status": "success" if not errors else "partial",
        "nodes_created": len(prepared_nodes),
        "edges_created": len(prepared_edges),
        "nodes": prepared_nodes,
        "edges": prepared_edges
    }
    if errors:
        result["errors"] = errors
        logger.warning("batch_upsert_partial_failure", errors=len(errors))

    logger.info("batch_upsert_complete", mission_id=request.mission_id,
                nodes=len(prepared_nodes), edges=len(prepared_edges))
    return result

# Layout persistence for workflow visualization
layouts_store: Dict[str, Dict] = {}  # mission_id -> layout positions

class LayoutSave(BaseModel):
    positions: Dict[str, Dict[str, float]]  # node_id -> {x, y}
    zoom: Optional[float] = 1.0
    pan: Optional[Dict[str, float]] = None  # {x, y}

@app.post("/api/v1/layouts/{mission_id}")
async def save_layout(mission_id: str, layout: LayoutSave):
    """Save workflow layout positions for a mission"""
    layouts_store[mission_id] = {
        "positions": layout.positions,
        "zoom": layout.zoom,
        "pan": layout.pan or {"x": 0, "y": 0},
        "updated_at": datetime.utcnow().isoformat()
    }
    # Persist to database
    await database.save_layout(mission_id, layouts_store[mission_id])
    return {"status": "saved", "mission_id": mission_id}

@app.get("/api/v1/layouts/{mission_id}")
async def get_layout(mission_id: str):
    """Load workflow layout positions for a mission"""
    # Check memory cache first
    if mission_id in layouts_store:
        return layouts_store[mission_id]
    # Try loading from database
    layout = await database.get_layout(mission_id)
    if layout:
        layouts_store[mission_id] = layout
        return layout
    return {"positions": {}, "zoom": 1.0, "pan": {"x": 0, "y": 0}}

# Query workflow nodes specifically
class WorkflowQuery(BaseModel):
    mission_id: str
    node_types: Optional[List[str]] = None  # AGENT_RUN, TOOL_CALL, LLM_REASONING
    include_edges: bool = True

@app.post("/api/v1/workflow/query")
async def query_workflow(query: WorkflowQuery):
    """Query workflow-specific nodes and edges"""
    workflow_types = {"AGENT_RUN", "TOOL_CALL", "LLM_REASONING"}
    workflow_edges = {"TRIGGERS", "USES_TOOL", "PRODUCES", "REFINES", "LINKS_TO"}

    # Filter to requested types or all workflow types
    types_filter = set(query.node_types) if query.node_types else workflow_types
    types_filter = types_filter & workflow_types  # Ensure only workflow types

    # Get workflow nodes
    nodes = [
        serialize_for_json(n) for n in nodes_store.values()
        if n["mission_id"] == query.mission_id and n["type"] in types_filter
    ]

    # Get workflow edges if requested
    edges = []
    if query.include_edges:
        edges = [
            serialize_for_json(e) for e in edges_store
            if e["mission_id"] == query.mission_id and e["relation"] in workflow_edges
        ]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }

# ==================== DELETION ENDPOINTS ====================

@app.delete("/api/v1/missions/{mission_id}")
async def delete_mission(mission_id: str, source: str = "api"):
    """Delete a mission and all its associated data (nodes, edges, logs, layouts)"""
    logger.info("deleting_mission", mission_id=mission_id, source=source)

    # Remove from memory stores
    nodes_to_remove = [nid for nid, n in nodes_store.items() if n["mission_id"] == mission_id]
    for nid in nodes_to_remove:
        del nodes_store[nid]

    edges_before = len(edges_store)
    edges_store[:] = [e for e in edges_store if e["mission_id"] != mission_id]
    edges_removed = edges_before - len(edges_store)

    # Remove from layouts store
    if mission_id in layouts_store:
        del layouts_store[mission_id]

    # Remove from WebSocket connections
    if mission_id in ws_connections:
        for ws in list(ws_connections[mission_id]):
            try:
                await ws.close(code=1000, reason="Mission deleted")
            except Exception:
                pass
        del ws_connections[mission_id]

    # Delete from database
    result = await database.delete_mission(mission_id)

    # Publish deletion event
    event = GraphEvent(
        run_id=mission_id,
        event_type=EventType.NODE_DELETED,
        source=source,
        payload={"action": "mission_deleted", "mission_id": mission_id, **result}
    )
    await publish_event(event)

    logger.info("mission_deleted", mission_id=mission_id, nodes=len(nodes_to_remove), edges=edges_removed)
    return {
        "status": "deleted",
        "mission_id": mission_id,
        "nodes_deleted": len(nodes_to_remove),
        "edges_deleted": edges_removed,
        **result
    }

@app.delete("/api/v1/missions/{mission_id}/history")
async def delete_mission_history(mission_id: str, source: str = "api"):
    """Delete only logs/history for a mission (keeps nodes and edges)"""
    logger.info("deleting_mission_history", mission_id=mission_id, source=source)

    result = await database.delete_mission_history(mission_id)

    logger.info("mission_history_deleted", mission_id=mission_id, logs=result["logs_deleted"])
    return {
        "status": "deleted",
        "mission_id": mission_id,
        **result
    }

@app.delete("/api/v1/data/clear")
async def clear_all_data(confirm: str = None, source: str = "api"):
    """Clear ALL data from the database. Requires confirm=YES parameter."""
    if confirm != "YES":
        raise HTTPException(
            status_code=400,
            detail="This action will delete ALL data. Pass confirm=YES to proceed."
        )

    logger.warning("clearing_all_data", source=source)

    # Clear memory stores
    nodes_count = len(nodes_store)
    edges_count = len(edges_store)

    nodes_store.clear()
    edges_store.clear()
    layouts_store.clear()

    # Close all WebSocket connections
    await close_all_websockets()

    # Clear database
    result = await database.clear_all_data()

    logger.warning("all_data_cleared", **result)
    return {
        "status": "cleared",
        "memory_cleared": {
            "nodes": nodes_count,
            "edges": edges_count
        },
        "database_cleared": result
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
