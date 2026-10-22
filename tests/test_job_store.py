from app.jobs.job_store import (
    claim_next_job,
    complete_job,
    create_job,
    get_job,
)


def test_create_job_persists_contract_snapshot(tmp_path):
    db_path = tmp_path / "sentinel.db"

    contract = {
        "name": "weighbridge_tickets",
        "version": "1.0",
        "fields": {
            "ticket_id": {
                "type": "string",
                "required": True,
            },
        },
    }

    job = create_job(
        dataset_name="weighbridge",
        input_path=tmp_path / "incoming.csv",
        contract=contract,
        db_path=db_path,
    )

    # Change our in-memory contract after creating the job.
    contract["version"] = "2.0"

    saved_job = get_job(job["id"], db_path)

    assert saved_job["id"] == job["id"]
    assert saved_job["status"] == "QUEUED"
    assert saved_job["dataset_name"] == "weighbridge"

    # The queued job retains the original contract version.
    assert saved_job["contract"]["version"] == "1.0"
    assert saved_job["result"] is None


def test_job_can_be_claimed_and_completed(tmp_path):
    db_path = tmp_path / "sentinel.db"

    job = create_job(
        dataset_name="weighbridge",
        input_path=tmp_path / "incoming.csv",
        contract={
            "name": "weighbridge_tickets",
            "version": "1.0",
            "fields": {},
        },
        db_path=db_path,
    )

    claimed_job = claim_next_job(db_path)

    assert claimed_job["id"] == job["id"]
    assert claimed_job["status"] == "RUNNING"
    assert claimed_job["started_at"] is not None

    # There should be no queued jobs left to claim.
    assert claim_next_job(db_path) is None

    report = {
        "status": "NOT_READY",
        "total_records": 1,
        "valid_records": 0,
        "invalid_records": 1,
        "issues": [
            {
                "row": 2,
                "field": "gross_weight",
                "code": "INVALID_NUMBER",
                "message": "Expected a valid number",
            }
        ],
    }

    assert complete_job(job["id"], report, db_path) is True

    saved_job = get_job(job["id"], db_path)

    # Processing completed, even though the report found invalid data.
    assert saved_job["status"] == "COMPLETED"
    assert saved_job["result"] == report
    assert saved_job["finished_at"] is not None