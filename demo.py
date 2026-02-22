import asyncio
from devops_copilot.core.engine import WorkflowEngine
from devops_copilot.tools.standard_tools import web_search, calculator, idempotent_write
from devops_copilot.utils.logger import logger

async def main():
    logger.info("Initializing Enhanced AgentNexus Demo...")
    engine = WorkflowEngine(db_path="demo_state.db", run_metrics=True)
    
    session_id = "test-session-123"
    request = "Find information about multi-agent systems and calculate 10 * 5"
    logger.info(f"User Request: {request} (Session: {session_id})")
    
    # 1. Run First Part
    logger.info("--- Phase 1: Initial Run ---")
    result = await engine.run(request, session_id=session_id, max_steps=1)
    print(f"\nPhase 1 Results (1 step):\n{result}\n")
    
    # 2. Resume session
    logger.info("--- Phase 2: Resuming Session ---")
    resume_result = await engine.run(request, session_id=session_id, max_steps=2)
    print(f"\nPhase 2 Results (Resumed):\n{resume_result}\n")
    
    # 3. Test Security (simpleeval)
    logger.info("Testing security (simpleeval)...")
    calc_result = await engine.run("Calculate (10 + 5) * 2", session_id="sec-test")
    print(f"Calculation Result: {calc_result}")

if __name__ == "__main__":
    asyncio.run(main())
