"""
Recon Orchestrator - Mission coordination and workflow management
CQRS Write side - Commands for mission control
Publishes logs and progress to Kafka for real-time UI updates
Persists data to SQLite database
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Set
from enum import Enum
from datetime import datetime
import uuid
import structlog
import httpx
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager

# Import local database module
from database import db as database

# Import JSON-safe serialization utility
from core.utils.json_safe import make_json_safe

# Import LLM and event modules (always available)
LLM_AVAILABLE = False
try:
    from core.llm_client import LLMClient, get_llm_client
    from core.events import (
        emit_agent_started, emit_agent_finished, emit_phase_started,
        emit_phase_completed, emit_mission_status, emit_log as emit_kafka_log,
        emit_node_added, emit_nodes_batch, emit_llm_call,
        make_json_safe, build_event_envelope  # P0.1/P0.3: Event envelope v2 + JSON safety
    )
    LLM_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] LLM/Events modules not available: {e}")

# CrewAI is optional
CREWAI_AVAILABLE = False
try:
    from core.crew_runner import run_crewai_mission, CrewMissionRunner
    CREWAI_AVAILABLE = True
except ImportError:
    pass  # CrewAI not installed - will use direct service calls

# Kafka producer (aiokafka)
try:
    from aiokafka import AIOKafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    AIOKafkaProducer = None

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
KAFKA_TOPIC_LOGS = "logs.recon"
KAFKA_TOPIC_GRAPH = "graph.events"
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://host.docker.internal:11434"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:14b")
USE_CREWAI = os.getenv("USE_CREWAI", "true").lower() == "true"

# Global producer
kafka_producer: Optional[AIOKafkaProducer] = None

# WebSocket connections for logs
ws_log_connections: Dict[str, Set[WebSocket]] = {}  # mission_id -> connections

# Track running background tasks for proper shutdown
running_tasks: Set[asyncio.Task] = set()

def track_task(coro) -> asyncio.Task:
    """Create and track an asyncio task for proper cleanup on shutdown"""
    task = asyncio.create_task(coro)
    running_tasks.add(task)
    task.add_done_callback(running_tasks.discard)
    return task

async def cancel_all_tasks():
    """Cancel all running tasks gracefully"""
    if not running_tasks:
        return
    logger.info("cancelling_running_tasks", count=len(running_tasks))
    for task in running_tasks:
        task.cancel()
    # Wait for all tasks to complete (with exceptions suppressed)
    await asyncio.gather(*running_tasks, return_exceptions=True)
    running_tasks.clear()

async def close_all_websockets():
    """Close all WebSocket connections gracefully"""
    for mission_id, connections in ws_log_connections.items():
        for ws in list(connections):
            try:
                await ws.close(code=1001, reason="Server shutdown")
            except Exception:
                pass
    ws_log_connections.clear()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle"""
    global kafka_producer

    # Initialize database
    await database.init_db()
    logger.info("database_initialized")

    # Load existing missions from database
    await load_missions_from_db()

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

    # Shutdown: Cancel running tasks and close connections
    logger.info("shutdown_started")
    await cancel_all_tasks()
    await close_all_websockets()

    if kafka_producer:
        await kafka_producer.stop()
    logger.info("shutdown_complete")

async def load_missions_from_db():
    """Load existing missions from database into memory"""
    db_missions, _ = await database.list_missions(limit=1000)
    for m in db_missions:
        missions[m["id"]] = {
            "id": m["id"],
            "target_domain": m["target_domain"],
            "mode": MissionMode(m["mode"]),
            "status": MissionStatus(m["status"]),
            "current_phase": PhaseType(m["current_phase"]) if m.get("current_phase") else None,
            "seed_subdomains": m.get("seed_subdomains", []),
            "options": m.get("options", {}),
            "created_at": m["created_at"],
            "updated_at": m["updated_at"],
            "progress": m.get("progress", {})
        }
    logger.info("missions_loaded_from_db", count=len(missions))

app = FastAPI(
    title="Recon Orchestrator",
    description="Mission orchestration and workflow coordination with real-time logging",
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

class MissionMode(str, Enum):
    STEALTH = "stealth"
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"

class MissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PhaseType(str, Enum):
    OSINT = "osint"
    SAFETY_NET = "safety_net"
    ACTIVE_RECON = "active_recon"
    ENDPOINT_INTEL = "endpoint_intel"
    VERIFICATION = "verification"
    PLANNER = "planner"
    REPORTING = "reporting"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class MissionCreate(BaseModel):
    target_domain: str
    mode: MissionMode = MissionMode.AGGRESSIVE
    seed_subdomains: Optional[List[str]] = None
    options: Dict[str, Any] = Field(default_factory=dict)

class MissionResponse(BaseModel):
    id: str
    target_domain: str
    mode: MissionMode
    status: MissionStatus
    current_phase: Optional[PhaseType]
    created_at: datetime
    updated_at: datetime
    progress: Dict[str, Any]

class PhaseResult(BaseModel):
    phase: PhaseType
    status: str
    duration_seconds: float
    metrics: Dict[str, Any]
    errors: List[str] = []

# Workflow event schema (for agent/tool tracking)
class WorkflowEvent(BaseModel):
    run_id: str
    event_type: str  # agent_started, agent_finished, tool_called, tool_finished, asset_mutation
    source: str
    payload: Dict[str, Any]
    timestamp: str

# In-memory mission store
missions: Dict[str, Dict] = {}

# Service URLs
GRAPH_SERVICE = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8001")
OSINT_RUNNER = os.getenv("OSINT_RUNNER_URL", "http://osint-runner:8002")
ACTIVE_RECON = os.getenv("ACTIVE_RECON_URL", "http://active-recon:8003")
ENDPOINT_INTEL = os.getenv("ENDPOINT_INTEL_URL", "http://endpoint-intel:8004")
VERIFICATION = os.getenv("VERIFICATION_URL", "http://verification:8005")
PLANNER = os.getenv("PLANNER_URL", "http://planner:8007")
REPORTER = os.getenv("REPORTER_URL", "http://reporter:8006")

async def publish_log(mission_id: str, level: LogLevel, phase: str, message: str, metadata: Dict = None):
    """Publish log entry to Kafka, WebSocket clients, and database using Event Envelope v2"""
    timestamp = datetime.utcnow().isoformat()

    # Persist to database
    await database.create_log({
        "mission_id": mission_id,
        "level": level.value,
        "phase": phase,
        "message": message,
        "metadata": make_json_safe(metadata or {}),
        "timestamp": timestamp
    })

    # Build Event Envelope v2 for Kafka
    log_envelope = build_event_envelope(
        event_type="LOG",
        mission_id=mission_id,
        payload={
            "level": level.value,
            "message": message,
            "metadata": metadata or {},
        },
        phase=phase,
    )

    # Publish to Kafka
    if kafka_producer:
        try:
            await kafka_producer.send_and_wait(
                KAFKA_TOPIC_LOGS,
                value=log_envelope,
                key=mission_id.encode('utf-8')
            )
        except Exception as e:
            logger.warning("kafka_log_publish_failed", error=str(e))

    # Broadcast to WebSocket clients (use envelope for consistency)
    if mission_id in ws_log_connections:
        dead_connections = set()
        for ws in ws_log_connections[mission_id]:
            try:
                await ws.send_json(log_envelope)
            except Exception:
                dead_connections.add(ws)
        ws_log_connections[mission_id] -= dead_connections


async def publish_workflow_event(event: WorkflowEvent):
    """Publish workflow event to Kafka (graph.events) using Event Envelope v2"""
    if kafka_producer:
        try:
            # Build Event Envelope v2
            workflow_envelope = build_event_envelope(
                event_type=event.event_type,
                mission_id=event.run_id,
                payload={
                    "run_id": event.run_id,
                    "source": event.source,
                    "timestamp": event.timestamp,
                    **event.payload,
                },
            )
            await kafka_producer.send_and_wait(
                KAFKA_TOPIC_GRAPH,
                value=workflow_envelope,
                key=event.run_id.encode("utf-8"),
            )
        except Exception as e:
            logger.warning("kafka_workflow_publish_failed", error=str(e))
    else:
        logger.warning("kafka_unavailable_workflow_event_dropped", event_type=event.event_type)

# WebSocket endpoint for real-time logs
@app.websocket("/ws/logs/{mission_id}")
async def websocket_logs(websocket: WebSocket, mission_id: str):
    """WebSocket endpoint for real-time mission logs"""
    await websocket.accept()

    if mission_id not in ws_log_connections:
        ws_log_connections[mission_id] = set()
    ws_log_connections[mission_id].add(websocket)

    logger.info("ws_log_connected", mission_id=mission_id)

    # Send initial connection confirmation
    await websocket.send_json({
        "type": "connected",
        "run_id": mission_id,
        "message": "Connected to log stream",
        "timestamp": datetime.utcnow().isoformat()
    })

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("ws_log_disconnected", mission_id=mission_id)
    finally:
        if mission_id in ws_log_connections:
            ws_log_connections[mission_id].discard(websocket)

@app.get("/health")
async def health():
    kafka_status = "connected" if kafka_producer else "unavailable"

    # Check LLM availability
    llm_status = "unavailable"
    llm_model = None
    if LLM_AVAILABLE:
        try:
            llm_client = get_llm_client()
            if llm_client.is_available():
                llm_status = "connected"
                llm_model = llm_client.model_name
        except Exception:
            pass

    return {
        "status": "healthy",
        "service": "recon-orchestrator",
        "kafka": kafka_status,
        "llm": {
            "status": llm_status,
            "provider": LLM_PROVIDER,
            "model": llm_model or MODEL_NAME,
            "url": OLLAMA_URL,
            "module_loaded": LLM_AVAILABLE
        },
        "crewai": {
            "available": CREWAI_AVAILABLE,
            "enabled": USE_CREWAI and CREWAI_AVAILABLE
        },
        "active_ws_connections": sum(len(conns) for conns in ws_log_connections.values()),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/llm/status")
async def llm_status():
    """Check LLM availability and configuration"""
    if not LLM_AVAILABLE:
        return {
            "status": "unavailable",
            "reason": "LLM module not loaded",
            "provider": LLM_PROVIDER,
            "url": OLLAMA_URL
        }

    try:
        llm_client = get_llm_client()
        available = llm_client.is_available()

        return {
            "status": "connected" if available else "disconnected",
            "provider": llm_client.provider,
            "model": llm_client.model_name,
            "coder_model": llm_client.coder_model_name,
            "url": llm_client.ollama_base_url,
            "crewai_available": CREWAI_AVAILABLE,
            "crewai_enabled": USE_CREWAI and CREWAI_AVAILABLE
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "provider": LLM_PROVIDER,
            "url": OLLAMA_URL
        }

@app.post("/api/v1/missions", response_model=MissionResponse)
async def create_mission(mission: MissionCreate):
    """Start a new reconnaissance mission"""
    mission_id = str(uuid.uuid4())
    now = datetime.utcnow()

    logger.info("creating_mission", mission_id=mission_id, target=mission.target_domain, mode=mission.mode)

    mission_data = {
        "id": mission_id,
        "target_domain": mission.target_domain,
        "mode": mission.mode,
        "seed_subdomains": mission.seed_subdomains,
        "options": mission.options,
        "status": MissionStatus.PENDING,
        "current_phase": None,
        "created_at": now,
        "updated_at": now,
        "progress": {
            "phases_completed": [],
            "current_metrics": {}
        }
    }
    missions[mission_id] = mission_data

    # Persist to database
    await database.create_mission({
        "id": mission_id,
        "target_domain": mission.target_domain,
        "mode": mission.mode.value,
        "status": "pending",
        "current_phase": None,
        "seed_subdomains": mission.seed_subdomains or [],
        "options": mission.options,
        "progress": mission_data["progress"],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    })

    # Publish initial log
    await publish_log(
        mission_id,
        LogLevel.INFO,
        "init",
        f"Mission created for target: {mission.target_domain}",
        {"mode": mission.mode.value, "target": mission.target_domain}
    )

    # Start mission execution in background (tracked for proper shutdown)
    track_task(execute_mission(mission_id))

    return MissionResponse(**mission_data)

@app.get("/api/v1/missions/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: str):
    """Get mission status and details"""
    if mission_id not in missions:
        raise HTTPException(status_code=404, detail="Mission not found")
    return MissionResponse(**missions[mission_id])

@app.get("/api/v1/missions")
async def list_missions(limit: int = 20, offset: int = 0):
    """List all missions"""
    all_missions = list(missions.values())
    total = len(all_missions)
    results = all_missions[offset:offset + limit]

    # Serialize enum values for JSON response
    serialized = []
    for m in results:
        serialized.append({
            "id": m["id"],
            "target_domain": m["target_domain"],
            "mode": m["mode"].value if hasattr(m["mode"], "value") else m["mode"],
            "status": m["status"].value if hasattr(m["status"], "value") else m["status"],
            "current_phase": m.get("current_phase"),
            "created_at": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
            "updated_at": m["updated_at"].isoformat() if hasattr(m["updated_at"], "isoformat") else str(m["updated_at"]),
            "progress": m.get("progress", {}),
        })

    return {
        "missions": serialized,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.post("/api/v1/missions/{mission_id}/cancel")
async def cancel_mission(mission_id: str):
    """Cancel a running mission"""
    if mission_id not in missions:
        raise HTTPException(status_code=404, detail="Mission not found")

    mission = missions[mission_id]
    if mission["status"] not in [MissionStatus.PENDING, MissionStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Mission cannot be cancelled")

    mission["status"] = MissionStatus.CANCELLED
    mission["updated_at"] = datetime.utcnow()

    await publish_log(mission_id, LogLevel.WARNING, "cancel", "Mission cancelled by user")
    logger.info("mission_cancelled", mission_id=mission_id)
    return {"status": "cancelled", "mission_id": mission_id}

@app.delete("/api/v1/missions/{mission_id}")
async def delete_mission(mission_id: str):
    """Delete a mission and all its associated data from orchestrator"""
    logger.info("deleting_mission", mission_id=mission_id)

    # Remove from memory
    if mission_id in missions:
        del missions[mission_id]

    # Close WebSocket connections
    if mission_id in ws_log_connections:
        for ws in list(ws_log_connections[mission_id]):
            try:
                await ws.close(code=1000, reason="Mission deleted")
            except Exception:
                pass
        del ws_log_connections[mission_id]

    # Delete from database
    result = await database.delete_mission(mission_id)

    logger.info("mission_deleted", mission_id=mission_id, result=result)
    return {
        "status": "deleted",
        "mission_id": mission_id,
        **result
    }

@app.delete("/api/v1/data/clear")
async def clear_all_data(confirm: str = ""):
    """Clear ALL data from orchestrator database"""
    if confirm != "YES":
        raise HTTPException(status_code=400, detail="Confirmation required: pass confirm=YES")

    logger.warning("clearing_all_data")

    # Clear memory
    missions.clear()

    # Close all WebSocket connections
    await close_all_websockets()

    # Clear database
    result = await database.clear_all_data()

    logger.info("all_data_cleared", result=result)
    return {
        "status": "cleared",
        **result
    }

@app.post("/api/v1/missions/{mission_id}/phases/{phase}")
async def trigger_phase(mission_id: str, phase: PhaseType):
    """Manually trigger a specific phase"""
    if mission_id not in missions:
        raise HTTPException(status_code=404, detail="Mission not found")

    await publish_log(mission_id, LogLevel.INFO, phase.value, f"Phase {phase.value} manually triggered")
    track_task(run_phase(mission_id, phase))
    return {"status": "triggered", "phase": phase, "mission_id": mission_id}

async def get_graph_stats(mission_id: str) -> Dict[str, int]:
    """Fetch current graph statistics for checkpoint validation."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{GRAPH_SERVICE}/api/v1/missions/{mission_id}/stats")
            if response.status_code == 200:
                stats = response.json()
                return stats.get("nodes_by_type", {})
            return {}
        except Exception as e:
            logger.warning("failed_to_get_graph_stats", error=str(e))
            return {}


async def checkpoint_validate(mission_id: str, phase: PhaseType, expected: Dict[str, str]) -> bool:
    """
    Validate checkpoint conditions after a phase completes.
    Returns True if checkpoint passes, False if warning conditions met.
    """
    stats = await get_graph_stats(mission_id)

    await publish_log(
        mission_id,
        LogLevel.INFO,
        "checkpoint",
        f"Graph stats after {phase.value}",
        {"stats": stats}
    )

    # Check expected conditions
    warnings = []
    for node_type, condition in expected.items():
        count = stats.get(node_type, 0)
        if condition == ">0" and count == 0:
            warnings.append(f"Expected {node_type} > 0, got {count}")
        elif condition.startswith(">="):
            min_val = int(condition[2:])
            if count < min_val:
                warnings.append(f"Expected {node_type} >= {min_val}, got {count}")

    if warnings:
        for warning in warnings:
            await publish_log(mission_id, LogLevel.WARNING, "checkpoint", warning)
        return False
    return True


async def execute_mission(mission_id: str):
    """Execute full mission pipeline - uses CrewAI agents when available."""
    mission = missions[mission_id]
    mission["status"] = MissionStatus.RUNNING
    mission["updated_at"] = datetime.utcnow()
    mission_start = datetime.utcnow()

    # Check if we should use CrewAI with real LLM reasoning
    use_crewai_mode = USE_CREWAI and CREWAI_AVAILABLE

    if use_crewai_mode:
        await publish_log(mission_id, LogLevel.INFO, "start", "Mission execution started with CrewAI agents (LLM reasoning mode)")
        logger.info("mission_execution_started_crewai", mission_id=mission_id, target=mission["target_domain"])
    else:
        await publish_log(mission_id, LogLevel.INFO, "start", "Mission execution started (HTTP microservices mode)")
        logger.info("mission_execution_started", mission_id=mission_id, target=mission["target_domain"])

    await publish_workflow_event(
        WorkflowEvent(
            run_id=mission_id,
            event_type="agent_started",
            source="orchestrator",
            payload={
                "agent_id": f"agent-orchestrator-{mission_id}",
                "agent_name": "Orchestrator",
                "phase": "INIT",
                "status": "running",
                "mode": "crewai" if use_crewai_mode else "microservices"
            },
            timestamp=datetime.utcnow().isoformat(),
        )
    )

    # === CrewAI MODE: Use real LLM agents with tools ===
    if use_crewai_mode:
        try:
            await publish_log(mission_id, LogLevel.INFO, "crewai", "Initializing CrewAI mission runner with LLM reasoning")

            # Get mode value
            mode_value = mission["mode"]
            if hasattr(mode_value, 'value'):
                mode_value = mode_value.value

            # Run the full CrewAI mission
            crewai_result = await run_crewai_mission(
                mission_id=mission_id,
                target_domain=mission["target_domain"],
                mode=mode_value
            )

            total_duration = (datetime.utcnow() - mission_start).total_seconds()

            # Handle None or non-dict results
            if crewai_result is None or not isinstance(crewai_result, dict):
                crewai_result = {
                    "status": "failed",
                    "error": f"Invalid CrewAI result: {type(crewai_result).__name__}"
                }

            if crewai_result.get("status") == "completed":
                mission["status"] = MissionStatus.COMPLETED
                # Use make_json_safe to recursively convert CrewOutput objects
                serializable_result = make_json_safe(crewai_result)
                mission["progress"]["current_metrics"]["crewai"] = serializable_result

                await publish_log(
                    mission_id,
                    LogLevel.INFO,
                    "complete",
                    f"CrewAI mission completed successfully in {total_duration:.2f}s",
                    {"total_duration": total_duration, "crewai_result": str(crewai_result)[:500]}
                )
                logger.info("crewai_mission_completed", mission_id=mission_id, duration=total_duration)

                await publish_workflow_event(
                    WorkflowEvent(
                        run_id=mission_id,
                        event_type="agent_finished",
                        source="orchestrator",
                        payload={
                            "agent_id": f"agent-orchestrator-{mission_id}",
                            "status": "completed",
                            "total_duration": total_duration,
                            "mode": "crewai"
                        },
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )
            else:
                mission["status"] = MissionStatus.FAILED
                error_msg = str(crewai_result.get("error") or crewai_result.get("reason") or "Unknown error")

                await publish_log(
                    mission_id,
                    LogLevel.ERROR,
                    "error",
                    f"CrewAI mission failed: {error_msg}",
                    {"error": error_msg, "duration": total_duration}
                )
                logger.error("crewai_mission_failed", mission_id=mission_id, error=error_msg)

            # Sanitize progress before DB persistence
            safe_progress = make_json_safe(mission["progress"])

            # Update database - isolated from CrewAI execution errors
            try:
                await database.update_mission(mission_id, {
                    "status": mission["status"].value,
                    "progress": safe_progress,
                    "updated_at": datetime.utcnow().isoformat()
                })
                logger.info("crewai_mission_persisted", mission_id=mission_id)
            except Exception as db_err:
                # DB error should NOT mark mission as FAILED if CrewAI succeeded
                logger.warning("crewai_mission_db_error", mission_id=mission_id, error=str(db_err))
                if mission["status"] == MissionStatus.COMPLETED:
                    # Don't change COMPLETED to FAILED just because of DB error
                    await publish_log(
                        mission_id,
                        LogLevel.WARNING,
                        "warning",
                        f"Mission completed but DB persistence failed: {db_err}",
                        {"db_error": str(db_err)}
                    )

            return

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            mission["status"] = MissionStatus.FAILED

            await publish_log(mission_id, LogLevel.ERROR, "error", f"CrewAI mission exception: {e}")
            logger.error("crewai_mission_exception", mission_id=mission_id, error=str(e), traceback=error_trace)

            try:
                await database.update_mission(mission_id, {
                    "status": "failed",
                    "updated_at": datetime.utcnow().isoformat()
                })
            except Exception as db_err:
                logger.warning("crewai_mission_db_error_on_fail", mission_id=mission_id, error=str(db_err))

            return

    # === LEGACY MODE: HTTP microservices (fallback) ===
    # Define phases with checkpoint expectations
    phases_config = [
        (PhaseType.OSINT, {"SUBDOMAIN": ">0"}),
        (PhaseType.SAFETY_NET, {}),  # No checkpoint - internal
        (PhaseType.ACTIVE_RECON, {"HTTP_SERVICE": ">0"}),
        (PhaseType.ENDPOINT_INTEL, {}),  # May have 0 endpoints if no HTTP services with endpoints
        (PhaseType.VERIFICATION, {}),  # May have 0 vulns
        (PhaseType.PLANNER, {}),  # May have 0 attack paths
        (PhaseType.REPORTING, {"REPORT": ">0"}),
    ]

    try:
        for i, (phase, checkpoint_expected) in enumerate(phases_config):
            if mission["status"] == MissionStatus.CANCELLED:
                await publish_log(mission_id, LogLevel.WARNING, phase.value, "Mission cancelled, stopping execution")
                break

            phase_start = datetime.utcnow()

            await publish_log(
                mission_id,
                LogLevel.INFO,
                phase.value,
                f"[{i+1}/{len(phases_config)}] Starting phase: {phase.value}",
                {"phase_index": i, "total_phases": len(phases_config), "start_time": phase_start.isoformat()}
            )
            logger.info("phase_starting", mission_id=mission_id, phase=phase.value, index=i+1, total=len(phases_config))

            await publish_workflow_event(
                WorkflowEvent(
                    run_id=mission_id,
                    event_type="agent_started",
                    source="orchestrator",
                    payload={
                        "agent_id": f"agent-{phase.value}",
                        "agent_name": phase.value,
                        "phase": phase.value,
                        "status": "running",
                    },
                    timestamp=phase_start.isoformat(),
                )
            )

            # Execute phase and WAIT for completion
            await run_phase(mission_id, phase)

            phase_end = datetime.utcnow()
            phase_duration = (phase_end - phase_start).total_seconds()

            mission["progress"]["phases_completed"].append(phase.value)

            # Run checkpoint validation if expectations defined
            if checkpoint_expected:
                await checkpoint_validate(mission_id, phase, checkpoint_expected)

            await publish_log(
                mission_id,
                LogLevel.INFO,
                phase.value,
                f"[{i+1}/{len(phases_config)}] Completed phase: {phase.value} in {phase_duration:.2f}s",
                {"duration_seconds": phase_duration, "end_time": phase_end.isoformat()}
            )
            logger.info("phase_completed", mission_id=mission_id, phase=phase.value, duration=phase_duration)

            await publish_workflow_event(
                WorkflowEvent(
                    run_id=mission_id,
                    event_type="agent_finished",
                    source="orchestrator",
                    payload={
                        "agent_id": f"agent-{phase.value}",
                        "status": "completed",
                        "duration": phase_duration,
                    },
                    timestamp=phase_end.isoformat(),
                )
            )

            # Update database with progress (P0.3: use make_json_safe)
            await database.update_mission(mission_id, {
                "current_phase": phase.value,
                "progress": make_json_safe(mission["progress"]),
                "updated_at": phase_end.isoformat()
            })

        if mission["status"] != MissionStatus.CANCELLED:
            mission["status"] = MissionStatus.COMPLETED
            total_duration = (datetime.utcnow() - mission_start).total_seconds()

            # Final graph stats
            final_stats = await get_graph_stats(mission_id)

            await publish_log(
                mission_id,
                LogLevel.INFO,
                "complete",
                f"Mission completed successfully in {total_duration:.2f}s",
                {"total_duration": total_duration, "final_stats": final_stats}
            )
            logger.info("mission_completed", mission_id=mission_id, duration=total_duration, stats=final_stats)

            await publish_workflow_event(
                WorkflowEvent(
                    run_id=mission_id,
                    event_type="agent_finished",
                    source="orchestrator",
                    payload={
                        "agent_id": f"agent-orchestrator-{mission_id}",
                        "status": "completed",
                        "total_duration": total_duration,
                    },
                    timestamp=datetime.utcnow().isoformat(),
                )
            )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error("mission_failed", mission_id=mission_id, error=str(e), traceback=error_trace)
        mission["status"] = MissionStatus.FAILED
        mission["progress"]["error"] = str(e)
        await publish_log(mission_id, LogLevel.ERROR, "error", f"Mission failed: {str(e)}", {"traceback": error_trace})
        await publish_workflow_event(
            WorkflowEvent(
                run_id=mission_id,
                event_type="agent_finished",
                source="orchestrator",
                payload={
                    "agent_id": f"agent-orchestrator-{mission_id}",
                    "status": "error",
                    "error": str(e),
                },
                timestamp=datetime.utcnow().isoformat(),
            )
        )

    mission["updated_at"] = datetime.utcnow()
    await database.update_mission(mission_id, {
        "status": mission["status"].value,
        "updated_at": mission["updated_at"].isoformat()
    })

async def run_phase(mission_id: str, phase: PhaseType):
    """Run a single phase with detailed logging and error handling."""
    mission = missions[mission_id]
    mission["current_phase"] = phase
    mission["updated_at"] = datetime.utcnow()

    logger.info("run_phase_called", mission_id=mission_id, phase=phase.value)
    start_time = datetime.utcnow()

    # Phase routing - maps phase to service URL
    service_map = {
        PhaseType.OSINT: OSINT_RUNNER,
        PhaseType.ACTIVE_RECON: ACTIVE_RECON,
        PhaseType.ENDPOINT_INTEL: ENDPOINT_INTEL,
        PhaseType.VERIFICATION: VERIFICATION,
        PhaseType.PLANNER: PLANNER,
        PhaseType.REPORTING: REPORTER
    }

    if phase == PhaseType.SAFETY_NET:
        # Safety net is internal check + fallback
        await check_safety_net(mission_id)
    elif phase in service_map:
        service_url = service_map[phase]
        # Use longer timeout for phases that do real work (5 minutes)
        timeout = httpx.Timeout(600.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                call_start = datetime.utcnow()
                call_start_iso = call_start.isoformat()

                await publish_log(
                    mission_id,
                    LogLevel.INFO,
                    phase.value,
                    f"Calling service: {service_url}/api/v1/execute",
                    {"service_url": service_url, "call_start": call_start_iso}
                )
                logger.info("service_call_starting", mission_id=mission_id, phase=phase.value, url=service_url)

                await publish_workflow_event(
                    WorkflowEvent(
                        run_id=mission_id,
                        event_type="tool_called",
                        source="orchestrator",
                        payload={
                            "tool_call_id": f"tool-{phase.value}-{mission_id}",
                            "tool": f"{phase.value}-service",
                            "agent_id": f"agent-{phase.value}",
                            "start_time": call_start_iso,
                        },
                        timestamp=call_start_iso,
                    )
                )

                # Prepare mode value - handle both string and enum
                mode_value = mission["mode"]
                if hasattr(mode_value, 'value'):
                    mode_value = mode_value.value

                request_payload = {
                    "mission_id": mission_id,
                    "target_domain": mission["target_domain"],
                    "mode": mode_value,
                    "options": mission.get("options", {})
                }
                logger.debug("service_request_payload", payload=request_payload)

                # Make the HTTP call and WAIT for response
                response = await client.post(
                    f"{service_url}/api/v1/execute",
                    json=request_payload
                )

                call_end = datetime.utcnow()
                call_duration = (call_end - call_start).total_seconds()

                logger.info(
                    "service_call_completed",
                    mission_id=mission_id,
                    phase=phase.value,
                    status_code=response.status_code,
                    duration=call_duration
                )

                if response.status_code == 200:
                    result = response.json()
                    phase_status = result.get("status", "unknown")
                    phase_results = result.get("results", {})
                    phase_duration = result.get("duration", 0)

                    mission["progress"]["current_metrics"][phase.value] = phase_results

                    await publish_log(
                        mission_id,
                        LogLevel.INFO,
                        phase.value,
                        f"Service completed: status={phase_status}, duration={phase_duration:.2f}s, call_duration={call_duration:.2f}s",
                        {
                            "service_status": phase_status,
                            "service_duration": phase_duration,
                            "call_duration": call_duration,
                            "results_summary": {k: v if not isinstance(v, list) else len(v) for k, v in phase_results.items()} if isinstance(phase_results, dict) else phase_results
                        }
                    )

                    await publish_workflow_event(
                        WorkflowEvent(
                            run_id=mission_id,
                            event_type="tool_finished",
                            source="orchestrator",
                            payload={
                                "tool_call_id": f"tool-{phase.value}-{mission_id}",
                                "status": "success",
                                "service_status": phase_status,
                                "duration": call_duration,
                                "end_time": call_end.isoformat(),
                            },
                            timestamp=call_end.isoformat(),
                        )
                    )
                else:
                    error_text = response.text[:500] if response.text else "No response body"
                    await publish_log(
                        mission_id,
                        LogLevel.ERROR,
                        phase.value,
                        f"Service returned error status {response.status_code}",
                        {"status_code": response.status_code, "error": error_text, "duration": call_duration}
                    )
                    logger.error("service_error_response", status_code=response.status_code, error=error_text)

                    await publish_workflow_event(
                        WorkflowEvent(
                            run_id=mission_id,
                            event_type="tool_finished",
                            source="orchestrator",
                            payload={
                                "tool_call_id": f"tool-{phase.value}-{mission_id}",
                                "status": "failure",
                                "error_code": response.status_code,
                                "end_time": call_end.isoformat(),
                            },
                            timestamp=call_end.isoformat(),
                        )
                    )

            except httpx.TimeoutException as e:
                error_msg = f"Service timeout after 600s: {str(e)}"
                logger.error("service_timeout", phase=phase.value, error=str(e))
                await publish_log(mission_id, LogLevel.ERROR, phase.value, error_msg)
                await publish_workflow_event(
                    WorkflowEvent(
                        run_id=mission_id,
                        event_type="tool_finished",
                        source="orchestrator",
                        payload={
                            "tool_call_id": f"tool-{phase.value}-{mission_id}",
                            "status": "timeout",
                            "error": str(e),
                            "end_time": datetime.utcnow().isoformat(),
                        },
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )

            except httpx.RequestError as e:
                error_msg = f"Service connection error: {str(e)}"
                logger.error("service_connection_error", phase=phase.value, error=str(e))
                await publish_log(mission_id, LogLevel.ERROR, phase.value, error_msg)
                await publish_workflow_event(
                    WorkflowEvent(
                        run_id=mission_id,
                        event_type="tool_finished",
                        source="orchestrator",
                        payload={
                            "tool_call_id": f"tool-{phase.value}-{mission_id}",
                            "status": "failure",
                            "end_time": datetime.utcnow().isoformat(),
                        },
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )

    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info("phase_completed", mission_id=mission_id, phase=phase, duration=duration)

async def check_safety_net(mission_id: str):
    """
    Check if mission should continue based on discovery results.
    If no subdomains were found, inject fallback apex + www subdomains.
    """
    await publish_log(mission_id, LogLevel.INFO, "safety_net", "Running safety net checks")

    mission = missions.get(mission_id)
    if not mission:
        logger.warning("safety_net_mission_not_found", mission_id=mission_id)
        return

    target_domain = mission.get("target_domain", "")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{GRAPH_SERVICE}/api/v1/missions/{mission_id}/stats")
            if response.status_code == 200:
                stats = response.json()
                subdomains = stats.get("nodes_by_type", {}).get("SUBDOMAIN", 0)
                http_services = stats.get("nodes_by_type", {}).get("HTTP_SERVICE", 0)
                total_nodes = stats.get("total_nodes", 0)

                await publish_log(
                    mission_id,
                    LogLevel.INFO,
                    "safety_net",
                    f"Graph stats: {total_nodes} nodes, {subdomains} subdomains, {http_services} http_services",
                    {"total_nodes": total_nodes, "subdomains": subdomains, "http_services": http_services}
                )

                # Fallback: If no subdomains, inject apex + www
                if subdomains == 0 and target_domain:
                    await publish_log(
                        mission_id,
                        LogLevel.WARNING,
                        "safety_net",
                        f"No subdomains discovered - injecting fallback: {target_domain}, www.{target_domain}"
                    )

                    # Inject apex domain
                    await client.post(
                        f"{GRAPH_SERVICE}/api/v1/nodes",
                        json={
                            "mission_id": mission_id,
                            "type": "SUBDOMAIN",
                            "label": target_domain,
                            "properties": {
                                "name": target_domain,
                                "priority": 10,
                                "tag": "SAFETY_NET_FALLBACK",
                                "category": "RECON"
                            }
                        }
                    )

                    # Inject www subdomain
                    www_domain = f"www.{target_domain}"
                    await client.post(
                        f"{GRAPH_SERVICE}/api/v1/nodes",
                        json={
                            "mission_id": mission_id,
                            "type": "SUBDOMAIN",
                            "label": www_domain,
                            "properties": {
                                "name": www_domain,
                                "priority": 10,
                                "tag": "SAFETY_NET_FALLBACK",
                                "category": "RECON"
                            }
                        }
                    )

                    await publish_log(
                        mission_id,
                        LogLevel.INFO,
                        "safety_net",
                        f"Fallback subdomains injected: {target_domain}, {www_domain}"
                    )

                elif subdomains > 0:
                    await publish_log(
                        mission_id,
                        LogLevel.INFO,
                        "safety_net",
                        f"Safety net passed: {subdomains} subdomains available for active recon"
                    )

        except httpx.RequestError as e:
            await publish_log(
                mission_id,
                LogLevel.WARNING,
                "safety_net",
                f"Could not fetch graph stats: {str(e)} - continuing anyway"
            )

# SSE endpoint for logs (alternative to WebSocket)
@app.get("/api/v1/sse/logs/{mission_id}")
async def sse_logs(mission_id: str):
    """Server-Sent Events endpoint for logs"""
    from starlette.responses import StreamingResponse

    async def log_generator():
        queue: asyncio.Queue = asyncio.Queue()

        # Create temporary connection tracking
        if mission_id not in ws_log_connections:
            ws_log_connections[mission_id] = set()

        class SSEConnection:
            async def send_json(self, data):
                await queue.put(data)

        sse_conn = SSEConnection()
        ws_log_connections[mission_id].add(sse_conn)

        try:
            while True:
                try:
                    log = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(log)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
        finally:
            ws_log_connections[mission_id].discard(sse_conn)

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
