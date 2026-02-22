"""
log_storage.py — Async SQLite log store (non-blocking event loop safe)
Uses aiosqlite so log ingestion/queries never block the asyncio loop.
"""
import aiosqlite
import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from devops_copilot.utils.logger import logger


class LogStorage:
    """Async Elasticsearch-like log store backed by SQLite via aiosqlite."""

    def __init__(self, db_path: str = "devops_logs.db"):
        self.db_path = db_path

    async def _init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    service TEXT,
                    level TEXT,
                    message TEXT,
                    metadata_json TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS spike_tracker (
                    service TEXT PRIMARY KEY,
                    spike_started_at REAL
                )
            """)
            await db.commit()
        logger.info(f"[AsyncLogStorage] Initialized at {self.db_path}")

    async def setup(self):
        """Call once on startup to ensure tables exist."""
        await self._init_db()

    async def ingest_log(self, service: str, level: str, message: str,
                         metadata: Optional[Dict[str, Any]] = None):
        ts = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO logs (timestamp, service, level, message, metadata_json) VALUES (?,?,?,?,?)",
                (ts, service, level, message, json.dumps(metadata or {}))
            )
            if level == "ERROR":
                await db.execute(
                    "INSERT OR IGNORE INTO spike_tracker (service, spike_started_at) VALUES (?,?)",
                    (service, ts)
                )
            await db.commit()

    async def query_logs(self, service: Optional[str] = None, level: Optional[str] = None,
                         start_time: Optional[float] = None, limit: int = 100) -> List[Dict[str, Any]]:
        query = "SELECT timestamp, service, level, message, metadata_json FROM logs WHERE 1=1"
        params: list = []
        if service:
            query += " AND service = ?"; params.append(service)
        if level:
            query += " AND level = ?"; params.append(level)
        if start_time:
            query += " AND timestamp >= ?"; params.append(start_time)
        query += " ORDER BY timestamp DESC LIMIT ?"; params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        return [
            {"timestamp": r[0], "service": r[1], "level": r[2],
             "message": r[3], "metadata": json.loads(r[4])}
            for r in rows
        ]

    async def get_error_rate(self, service: str, window_seconds: int = 300) -> float:
        start_time = time.time() - window_seconds
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM logs WHERE service=? AND timestamp>=?",
                (service, start_time)
            ) as cur:
                total = (await cur.fetchone())[0]
            if total == 0:
                return 0.0
            async with db.execute(
                "SELECT COUNT(*) FROM logs WHERE service=? AND level='ERROR' AND timestamp>=?",
                (service, start_time)
            ) as cur:
                errors = (await cur.fetchone())[0]
        return errors / total

    async def get_spike_start(self, service: str) -> Optional[float]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT spike_started_at FROM spike_tracker WHERE service=?", (service,)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else None

    async def clear_spike(self, service: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM spike_tracker WHERE service=?", (service,))
            await db.commit()

    # ── Sync shims ─────────────────────────────────────────────────────────────
    # Tool functions are synchronous. These shims run async methods in a fresh
    # background thread with its own event loop, so they are safe to call from
    # inside an already-running asyncio event loop (e.g. the engine's loop).

    def _run_sync(self, coro):
        """Run an async coroutine in a dedicated background thread."""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    def ingest_log_sync(self, service: str, level: str, message: str,
                        metadata: Optional[Dict[str, Any]] = None):
        self._run_sync(self.ingest_log(service, level, message, metadata))

    def get_error_rate_sync(self, service: str, window_seconds: int = 300) -> float:
        return self._run_sync(self.get_error_rate(service, window_seconds))

    def get_spike_start_sync(self, service: str) -> Optional[float]:
        return self._run_sync(self.get_spike_start(service))

    def clear_spike_sync(self, service: str):
        self._run_sync(self.clear_spike(service))

    def query_logs_sync(self, service: Optional[str] = None, level: Optional[str] = None,
                        start_time: Optional[float] = None, limit: int = 100):
        return self._run_sync(self.query_logs(service, level, start_time, limit))
