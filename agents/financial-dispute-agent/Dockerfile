# Dockerfile — Financial Dispute Resolution Agent (Service API)
#
# Builds a container image for the Kubernetes deployment on k3d.
# The pod runs under gVisor (runtimeClassName: gvisor) for syscall isolation.
#
# The image contains:
#   - The financial_dispute_agent package (orchestrator + tools + lambdas + prompts)
#   - The CAST library
#   - The setup_db.py script (run by the initContainer to build the DuckDB)
#   - uvicorn + FastAPI for the HTTP API
#
# The DuckDB database is NOT baked into the image. It is generated at runtime
# by the initContainer (setup_db.py) and stored on a shared NFS volume.
#
# Build (from the repo root — aipaas/):
#   docker build -t localhost:5001/financial-dispute-agent:latest \
#     -f agents/financial-dispute-agent/Dockerfile \
#     .
#
# Push to the k3d local registry:
#   docker push localhost:5001/financial-dispute-agent:latest

FROM python:3.13-slim

# --- Non-root user (security best practice) ---
RUN groupadd -r agent && useradd -r -g agent -u 10001 agent

WORKDIR /app

# --- Install system dependencies ---
# gcc: needed to build duckdb native extension
# libgomp1: needed by duckdb
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# --- Copy and install CAST library (from libs/) ---
COPY libs/custom-aws-strands-toolkit/pyproject.toml /tmp/cast-build/
COPY libs/custom-aws-strands-toolkit/src/ /tmp/cast-build/src/
RUN pip install --no-cache-dir /tmp/cast-build && rm -rf /tmp/cast-build

# --- Copy and install the agent package ---
COPY agents/financial-dispute-agent/src/ /app/src/
COPY agents/financial-dispute-agent/pyproject.toml /app/
RUN pip install --no-cache-dir -e /app

# --- Copy the setup_db.py script (run by the initContainer) ---
# The DB is NOT baked into the image. It is generated at runtime on a shared NFS volume.
COPY agents/financial-dispute-agent/data/setup_db.py /app/data/setup_db.py

# --- Install FastAPI + uvicorn ---
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# --- Install RAG dependencies ---
# sentence-transformers: embedding model (all-MiniLM-L6-v2, 88MB, 384 dims)
# faiss-cpu: vector similarity search (used by the FAISS RAG provider)
#
# PyTorch is installed CPU-only to avoid pulling ~2GB of CUDA libraries.
# sentence-transformers depends on torch, so we install the CPU wheel first
# from the PyTorch CPU index, then sentence-transformers reuses it.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir sentence-transformers faiss-cpu

# --- Ensure /app is owned by the non-root user (UID 10001) ---
# This allows the initContainer (which runs as UID 10001) to write
# intermediate files to /app/data/raw/ during setup_db.py execution.
RUN chown -R agent:agent /app

# --- Switch to non-root user ---
USER agent

# --- Expose the API port ---
EXPOSE 8000

# --- Health check ---
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# --- Run the API ---
CMD ["uvicorn", "financial_dispute_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
