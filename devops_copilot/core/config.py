"""
config.py — Centralized threshold and tuning configuration.
All values can be overridden via environment variables or per-service overrides.
"""
import os
from typing import Dict, Optional


class ThresholdConfig:
    """
    Anomaly detection thresholds, loaded from environment with sensible defaults.

    Per-service overrides via env:
        THRESHOLD_<SERVICE_UPPER>_ERROR_RATE=0.25
        WINDOW_<SERVICE_UPPER>_SECONDS=120

    Example:
        THRESHOLD_PAYMENT_GATEWAY_ERROR_RATE=0.20
        WINDOW_PAYMENT_GATEWAY_SECONDS=120
    """

    # === Global defaults ======================================================
    # Error rate above which an anomaly is flagged (0.0 – 1.0)
    DEFAULT_ERROR_RATE_THRESHOLD: float = float(
        os.getenv("ANOMALY_ERROR_RATE_THRESHOLD", "0.10")
    )
    # Rolling window for error rate calculation (seconds)
    DEFAULT_WINDOW_SECONDS: int = int(
        os.getenv("ANOMALY_WINDOW_SECONDS", "300")
    )
    # Minimum total log volume before anomaly detection fires (avoids cold-start noise)
    MIN_LOG_VOLUME: int = int(
        os.getenv("ANOMALY_MIN_LOG_VOLUME", "5")
    )

    # === MTTD ================================================================
    # Maximum MTTD to record in Prometheus (seconds); spikes > this are clamped
    MTTD_CEILING_SECONDS: float = float(
        os.getenv("MTTD_CEILING_SECONDS", "3600")
    )

    # === Remediation =========================================================
    # Number of consecutive anomaly checks before auto-escalation is considered
    ESCALATION_THRESHOLD: int = int(
        os.getenv("ESCALATION_THRESHOLD_COUNT", "3")
    )

    @classmethod
    def error_rate_threshold(cls, service: str) -> float:
        """Return error rate threshold for a specific service, with env override."""
        key = f"THRESHOLD_{_env_key(service)}_ERROR_RATE"
        return float(os.getenv(key, str(cls.DEFAULT_ERROR_RATE_THRESHOLD)))

    @classmethod
    def window_seconds(cls, service: str) -> int:
        """Return the lookback window for a specific service."""
        key = f"WINDOW_{_env_key(service)}_SECONDS"
        return int(os.getenv(key, str(cls.DEFAULT_WINDOW_SECONDS)))

    @classmethod
    def summary(cls) -> Dict:
        """Return current effective config as a dict (for /health response)."""
        return {
            "default_error_rate_threshold": cls.DEFAULT_ERROR_RATE_THRESHOLD,
            "default_window_seconds": cls.DEFAULT_WINDOW_SECONDS,
            "min_log_volume": cls.MIN_LOG_VOLUME,
            "mttd_ceiling_seconds": cls.MTTD_CEILING_SECONDS,
            "escalation_threshold": cls.ESCALATION_THRESHOLD,
        }


def _env_key(service: str) -> str:
    """Convert 'payment-gateway' → 'PAYMENT_GATEWAY' for env lookups."""
    return service.upper().replace("-", "_").replace(".", "_")


# Singleton instance used by tools
thresholds = ThresholdConfig()
