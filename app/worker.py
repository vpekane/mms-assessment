import time
from pathlib import Path

from app.job_store import (
    DATABASE_PATH,
    claim_next_job,
    complete_job,
    fail_job,
)
from app.validator import validate_csv


def process_next_job(db_path=DATABASE_PATH):
    """Claim and process one queued job.

    Returns True if a job was processed, or False if the queue was empty.
    """
    job = claim_next_job(db_path=db_path)

    if job is None:
        return False

    job_id = job["id"]

    try:
        report = validate_csv(
            Path(job["input_path"]),
            job["contract"],
        )

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

        fail_job(
            job_id=job_id,
            error=error,
            db_path=db_path,
        )

        print(f"Job {job_id} failed: {error}")

        return True

    completed = complete_job(
        job_id=job_id,
        result=report,
        db_path=db_path,
    )

    if not completed:
        raise RuntimeError(
            f"Could not mark job '{job_id}' as completed"
        )

    print(f"Job {job_id} completed")

    return True


def run_worker(poll_interval=2, db_path=DATABASE_PATH):
    """Continuously process queued jobs."""
    print("Sentinel worker started")

    while True:
        job_processed = process_next_job(db_path=db_path)

        if not job_processed:
            time.sleep(poll_interval)


if __name__ == "__main__":
    run_worker()