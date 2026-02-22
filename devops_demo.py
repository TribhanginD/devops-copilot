import asyncio
import json
import time
from devops_copilot.core.engine import WorkflowEngine
from devops_copilot.tools.devops_tools import log_store # Import shared instance
from devops_copilot.utils.logger import logger

async def simulate_outage():
    service = "payment-gateway"
    logger.info(f"Simulating traffic for {service}...")
    
    # Ingest healthy logs
    for _ in range(10):
        log_store.ingest_log(service, "INFO", "Handling request successfully")
        
    # Ingest error spike
    logger.error("!!! TRAPPING ERROR SPIKE !!!")
    for _ in range(15):
        log_store.ingest_log(service, "ERROR", "java.lang.OutOfMemoryError: Java heap space")

async def main():
    logger.info("Initializing AI DevOps Copilot Demo...")
    engine = WorkflowEngine(db_path="devops_state.db", run_metrics=True)
    
    # 1. Simulate Outage
    await simulate_outage()
    
    session_id = "devops-incident-001"
    request = "Monitor the payment-gateway service, check for anomalies, and fix any issues found."
    
    # 2. Detection & Diagnosis
    logger.info("--- Phase 1: Detection & Diagnosis ---")
    result_turn1 = await engine.run(request, session_id=session_id)
    print(f"\nDetection Results:\n{result_turn1}\n")
    
    # 3. Approval Simulation
    # Assume the user reviews the proposal and grants approval in the state
    logger.info("--- USER APPROVAL GRANTED ---")
    state_dict = engine.persistence.load_session(session_id)
    state_dict["metadata"]["human_approved"] = True
    engine.persistence.save_session(session_id, state_dict)
    
    # 4. Remediation
    logger.info("--- Phase 2: Remediation ---")
    result_turn2 = await engine.run(request, session_id=session_id)
    print(f"\nRemediation Results:\n{result_turn2}\n")

if __name__ == "__main__":
    asyncio.run(main())
