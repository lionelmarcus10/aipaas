"""Database connection helper for the Insurance Claims Triage Agent.

All tools use this to get a read-only DuckDB connection.

Three modes (same pattern as financial-dispute-agent):
  1. NFS (k3d / EKS): DB_LOCAL_PATH env var points to the NFS-mounted file.
  2. AWS Lambda: DB is downloaded from S3 to /tmp at cold start.
  3. Local dev: DB is at data/insurance_claims.duckdb relative to the repo.
"""

import os
from pathlib import Path

import duckdb

# Local dev path (relative to the repo, not the image)
LOCAL_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "insurance_claims.duckdb"

# Lambda /tmp path (downloaded from S3 at cold start)
LAMBDA_DB_PATH = Path("/tmp/insurance_claims.duckdb")

# Cache: only download once per Lambda execution context
_downloaded = False


def _download_from_s3() -> Path:
    """Download the DuckDB from S3 to /tmp (Lambda cold start)."""
    global _downloaded
    if _downloaded and LAMBDA_DB_PATH.exists():
        return LAMBDA_DB_PATH

    bucket = os.environ.get("DB_S3_BUCKET")
    key = os.environ.get("DB_S3_KEY", "insurance_claims.duckdb")

    if not bucket:
        raise ValueError("DB_S3_BUCKET env var required for S3 download")

    import boto3
    s3 = boto3.client("s3")
    print(f"[db] Downloading DuckDB from s3://{bucket}/{key} to {LAMBDA_DB_PATH}...")
    s3.download_file(bucket, key, str(LAMBDA_DB_PATH))
    print(f"[db] Downloaded {LAMBDA_DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    _downloaded = True
    return LAMBDA_DB_PATH


def get_db_path() -> Path:
    """Return the DB path, depending on the environment.

    Priority:
      1. DB_LOCAL_PATH env var (k3d/EKS NFS mount)
      2. DB_S3_BUCKET env var (Lambda) — download from S3 to /tmp
      3. LOCAL_DB_PATH (local dev) — relative to the repo
    """
    if os.environ.get("DB_LOCAL_PATH"):
        return Path(os.environ["DB_LOCAL_PATH"])

    if os.environ.get("DB_S3_BUCKET"):
        return _download_from_s3()

    return LOCAL_DB_PATH


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a read-only DuckDB connection to the insurance claims database."""
    db_path = get_db_path()
    return duckdb.connect(str(db_path), read_only=True)
