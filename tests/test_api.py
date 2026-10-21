from io import BytesIO
import yaml
import pytest
from pathlib import Path

from app import create_app

from app.job_store import get_job


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


def write_test_contract(directory):
    contract = {
        "name": "weighbridge_tickets",
        "version": "1.0",
        "fields": {
            "ticket_id": {
                "type": "string",
                "required": True,
                "unique": True,
            },
            "gross_weight": {
                "type": "number",
                "required": True,
                "minimum": 0,
            },
            "tare_weight": {
                "type": "number",
                "required": True,
                "minimum": 0,
            },
            "net_weight": {
                "type": "number",
                "required": True,
                "minimum": 0,
            },
            "timestamp": {
                "type": "datetime",
                "required": True,
            },
        },
        "rules": [
            {
                "name": "net_weight_consistency",
                "type": "difference_equals",
                "left": "gross_weight",
                "subtract": "tare_weight",
                "result": "net_weight",
                "tolerance": 0,
            }
        ],
    }

    contract_path = directory / "weighbridge.yaml"
    contract_path.write_text(
        yaml.safe_dump(contract),
        encoding="utf-8",
    )


def test_validate_endpoint_returns_report(tmp_path, monkeypatch):
    write_test_contract(tmp_path)

    monkeypatch.setattr(
        "app.contracts.CONTRACTS_DIR",
        tmp_path,
    )

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.post(
        "/validate",
        data={
            "contract_name": "weighbridge",
            "file": (
                BytesIO(
                    b"ticket_id,gross_weight,tare_weight,net_weight,timestamp\n"
                    b"WB001,15000,5000,10000,2026-10-20T08:30:00\n"
                ),
                "weighbridge.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    report = response.get_json()

    assert report["status"] == "READY"
    assert report["total_records"] == 1
    assert report["issues"] == []


def test_validate_endpoint_rejects_missing_file():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.post(
        "/validate",
        data={"contract_name": "weighbridge"},
    )

    assert response.status_code == 400
    assert "CSV file is required" in response.get_json()["error"]


def test_validate_endpoint_rejects_missing_contract():
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.post(
        "/validate",
        data={
            "contract_name": "does_not_exist",
            "file": (
                BytesIO(b"ticket_id\nWB001\n"),
                "weighbridge.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 404


def test_detect_drift_returns_report(client):
    response = client.post(
        "/detect-drift",
        data={
            "dataset_name": "weighbridge",
            "file": (
                BytesIO(
                    b"ticket_id,gross_weight,tare_weight,net_weight,timestamp\n"
                    b"T-001,not-a-number,5000,10000,2026-10-20T08:30:00\n"
                ),
                "incoming.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    report = response.get_json()

    assert report["dataset_name"] == "weighbridge"

    # The CSV headers match the contract.
    assert report["has_drift"] is False
    assert report["findings"] == []

    # The invalid numeric value is still reported.
    assert report["data_quality"]["status"] == "NOT_READY"

    issue_codes = {
        issue["code"]
        for issue in report["data_quality"]["issues"]
    }

    assert "INVALID_NUMBER" in issue_codes


def test_detect_drift_requires_dataset_name(client):
    response = client.post(
        "/detect-drift",
        data={
            "file": (
                BytesIO(b"ticket_id\nT-001\n"),
                "incoming.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "The 'dataset_name' field is required"
    )


def test_detect_drift_returns_404_for_missing_contract(client):
    response = client.post(
        "/detect-drift",
        data={
            "dataset_name": "unknown_dataset",
            "file": (
                BytesIO(b"ticket_id\nT-001\n"),
                "incoming.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 404

    assert response.get_json()["error"] == (
        "Contract file: 'unknown_dataset.yaml' was not found"
    )


def test_detect_drift_reports_contract_schema_mismatches(client):
    response = client.post(
        "/detect-drift",
        data={
            "dataset_name": "weighbridge",
            "file": (
                BytesIO(
                    b"ticket_id,gross_weight,tare_weight,unexpected_field\n"
                    b"T-001,15000,5000,example\n"
                ),
                "incoming.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    report = response.get_json()

    assert report["has_drift"] is True

    finding_codes = {
        finding["code"]
        for finding in report["findings"]
    }

    assert "MISSING_COLUMN" in finding_codes
    assert "UNEXPECTED_COLUMN" in finding_codes


def test_submit_job_creates_queued_job(tmp_path, monkeypatch):
    write_test_contract(tmp_path)

    database_path = tmp_path / "sentinel.db"
    upload_directory = tmp_path / "uploads"

    monkeypatch.setattr(
        "app.contracts.CONTRACTS_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        "app.api.DATABASE_PATH",
        database_path,
    )
    monkeypatch.setattr(
        "app.api.JOB_UPLOAD_DIR",
        upload_directory,
    )

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.post(
        "/jobs",
        data={
            "dataset_name": "weighbridge",
            "file": (
                BytesIO(
                    b"ticket_id,gross_weight,tare_weight,net_weight,timestamp\n"
                    b"WB001,15000,5000,10000,2026-10-20T08:30:00\n"
                ),
                "weighbridge.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 202

    body = response.get_json()

    assert body["dataset_name"] == "weighbridge"
    assert body["status"] == "QUEUED"
    assert body["job_id"]
    assert body["status_url"] == f"/jobs/{body['job_id']}"

    job = get_job(body["job_id"], db_path=database_path)

    assert job is not None
    assert job["status"] == "QUEUED"
    assert job["contract"]["version"] == "1.0"
    assert job["result"] is None

    # The worker will need this file after the request finishes.
    assert Path(job["input_path"]).is_file()