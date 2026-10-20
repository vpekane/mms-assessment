from io import BytesIO
import yaml

from app import create_app
from app.contracts import CONTRACTS_DIR


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
