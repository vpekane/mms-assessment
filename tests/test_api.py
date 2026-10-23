from io import BytesIO
import yaml
from types import SimpleNamespace
import pytest
from pathlib import Path

from app import create_app

from app.jobs.job_store import get_job, create_job
from app.workers.worker import process_next_job


@pytest.fixture(autouse=True)
def mock_clerk_authentication(monkeypatch):
    """Simulate a successfully authenticated Clerk user in API tests."""

    def fake_authenticate_request(request, options):
        return SimpleNamespace(
            is_signed_in=True,
            reason=None,
            payload={"sub": "test-user-123"},
        )

    # Avoid requiring real Clerk credentials in automated tests.
    monkeypatch.setattr(
        "app.auth.AuthenticateRequestOptions",
        lambda **kwargs: None,
    )

    # Simulate the SDK accepting the user's session.
    monkeypatch.setattr(
        "app.auth.authenticate_request",
        fake_authenticate_request,
    )


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

    contract_directory = directory / "weighbridge"
    contract_directory.mkdir(parents=True, exist_ok=True)

    contract_path = contract_directory / "weighbridge_1.0.yaml"
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
            "contract_version": '1.0',
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
            "contract_version": "1.0",
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
            "contract_name": "weighbridge",
            "contract_version": '1.0',
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

    assert report["contract_name"] == "weighbridge"

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
        "The 'contract_name' field is required"
    )


def test_detect_drift_returns_404_for_missing_contract(client):
    response = client.post(
        "/detect-drift",
        data={
            "contract_name": "unknown_dataset",
            "contract_version": "1.0",
            "file": (
                BytesIO(b"ticket_id\nT-001\n"),
                "incoming.csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 404

    assert response.get_json()["error"] == (
        "Contract 'unknown_dataset' version 'unknown_dataset_1.0' was not found"
    )


def test_detect_drift_reports_contract_schema_mismatches(client):
    response = client.post(
        "/detect-drift",
        data={
            "contract_name": "weighbridge",
            "contract_version": '1.0',
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
            "contract_name": "weighbridge",
            "contract_version": "1.0",
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

    assert body["contract_name"] == "weighbridge"
    assert body["status"] == "QUEUED"
    assert body["job_id"]
    assert body["status_url"] == f"/jobs/{body['job_id']}"

    job = get_job(body["job_id"], db_path=database_path)

    assert job is not None
    assert job["status"] == "QUEUED"
    assert job["contract"]["version"] == "1.0"
    assert job["result"] is None
    assert job["owner_id"] == "test-user-123"

    # The worker will need this file after the request finishes.
    assert Path(job["input_path"]).is_file()


def test_get_job_returns_404_for_unknown_id(tmp_path, monkeypatch):
    database_path = tmp_path / "sentinel.db"

    monkeypatch.setattr(
        "app.api.DATABASE_PATH",
        database_path,
    )

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/jobs/unknown-job-id")

    assert response.status_code == 404
    assert response.get_json()["error"] == (
        "Job 'unknown-job-id' was not found"
    )


def test_get_job_tracks_job_through_completion(tmp_path, monkeypatch):
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

    submission = client.post(
        "/jobs",
        data={
            "contract_name": "weighbridge",
            "contract_version": "1.0",
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

    assert submission.status_code == 202

    job_id = submission.get_json()["job_id"]

    # Before the worker processes the job, its status is QUEUED.
    queued_response = client.get(f"/jobs/{job_id}")

    assert queued_response.status_code == 200

    queued_job = queued_response.get_json()

    assert queued_job["job_id"] == job_id
    assert queued_job["contract_name"] == "weighbridge"
    assert queued_job["status"] == "QUEUED"
    assert queued_job["result"] is None
    assert queued_job["error"] is None

    # The worker processes the queued job.
    assert process_next_job(db_path=database_path) is True

    # The same endpoint now exposes the completed result.
    completed_response = client.get(f"/jobs/{job_id}")

    assert completed_response.status_code == 200

    completed_job = completed_response.get_json()

    assert completed_job["job_id"] == job_id
    assert completed_job["status"] == "COMPLETED"
    assert completed_job["result"]["status"] == "READY"
    assert completed_job["result"]["total_records"] == 1
    assert completed_job["result"]["issues"] == []
    assert completed_job["finished_at"] is not None

    # Internal implementation details aren't exposed to API clients.
    assert "input_path" not in completed_job
    assert "contract" not in completed_job

def test_get_contracts_returns_available_versions(
    tmp_path,
    monkeypatch,
):
    write_test_contract(tmp_path)

    monkeypatch.setattr(
        "app.contracts.CONTRACTS_DIR",
        tmp_path,
    )

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/contracts")

    assert response.status_code == 200

    body = response.get_json()

    assert body["contracts"] == [
        {
            "contract_name": "weighbridge",
            "display_name": "weighbridge_tickets",
            "version": "1.0",
        }
    ]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/me"),
        ("GET", "/contracts"),
        ("POST", "/validate"),
        ("POST", "/detect-drift"),
        ("POST", "/jobs"),
        ("GET", "/jobs/unknown-job-id"),
    ],
)
def test_protected_endpoints_reject_unauthenticated_requests(
    method,
    path,
    monkeypatch,
):
    def fake_unauthenticated_request(request, options):
        return SimpleNamespace(
            is_signed_in=False,
            reason=SimpleNamespace(
                name="SESSION_TOKEN_MISSING"
            ),
            payload={},
        )

    monkeypatch.setattr(
        "app.auth.authenticate_request",
        fake_unauthenticated_request,
    )

    app = create_app()
    app.config["TESTING"] = True

    response = app.test_client().open(
        path,
        method=method,
    )

    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized"


def test_user_cannot_access_another_users_job(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "sentinel.db"

    monkeypatch.setattr(
        "app.api.DATABASE_PATH",
        database_path,
    )

    # Create a job belonging to the original user.
    job = create_job(
        dataset_name="weighbridge",
        input_path=tmp_path / "unused.csv",
        contract={"version": "1.0"},
        db_path=database_path,
        owner_id="original-user",
    )

    # Simulate a different, successfully authenticated user.
    def authenticate_as_another_user(request, options):
        return SimpleNamespace(
            is_signed_in=True,
            reason=None,
            payload={"sub": "different-user"},
        )

    monkeypatch.setattr(
        "app.auth.authenticate_request",
        authenticate_as_another_user,
    )

    app = create_app()
    app.config["TESTING"] = True

    response = app.test_client().get(
        f"/jobs/{job['id']}"
    )

    assert response.status_code == 404