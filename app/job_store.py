import json
import sqlite3
import uuid

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATABASE_PATH = DATA_DIR / "sentinel.db"


def _connect(db_path):
    """Open a SQLite connection and ensure its directory exists"""

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.row_factory = sqlite3.Row

    return connection


def _utc_now():
    """Return the current UTC time as an ISO-formatted string."""
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path=DATABASE_PATH):
    """Create the jobs table if it does not already exist."""
    with closing(_connect(db_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    dataset_name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN (
                            'QUEUED',
                            'RUNNING',
                            'COMPLETED',
                            'FAILED'
                        )
                    ),
                    input_path TEXT NOT NULL,
                    contract_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at
                ON jobs (status, created_at)
                """
            )


def _decode_job(row):
    """Convert a SQLite row into a Python dictionary."""
    if row is None:
        return None

    job = dict(row)

    job["contract"] = json.loads(job.pop("contract_json"))

    result_json = job.pop("result_json")
    job["result"] = (
        json.loads(result_json)
        if result_json is not None
        else None
    )

    return job


def create_job(dataset_name, input_path, contract, db_path=DATABASE_PATH):
    """Persist a new job in the QUEUED state."""
    init_db(db_path)

    job_id = str(uuid.uuid4())
    created_at = _utc_now()

    with closing(_connect(db_path)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id,
                    dataset_name,
                    status,
                    input_path,
                    contract_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    dataset_name,
                    "QUEUED",
                    str(input_path),
                    json.dumps(contract),
                    created_at,
                ),
            )

    return get_job(job_id, db_path)


def get_job(job_id, db_path=DATABASE_PATH):
    """Retrieve a job by its ID, or return None if it does not exist."""
    init_db(db_path)

    with closing(_connect(db_path)) as connection:
        row = connection.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

    return _decode_job(row)


def claim_next_job(db_path=DATABASE_PATH):
    """Atomically claim the oldest queued job for processing."""
    init_db(db_path)

    with closing(_connect(db_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")

        try:
            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'QUEUED'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                connection.commit()
                return None

            connection.execute(
                """
                UPDATE jobs
                SET status = 'RUNNING',
                    started_at = ?
                WHERE id = ? AND status = 'QUEUED'
                """,
                (_utc_now(), row["id"]),
            )

            claimed_row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (row["id"],),
            ).fetchone()

            connection.commit()

            return _decode_job(claimed_row)

        except Exception:
            connection.rollback()
            raise


def complete_job(job_id, result, db_path=DATABASE_PATH):
    """Save the validation result and mark a running job as completed."""
    init_db(db_path)

    with closing(_connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = 'COMPLETED',
                    result_json = ?,
                    error = NULL,
                    finished_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (
                    json.dumps(result),
                    _utc_now(),
                    job_id,
                ),
            )

    return cursor.rowcount == 1


def fail_job(job_id, error, db_path=DATABASE_PATH):
    """Record a processing error and mark a running job as failed."""
    init_db(db_path)

    with closing(_connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = 'FAILED',
                    error = ?,
                    finished_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (
                    error,
                    _utc_now(),
                    job_id,
                ),
            )

    return cursor.rowcount == 1