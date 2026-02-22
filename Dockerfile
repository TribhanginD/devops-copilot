# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry==2.1.1 && \
    poetry config virtualenvs.create false

# ── Dependency layer (cached unless pyproject.toml changes) ──────────────────
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-root --only main --no-interaction --no-ansi

# ── App layer ─────────────────────────────────────────────────────────────────
COPY devops_copilot/ ./devops_copilot/
COPY devops_demo.py demo.py ./

# Runtime env defaults (override in docker-compose or at runtime)
ENV PYTHONUNBUFFERED=1 \
    PROMETHEUS_PORT=8001 \
    DATABASE_URL=sqlite:///./data/devops_state.db \
    LLM_PROVIDER=groq \
    ANOMALY_ERROR_RATE_THRESHOLD=0.10 \
    ANOMALY_WINDOW_SECONDS=300 \
    ANOMALY_MIN_LOG_VOLUME=5

EXPOSE 8000 8001

# Default: run the FastAPI control plane
CMD ["uvicorn", "devops_copilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
