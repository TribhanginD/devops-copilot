# DevOps Copilot

AI-powered incident detection, diagnosis, and remediation using Multi-Agent LLMs.

## 🚀 Features
- **Multi-Provider LLM**: Support for Google Gemini and Groq (Llama-3.3-70B).
- **Async Engine**: High-performance non-blocking SQLite storage via `aiosqlite`.
- **Human-in-the-Loop**: FastAPI-based approval gateway for critical actions.
- **Configurable Thresholds**: Per-service anomaly detection tuning with cold-start protection.
- **Observability**: Prometheus metrics and provisioned Grafana dashboards.

## 📦 Setup

1. **Environment**:
   ```bash
   cp .env.example .env
   # Add your GOOGLE_API_KEY or GROQ_API_KEY
   ```

2. **Run Locally**:
   ```bash
   pip install poetry
   poetry install
   poetry run python devops_demo.py
   ```

3. **Docker Stack (API + Prometheus + Grafana)**:
   ```bash
   docker compose up -d
   ```

## 🛠️ Control Plane API
- `POST /sessions/{id}/approve`: Unblock a pending agent action.
- `POST /sessions/{id}/reject`: Flag a false positive.
- `GET  /sessions/{id}`: Inspect agent state.

## 📊 Monitoring
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000` (admin/devops123)
