"""
Shared Database Module for Gotham Recon Services
SQLite with async support via aiosqlite
"""
import aiosqlite
import json
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path

# Database path
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = os.getenv("DATABASE_PATH", str(DB_DIR / "gotham.db"))

# Ensure data directory exists
DB_DIR.mkdir(parents=True, exist_ok=True)

async def get_db() -> aiosqlite.Connection:
    """Get database connection"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

async def init_db():
    """Initialize database tables"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Missions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                id TEXT PRIMARY KEY,
                target_domain TEXT NOT NULL,
                mode TEXT DEFAULT 'aggressive',
                status TEXT DEFAULT 'pending',
                current_phase TEXT,
                seed_subdomains TEXT,
                options TEXT,
                progress TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Nodes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                properties TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (mission_id) REFERENCES missions(id)
            )
        """)

        # Edges table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                relation TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (mission_id) REFERENCES missions(id),
                UNIQUE(from_node, to_node, relation, mission_id)
            )
        """)

        # Logs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                level TEXT NOT NULL,
                phase TEXT,
                message TEXT NOT NULL,
                metadata TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (mission_id) REFERENCES missions(id)
            )
        """)

        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_nodes_mission ON nodes(mission_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_edges_mission ON edges(mission_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_mission ON logs(mission_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")

        await db.commit()
        print(f"[DB] Database initialized at {DB_PATH}")

# Mission CRUD
async def create_mission(mission_data: Dict) -> Dict:
    """Create a new mission"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO missions (id, target_domain, mode, status, current_phase, seed_subdomains, options, progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mission_data["id"],
            mission_data["target_domain"],
            mission_data.get("mode", "aggressive"),
            mission_data.get("status", "pending"),
            mission_data.get("current_phase"),
            json.dumps(mission_data.get("seed_subdomains", [])),
            json.dumps(mission_data.get("options", {})),
            json.dumps(mission_data.get("progress", {})),
            mission_data["created_at"],
            mission_data["updated_at"]
        ))
        await db.commit()
    return mission_data

async def get_mission(mission_id: str) -> Optional[Dict]:
    """Get a mission by ID"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "target_domain": row["target_domain"],
                    "mode": row["mode"],
                    "status": row["status"],
                    "current_phase": row["current_phase"],
                    "seed_subdomains": json.loads(row["seed_subdomains"] or "[]"),
                    "options": json.loads(row["options"] or "{}"),
                    "progress": json.loads(row["progress"] or "{}"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
    return None

async def update_mission(mission_id: str, updates: Dict) -> Optional[Dict]:
    """Update a mission"""
    async with aiosqlite.connect(DB_PATH) as db:
        set_clauses = []
        values = []
        for key, value in updates.items():
            if key in ["progress", "options", "seed_subdomains"]:
                value = json.dumps(value)
            set_clauses.append(f"{key} = ?")
            values.append(value)

        values.append(datetime.utcnow().isoformat())
        values.append(mission_id)

        await db.execute(
            f"UPDATE missions SET {', '.join(set_clauses)}, updated_at = ? WHERE id = ?",
            values
        )
        await db.commit()
    return await get_mission(mission_id)

async def list_missions(limit: int = 20, offset: int = 0) -> tuple[List[Dict], int]:
    """List missions with pagination"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Get total count
        async with db.execute("SELECT COUNT(*) as cnt FROM missions") as cursor:
            row = await cursor.fetchone()
            total = row["cnt"]

        # Get missions
        async with db.execute(
            "SELECT * FROM missions ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ) as cursor:
            missions = []
            async for row in cursor:
                missions.append({
                    "id": row["id"],
                    "target_domain": row["target_domain"],
                    "mode": row["mode"],
                    "status": row["status"],
                    "current_phase": row["current_phase"],
                    "seed_subdomains": json.loads(row["seed_subdomains"] or "[]"),
                    "options": json.loads(row["options"] or "{}"),
                    "progress": json.loads(row["progress"] or "{}"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })
    return missions, total

# Node CRUD
async def create_node(node_data: Dict) -> Dict:
    """Create or update a node"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO nodes (id, type, mission_id, properties, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            node_data["id"],
            node_data["type"],
            node_data["mission_id"],
            json.dumps(node_data.get("properties", {})),
            node_data.get("created_at", datetime.utcnow().isoformat()),
            datetime.utcnow().isoformat()
        ))
        await db.commit()
    return node_data

async def get_node(node_id: str) -> Optional[Dict]:
    """Get a node by ID"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "type": row["type"],
                    "mission_id": row["mission_id"],
                    "properties": json.loads(row["properties"] or "{}"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
    return None

async def delete_node(node_id: str) -> bool:
    """Delete a node"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        await db.execute("DELETE FROM edges WHERE from_node = ? OR to_node = ?", (node_id, node_id))
        await db.commit()
    return True

async def query_nodes(mission_id: str, node_types: List[str] = None, risk_score_min: int = None, limit: int = 100, offset: int = 0) -> tuple[List[Dict], int]:
    """Query nodes with filters"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        where_clauses = ["mission_id = ?"]
        params = [mission_id]

        if node_types:
            placeholders = ",".join(["?" for _ in node_types])
            where_clauses.append(f"type IN ({placeholders})")
            params.extend(node_types)

        where_sql = " AND ".join(where_clauses)

        # Get total
        async with db.execute(f"SELECT COUNT(*) as cnt FROM nodes WHERE {where_sql}", params) as cursor:
            row = await cursor.fetchone()
            total = row["cnt"]

        # Get nodes
        params.extend([limit, offset])
        async with db.execute(
            f"SELECT * FROM nodes WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params
        ) as cursor:
            nodes = []
            async for row in cursor:
                node = {
                    "id": row["id"],
                    "type": row["type"],
                    "mission_id": row["mission_id"],
                    "properties": json.loads(row["properties"] or "{}"),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                # Filter by risk_score if specified
                if risk_score_min is not None:
                    if node["properties"].get("risk_score", 0) < risk_score_min:
                        continue
                nodes.append(node)
    return nodes, total

# Edge CRUD
async def create_edge(edge_data: Dict) -> Dict:
    """Create an edge"""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO edges (from_node, to_node, relation, mission_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                edge_data["from_node"],
                edge_data["to_node"],
                edge_data["relation"],
                edge_data["mission_id"],
                edge_data.get("created_at", datetime.utcnow().isoformat())
            ))
            await db.commit()
        except aiosqlite.IntegrityError:
            pass  # Edge already exists
    return edge_data

async def get_edges(mission_id: str) -> List[Dict]:
    """Get all edges for a mission"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM edges WHERE mission_id = ?",
            (mission_id,)
        ) as cursor:
            edges = []
            async for row in cursor:
                edges.append({
                    "from_node": row["from_node"],
                    "to_node": row["to_node"],
                    "relation": row["relation"],
                    "mission_id": row["mission_id"],
                    "created_at": row["created_at"]
                })
    return edges

async def get_mission_stats(mission_id: str) -> Dict:
    """Get statistics for a mission"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Total nodes
        async with db.execute("SELECT COUNT(*) as cnt FROM nodes WHERE mission_id = ?", (mission_id,)) as cursor:
            row = await cursor.fetchone()
            total_nodes = row["cnt"]

        # Total edges
        async with db.execute("SELECT COUNT(*) as cnt FROM edges WHERE mission_id = ?", (mission_id,)) as cursor:
            row = await cursor.fetchone()
            total_edges = row["cnt"]

        # Nodes by type
        async with db.execute(
            "SELECT type, COUNT(*) as cnt FROM nodes WHERE mission_id = ? GROUP BY type",
            (mission_id,)
        ) as cursor:
            nodes_by_type = {}
            async for row in cursor:
                nodes_by_type[row["type"]] = row["cnt"]

    return {
        "mission_id": mission_id,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "nodes_by_type": nodes_by_type
    }

# Log functions
async def create_log(log_data: Dict) -> Dict:
    """Create a log entry"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO logs (mission_id, level, phase, message, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            log_data["mission_id"],
            log_data["level"],
            log_data.get("phase", ""),
            log_data["message"],
            json.dumps(log_data.get("metadata", {})),
            log_data.get("timestamp", datetime.utcnow().isoformat())
        ))
        await db.commit()
    return log_data

async def get_logs(mission_id: str, limit: int = 100) -> List[Dict]:
    """Get logs for a mission"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM logs WHERE mission_id = ? ORDER BY timestamp DESC LIMIT ?",
            (mission_id, limit)
        ) as cursor:
            logs = []
            async for row in cursor:
                logs.append({
                    "mission_id": row["mission_id"],
                    "level": row["level"],
                    "phase": row["phase"],
                    "message": row["message"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "timestamp": row["timestamp"]
                })
    return logs
