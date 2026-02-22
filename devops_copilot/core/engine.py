"""
engine.py — WorkflowEngine with async persistence, approval gate, and telemetry.
"""
from typing import Optional
import json
import uuid

from devops_copilot.agents.workflow_agents import PlannerAgent, ExecutorAgent
from devops_copilot.agents.base import AgentState
from devops_copilot.core.memory import MemorySystem
from devops_copilot.core.persistence import PersistenceLayer
from devops_copilot.core.observability import start_metrics_server
from devops_copilot.core.telemetry import tracer
from devops_copilot.utils.logger import logger


class WorkflowEngine:
    """Orchestrates the Multi-Agent ReAct loop with async persistence."""

    def __init__(self, db_path: str = "agentnexus_state.db",
                 memory_dir: str = "./chroma_db", run_metrics: bool = True):
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.memory = MemorySystem(persist_directory=memory_dir)
        self.persistence = PersistenceLayer(db_path=db_path)

        if run_metrics:
            try:
                start_metrics_server()
            except Exception as e:
                logger.warning(f"Could not start metrics server: {e}")

    async def run(self, user_request: str, session_id: Optional[str] = None,
                  max_steps: int = 5) -> str:
        """Run the incremental Plan → Execute → Reflect loop.

        Automatically awaits setup() on first use.
        Blocks on PENDING_APPROVAL and resumes when the API sets human_approved=True.
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        # Ensure DB tables exist (idempotent)
        await self.persistence.setup()

        # Load or create session state
        stored_state = await self.persistence.load_session(session_id)
        if stored_state:
            state = AgentState(**stored_state)
            logger.info(f"Resumed session {session_id}")
        else:
            state = AgentState(session_id=session_id)
            logger.info(f"Started new session {session_id}")

        results = []
        for i in range(max_steps):
            # 0. Context retrieval
            memories = self.memory.search_memories(user_request)
            context_str = str(memories.get("documents", []))

            # Start OTel-style trace for this turn
            turn_trace = tracer.start_trace(f"Turn {i+1}", parent_id=session_id)

            # 1. Incremental Planning — one step at a time
            logger.info(f"--- Step {i+1} Planning ---")
            plan = await self.planner.chat(
                f"Context: {context_str}\nRequest: {user_request}\nPrevious results: {results}",
                state
            )

            if not plan.steps:
                logger.info("Planner signals completion (empty steps).")
                turn_trace.finish(status="completed", metadata={"info": "no more steps"})
                break

            step = plan.steps[0]

            # 2. Human-in-the-loop gate
            logger.info(f"Executing step: {step.tool_name}")
            needs_approval = "REQUIRES_APPROVAL" in step.thought.upper()

            if needs_approval and not state.metadata.get("human_approved"):
                logger.warning(f"⏸  ACTION BLOCKED pending approval: {step.tool_name}")
                results.append({
                    "step": i + 1,
                    "status": "PENDING_APPROVAL",
                    "tool": step.tool_name,
                    "thought": step.thought,
                    "approve_endpoint": f"POST /sessions/{session_id}/approve"
                })
                await self.persistence.save_session(session_id, state.model_dump())
                return json.dumps(results, indent=2)

            result = await self.executor.chat(step, state)
            results.append({"step": i + 1, "status": "executed",
                            "tool": step.tool_name, "result": result})

            # Reset approval flag after single use
            state.metadata["human_approved"] = False

            # 3. Persist state
            await self.persistence.save_session(session_id, state.model_dump())

            # Finish trace
            turn_trace.finish(metadata={
                "tool": step.tool_name,
                "success": "Error" not in str(result)
            })

            if "FINISH" in step.thought.upper():
                break

        # 4. Long-term memory
        self.memory.add_memories(
            documents=[f"Request: {user_request}\nLog: {results}"],
            metadatas=[{"session_id": session_id}],
            ids=[str(uuid.uuid4())]
        )

        return json.dumps(results, indent=2)
