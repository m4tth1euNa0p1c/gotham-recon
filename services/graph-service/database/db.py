"""
Shared Database Module for Gotham Recon Services
SQLite with async support via aiosqlite

P0.2: Implements deterministic edge IDs for idempotent upserts
Edge ID = sha1("{relation}|{from_node}|{to_node}|{mission_id}")[:16]
"""
import aiosqlite
import json
import os
import hashlib
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


def generate_edge_id(from_node: str, to_node: str, relation: str, mission_id: str) -> str:
    """
    Generate deterministic edge ID using SHA1 hash.
    P0.2: edge_key = "{relation}|{from}|{to}|{mission}" → sha1[:16]
    """
    edge_key = f"{relation}|{from_node}|{to_node}|{mission_id}"
    return hashlib.sha1(edge_key.encode()).hexdigest()[:16]

# Database path - use environment variable or default
DB_PATH = os.getenv("DATABASE_PATH", "/data/gotham.db")

# Ensure data directory exists
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

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

        # Edges table - P0.2: Use deterministic text ID instead of auto-increment
        await db.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                relation TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                properties TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (mission_id) REFERENCES missions(id)
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

        # Layouts table for workflow visualization
        await db.execute("""
            CREATE TABLE IF NOT EXISTS layouts (
                mission_id TEXT PRIMARY KEY,
                positions TEXT NOT NULL,
                zoom REAL DEFAULT 1.0,
                pan TEXT,
                updated_at TEXT NOT NULL,
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


async def update_node(node_id: str, node_data: Dict) -> Dict:
    """
    Update a node in the database (Lot 3: Deep Verification support).
    Used for updating vulnerability status and evidence.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE nodes
            SET properties = ?, updated_at = ?
            WHERE id = ?
        """, (
            json.dumps(node_data.get("properties", {})),
            node_data.get("updated_at", datetime.utcnow().isoformat()),
            node_id
        ))
        await db.commit()
    return node_data

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
    """
    Create an edge with idempotent upsert.
    P0.2: Uses deterministic ID (sha1 hash) and INSERT OR IGNORE for idempotence.
    """
    # Generate deterministic edge ID
    edge_id = edge_data.get("id") or generate_edge_id(
        edge_data["from_node"],
        edge_data["to_node"],
        edge_data["relation"],
        edge_data["mission_id"]
    )
    edge_data["id"] = edge_id

    async with aiosqlite.connect(DB_PATH) as db:
        # INSERT OR IGNORE for idempotent upsert - no duplicate errors
        await db.execute("""
            INSERT OR IGNORE INTO edges (id, from_node, to_node, relation, mission_id, properties, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            edge_id,
            edge_data["from_node"],
            edge_data["to_node"],
            edge_data["relation"],
            edge_data["mission_id"],
            json.dumps(edge_data.get("properties", {})),
            edge_data.get("created_at", datetime.utcnow().isoformat())
        ))
        await db.commit()
    return edge_data


async def create_edges_batch(edges: List[Dict]) -> List[Dict]:
    """
    Batch create edges with idempotent upsert.
    P0.2: Uses deterministic IDs and single transaction for atomicity (P0.4).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        for edge_data in edges:
            # Generate deterministic edge ID
            edge_id = edge_data.get("id") or generate_edge_id(
                edge_data["from_node"],
                edge_data["to_node"],
                edge_data["relation"],
                edge_data["mission_id"]
            )
            edge_data["id"] = edge_id

            await db.execute("""
                INSERT OR IGNORE INTO edges (id, from_node, to_node, relation, mission_id, properties, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                edge_id,
                edge_data["from_node"],
                edge_data["to_node"],
                edge_data["relation"],
                edge_data["mission_id"],
                json.dumps(edge_data.get("properties", {})),
                edge_data.get("created_at", datetime.utcnow().isoformat())
            ))
        await db.commit()
    return edges

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
                    "id": row["id"],
                    "from_node": row["from_node"],
                    "to_node": row["to_node"],
                    "relation": row["relation"],
                    "mission_id": row["mission_id"],
                    "properties": json.loads(row["properties"] or "{}"),
                    "created_at": row["created_at"]
                })
    return edges

async def batch_upsert(nodes: List[Dict], edges: List[Dict]) -> Dict:
    """
    P0.4: Atomic batch upsert of nodes and edges in a single transaction.
    All operations succeed or all fail together.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            # Insert/update all nodes
            for node_data in nodes:
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

            # Insert all edges with deterministic IDs (INSERT OR IGNORE)
            for edge_data in edges:
                edge_id = edge_data.get("id") or generate_edge_id(
                    edge_data["from_node"],
                    edge_data["to_node"],
                    edge_data["relation"],
                    edge_data["mission_id"]
                )
                await db.execute("""
                    INSERT OR IGNORE INTO edges (id, from_node, to_node, relation, mission_id, properties, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    edge_id,
                    edge_data["from_node"],
                    edge_data["to_node"],
                    edge_data["relation"],
                    edge_data["mission_id"],
                    json.dumps(edge_data.get("properties", {})),
                    edge_data.get("created_at", datetime.utcnow().isoformat())
                ))

            # Commit the transaction atomically
            await db.commit()

            return {
                "nodes_upserted": len(nodes),
                "edges_upserted": len(edges)
            }
        except Exception as e:
            # Rollback on any error
            await db.rollback()
            raise e


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

# Layout persistence for workflow visualization
async def save_layout(mission_id: str, layout_data: Dict) -> Dict:
    """Save workflow layout for a mission"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO layouts (mission_id, positions, zoom, pan, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            mission_id,
            json.dumps(layout_data.get("positions", {})),
            layout_data.get("zoom", 1.0),
            json.dumps(layout_data.get("pan", {"x": 0, "y": 0})),
            layout_data.get("updated_at", datetime.utcnow().isoformat())
        ))
        await db.commit()
    return layout_data

async def get_layout(mission_id: str) -> Optional[Dict]:
    """Get workflow layout for a mission"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM layouts WHERE mission_id = ?", (mission_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "positions": json.loads(row["positions"] or "{}"),
                    "zoom": row["zoom"],
                    "pan": json.loads(row["pan"] or '{"x": 0, "y": 0}'),
                    "updated_at": row["updated_at"]
                }
    return None

# ==================== DELETION FUNCTIONS ====================

async def delete_mission(mission_id: str) -> Dict:
    """Delete a mission and all its associated data (nodes, edges, logs, layouts)"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Get counts before deletion
        async with db.execute("SELECT COUNT(*) as cnt FROM nodes WHERE mission_id = ?", (mission_id,)) as cursor:
            nodes_deleted = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) as cnt FROM edges WHERE mission_id = ?", (mission_id,)) as cursor:
            edges_deleted = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) as cnt FROM logs WHERE mission_id = ?", (mission_id,)) as cursor:
            logs_deleted = (await cursor.fetchone())[0]

        # Delete all data for this mission
        await db.execute("DELETE FROM nodes WHERE mission_id = ?", (mission_id,))
        await db.execute("DELETE FROM edges WHERE mission_id = ?", (mission_id,))
        await db.execute("DELETE FROM logs WHERE mission_id = ?", (mission_id,))
        await db.execute("DELETE FROM layouts WHERE mission_id = ?", (mission_id,))
        await db.execute("DELETE FROM missions WHERE id = ?", (mission_id,))
        await db.commit()

    return {
        "mission_id": mission_id,
        "nodes_deleted": nodes_deleted,
        "edges_deleted": edges_deleted,
        "logs_deleted": logs_deleted
    }

async def clear_all_data() -> Dict:
    """Clear all data from the database (missions, nodes, edges, logs, layouts)"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Get counts before deletion
        async with db.execute("SELECT COUNT(*) as cnt FROM missions") as cursor:
            missions_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) as cnt FROM nodes") as cursor:
            nodes_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) as cnt FROM edges") as cursor:
            edges_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) as cnt FROM logs") as cursor:
            logs_count = (await cursor.fetchone())[0]

        # Delete all data
        await db.execute("DELETE FROM nodes")
        await db.execute("DELETE FROM edges")
        await db.execute("DELETE FROM logs")
        await db.execute("DELETE FROM layouts")
        await db.execute("DELETE FROM missions")
        await db.commit()

    return {
        "missions_deleted": missions_count,
        "nodes_deleted": nodes_count,
        "edges_deleted": edges_count,
        "logs_deleted": logs_count
    }

async def delete_mission_history(mission_id: str) -> Dict:
    """Delete only logs/history for a mission (keeps nodes and edges)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) as cnt FROM logs WHERE mission_id = ?", (mission_id,)) as cursor:
            logs_deleted = (await cursor.fetchone())[0]

        await db.execute("DELETE FROM logs WHERE mission_id = ?", (mission_id,))
        await db.commit()

    return {
        "mission_id": mission_id,
        "logs_deleted": logs_deleted
    }
