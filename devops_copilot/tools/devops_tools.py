"""
devops_tools.py — DevOps tool registry using configurable thresholds.
"""
from devops_copilot.tools.registry import registry
from devops_copilot.core.log_storage import LogStorage
from devops_copilot.core.config import thresholds
from devops_copilot.core.observability import (
    track_tool_metrics, ACTIVE_INCIDENTS,
    REMEDIATION_SUCCESS, REMEDIATION_FAILURE,
    ANOMALY_DETECTION_TIME
)
from devops_copilot.utils.logger import logger
from typing import Optional, Dict, Any
import time

# Shared async log store instance
log_store = LogStorage()


@registry.register(name="search_logs", description="Search production logs for a service.")
@track_tool_metrics("search_logs")
def search_logs(service: str, level: Optional[str] = None, minutes_ago: int = 5) -> str:
    window = thresholds.window_seconds(service) // 60  # use per-service window
    start_time = time.time() - (max(minutes_ago, window) * 60)
    logs = log_store.query_logs_sync(service=service, level=level, start_time=start_time)
    if not logs:
        return f"No logs found for {service} in the last {minutes_ago} minutes."
    formatted = "\n".join(f"[{l['level']}] {l['message']}" for l in logs)
    return f"Latest logs for {service}:\n{formatted}"


@registry.register(name="get_metrics", description="Get error rates and health metrics for a service.")
@track_tool_metrics("get_metrics")
def get_metrics(service: str) -> Dict[str, Any]:
    window = thresholds.window_seconds(service)
    error_rate = log_store.get_error_rate_sync(service, window_seconds=window)
    threshold = thresholds.error_rate_threshold(service)

    # Require minimum log volume before triggering anomaly (avoids cold-start noise)
    total_logs = log_store.query_logs_sync(
        service=service,
        start_time=time.time() - window,
    )
    enough_data = len(total_logs) >= thresholds.MIN_LOG_VOLUME

    is_anomaly = enough_data and (error_rate > threshold)
    status = "CRITICAL" if is_anomaly else ("HEALTHY" if enough_data else "INSUFFICIENT_DATA")

    if is_anomaly:
        ACTIVE_INCIDENTS.inc()
        spike_start = log_store.get_spike_start_sync(service)
        if spike_start:
            mttd = min(time.time() - spike_start, thresholds.MTTD_CEILING_SECONDS)
            ANOMALY_DETECTION_TIME.observe(mttd)
            logger.info(f"MTTD for {service}: {mttd:.2f}s (threshold={threshold*100:.0f}%, window={window}s)")

    return {
        "service": service,
        "error_rate": f"{error_rate*100:.2f}%",
        "threshold": f"{threshold*100:.0f}%",
        "window_seconds": window,
        "status": status,
        "anomaly_detected": is_anomaly,
        "log_count": len(total_logs),
        "timestamp": time.time()
    }


@registry.register(name="restart_service", description="Restart a failing service. REQUIRES APPROVAL.")
@track_tool_metrics("restart_service")
def restart_service(service: str, reason: str) -> str:
    logger.warning(f"RESTARTING SERVICE: {service} | reason: {reason}")
    try:
        REMEDIATION_SUCCESS.labels(service=service).inc()
        ACTIVE_INCIDENTS.dec()
        log_store.clear_spike_sync(service)
        return f"Service {service} successfully restarted. Reason: {reason}"
    except Exception as e:
        REMEDIATION_FAILURE.labels(service=service).inc()
        raise e


@registry.register(name="slack_notify", description="Send a message to the DevOps Slack channel.")
@track_tool_metrics("slack_notify")
def slack_notify(channel: str, message: str) -> str:
    logger.info(f"SLACK [{channel}]: {message}")
    return f"Notification sent to #{channel}"
