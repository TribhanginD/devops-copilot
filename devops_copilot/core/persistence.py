"""
persistence.py — Async SQLite session state (non-blocking)
"""
import aiosqlite
import json
from typing import Dict, Any, Optional, List
from devops_copilot.utils.logger import logger


class PersistenceLayer:
    """Async session state store backed by SQLite via aiosqlite."""

    def __init__(self, db_path: str = "agentnexus_state.db"):
        self.db_path = db_path

    async def setup(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT,
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            await db.commit()
        logger.info(f"[AsyncPersistence] Initialized at {self.db_path}")

    async def save_session(self, session_id: str, state: Dict[str, Any]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sessions (session_id, state_json) VALUES (?,?)",
                (session_id, json.dumps(state))
            )
            await db.commit()
        logger.debug(f"Saved session {session_id}")

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT state_json FROM sessions WHERE session_id=?", (session_id,)
            ) as cur:
                row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    async def list_sessions(self) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT session_id FROM sessions") as cur:
                rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def set_approved(self, session_id: str):
        """Set human_approved=True in session metadata. Called by the API."""
        state = await self.load_session(session_id)
        if state is None:
            raise KeyError(f"Session '{session_id}' not found.")
        state.setdefault("metadata", {})["human_approved"] = True
        await self.save_session(session_id, state)
        logger.info(f"✅ Approval granted for session {session_id}")
