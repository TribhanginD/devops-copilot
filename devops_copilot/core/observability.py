from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
from functools import wraps
from typing import Callable, Any
from devops_copilot.utils.logger import logger
import os

# === General Agent Metrics ===
TOOL_CALL_SUCCESS = Counter("tool_call_success_total", "Total successful tool calls", ["tool_name"])
TOOL_CALL_FAILURE = Counter("tool_call_failure_total", "Total failed tool calls", ["tool_name"])
TOOL_CALL_LATENCY = Histogram("tool_call_latency_seconds", "Latency of tool calls in seconds", ["tool_name"])
AGENT_FAILURE = Counter("agent_failure_total", "Total agent failures", ["agent_name"])

# === DevOps Copilot Metrics ===
ANOMALY_DETECTION_TIME = Histogram(
    "devops_mttd_seconds",
    "Mean time to detection - time from anomaly start to agent detection",
    buckets=[1, 5, 10, 30, 60, 120, 300]
)
FALSE_POSITIVE_TOTAL = Counter("devops_false_positive_total", "Total false positive anomaly alerts")
ACTIVE_INCIDENTS = Gauge("devops_active_incidents", "Number of currently open incidents")
REMEDIATION_SUCCESS = Counter("devops_remediation_success_total", "Successful auto-remediations", ["service"])
REMEDIATION_FAILURE = Counter("devops_remediation_failure_total", "Failed auto-remediations", ["service"])

def start_metrics_server():
    port = int(os.getenv("PROMETHEUS_PORT", 8000))
    start_http_server(port)
    logger.info(f"Prometheus metrics server started on port {port}")

def track_tool_metrics(tool_name: str):
    """Decorator to track tool execution metrics."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                TOOL_CALL_SUCCESS.labels(tool_name=tool_name).inc()
                return result
            except Exception as e:
                TOOL_CALL_FAILURE.labels(tool_name=tool_name).inc()
                raise e
            finally:
                latency = time.time() - start_time
                TOOL_CALL_LATENCY.labels(tool_name=tool_name).observe(latency)
        return wrapper
    return decorator

class RateLimiter:
    """Sliding window rate limiter for precision."""
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests = []

    def acquire(self):
        now = time.time()
        # Remove requests older than 60s
        self.requests = [r for r in self.requests if r > now - 60]
        
        if len(self.requests) >= self.rpm:
            wait_time = 60 - (now - self.requests[0])
            logger.warning(f"Sliding window full. Waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            now = time.time() # Update now after sleep
            self.requests = [r for r in self.requests if r > now - 60]
        
        self.requests.append(now)
