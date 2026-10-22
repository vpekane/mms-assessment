from app.job_store import create_job, get_job
from app.worker import process_next_job


def test_worker_processes_queued_job(tmp_path):
    db_path = tmp_path / "sentinel.db"

    csv_path = tmp_path / "incoming.csv"
    csv_path.write_text(
        "ticket_id\n"
        "WB001\n",
        encoding="utf-8",
    )

    contract = {
        "name": "test_tickets",
        "version": "1.0",
        "fields": {
            "ticket_id": {
                "type": "string",
                "required": True,
            },
        },
    }

    job = create_job(
        dataset_name="test_tickets",
        input_path=csv_path,
        contract=contract,
        db_path=db_path,
    )

    processed = process_next_job(db_path=db_path)

    assert processed is True

    saved_job = get_job(job["id"], db_path=db_path)

    assert saved_job["status"] == "COMPLETED"
    assert saved_job["result"] is not None
    assert saved_job["result"]["status"] == "READY"
    assert saved_job["result"]["total_records"] == 1
    assert saved_job["finished_at"] is not None


def test_worker_marks_job_failed_when_input_is_missing(tmp_path):
    db_path = tmp_path / "sentinel.db"

    missing_csv_path = tmp_path / "missing.csv"

    job = create_job(
        dataset_name="test_tickets",
        input_path=missing_csv_path,
        contract={
            "name": "test_tickets",
            "version": "1.0",
            "fields": {
                "ticket_id": {
                    "type": "string",
                    "required": True,
                },
            },
        },
        db_path=db_path,
    )

    processed = process_next_job(db_path=db_path)

    assert processed is True

    saved_job = get_job(job["id"], db_path=db_path)

    assert saved_job["status"] == "FAILED"
    assert saved_job["error"] is not None
    assert saved_job["finished_at"] is not None


def test_worker_returns_false_when_queue_is_empty(tmp_path):
    db_path = tmp_path / "sentinel.db"

    processed = process_next_job(db_path=db_path)

    assert processed is False