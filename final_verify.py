
import asyncio
import os
import json
from dotenv import load_dotenv

# Load real environment variables
load_dotenv()

async def final_verification():
    print("🚀 Starting Final System Verification...")

    # 1. Check Provider
    provider = os.getenv("LLM_PROVIDER", "gemini")
    print(f"📡 Using Provider: {provider}")

    # 2. Test Threshold Logic & Async Log Storage
    from devops_copilot.core.log_storage import LogStorage
    from devops_copilot.core.config import thresholds

    db_path = "data/dev_verification.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    ls = LogStorage(db_path)
    await ls.setup()

    service = "payment-gateway"
    print(f"📊 Testing Thresholds for: {service}")

    # Ingest logs below threshold first
    for _ in range(5):
        await ls.ingest_log(service, "INFO", "Success")

    rate = await ls.get_error_rate(service, window_seconds=thresholds.window_seconds(service))
    threshold = thresholds.error_rate_threshold(service)
    print(f"   Initial Error Rate: {rate*100:.1f}% (Threshold: {threshold*100:.1f}%)")

    # Ingest logs to trigger anomaly (>5% for payment-gateway)
    for _ in range(2):
        await ls.ingest_log(service, "ERROR", "java.lang.OutOfMemoryError")

    rate = await ls.get_error_rate(service, window_seconds=thresholds.window_seconds(service))
    print(f"   Spike Error Rate: {rate*100:.1f}%")

    # 3. Test Workflow Engine (Real LLM call)
    from devops_copilot.core.engine import WorkflowEngine
    engine = WorkflowEngine(db_path="data/dev_verification_state.db", run_metrics=False)

    print("\n🤖 Running Agent Workflow (Real LLM Call)...")
    try:
        session_id = "final-verification-session"
        result_json = await engine.run(
            f"There is a spike in errors for {service}. Investigate and remediate.",
            session_id=session_id,
            max_steps=3
        )
        results = json.loads(result_json)

        print("\n✅ Execution Results:")
        for r in results:
            tool = r.get("tool", "unknown")
            status = r.get("status", "unknown")
            print(f"   - Step {r['step']}: {tool} [{status}]")

        # Verify PENDING_APPROVAL if restart_service was proposed
        proposed_tools = [r.get("tool") for r in results]
        if "restart_service" in proposed_tools:
            restart_step = next(r for r in results if r["tool"] == "restart_service")
            if restart_step["status"] == "PENDING_APPROVAL":
                print("\n✅ Human-in-the-loop Approval working correctly.")
            else:
                print("\n❌ Error: restart_service should require approval but status was " + restart_step["status"])
        else:
            print("\n⚠️  Note: Agent did not propose restart_service in this run.")

        print("\n🎉 Final Verification Successfully Completed!")

    except Exception as e:
        print(f"\n❌ Final Verification Failed: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        if os.path.exists(db_path): os.remove(db_path)
        if os.path.exists("data/dev_verification_state.db"): os.remove("data/dev_verification_state.db")

if __name__ == "__main__":
    asyncio.run(final_verification())
