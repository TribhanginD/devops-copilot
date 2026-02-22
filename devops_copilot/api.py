"""
api.py — FastAPI server exposing DevOps Copilot control plane.

Endpoints:
  POST /sessions/{session_id}/approve   — Grant human approval (unblocks engine)
  POST /sessions/{session_id}/reject    — Reject proposed action (marks false positive)
  GET  /sessions/{session_id}           — Inspect current session state
  GET  /sessions                        — List all active sessions
  GET  /health                          — Liveness probe
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from devops_copilot.core.persistence import PersistenceLayer
from devops_copilot.core.observability import FALSE_POSITIVE_TOTAL
from devops_copilot.utils.logger import logger
import os

app = FastAPI(
    title="AgentNexus DevOps Copilot API",
    description="Control plane for the AI DevOps Copilot — approve/reject agent actions.",
    version="1.0.0",
)

# Shared persistence layer (same DB as the engine)
_db_path = os.getenv("DATABASE_URL", "agentnexus_state.db").replace("sqlite:///./", "")
persistence = PersistenceLayer(db_path=_db_path)


@app.on_event("startup")
async def _startup():
    await persistence.setup()
    logger.info("API server started.")


# ── Request/Response models ────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    reason: Optional[str] = "Approved via API"


class RejectRequest(BaseModel):
    reason: Optional[str] = "Rejected — false positive"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/sessions")
async def list_sessions():
    sessions = await persistence.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    state = await persistence.load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return state


@app.post("/sessions/{session_id}/approve")
async def approve_action(session_id: str, body: ApproveRequest = ApproveRequest()):
    """
    Grant human approval for a PENDING_APPROVAL action.
    The engine polls session state — setting human_approved=True unblocks it.
    """
    try:
        await persistence.set_approved(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    logger.info(f"Approved session {session_id}: {body.reason}")
    return {"session_id": session_id, "status": "approved", "reason": body.reason}


@app.post("/sessions/{session_id}/reject")
async def reject_action(session_id: str, body: RejectRequest = RejectRequest()):
    """
    Reject a pending action and track it as a false positive in Prometheus.
    """
    state = await persistence.load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    # Record false positive metric
    FALSE_POSITIVE_TOTAL.inc()

    # Mark rejected so the engine can clean up or try a different plan
    state.setdefault("metadata", {})["human_approved"] = False
    state["metadata"]["rejected"] = True
    await persistence.save_session(session_id, state)

    logger.warning(f"Rejected session {session_id}: {body.reason}")
    return {"session_id": session_id, "status": "rejected", "reason": body.reason}
