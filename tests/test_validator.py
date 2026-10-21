import csv
import pytest

from app.validator import validate_csv
from app.contracts import load_contract


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


def make_contract():
    return {
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


def test_valid_csv_has_no_issues(tmp_path):
    csv_path = tmp_path / "valid.csv"

    write_csv(
        csv_path,
        [
            "ticket_id",
            "gross_weight",
            "tare_weight",
            "net_weight",
            "timestamp",
        ],
        [
            ["WB001", "15000", "5000", "10000", "2026-10-20T08:30:00"],
            ["WB002", "12000", "4000", "8000", "2026-10-20T09:00:00"],
        ],
    )

    report = validate_csv(csv_path, make_contract())

    assert report["status"] == "READY"
    assert report["total_records"] == 2
    assert report["valid_records"] == 2
    assert report["invalid_records"] == 0
    assert report["issues"] == []


def test_duplicate_ticket_id_is_reported(tmp_path):
    csv_path = tmp_path / "duplicates.csv"

    write_csv(
        csv_path,
        ["ticket_id", "gross_weight", "tare_weight", "net_weight", "timestamp"],
        [
            ["WB001", "10000", "3000", "7000", "2026-10-20T08:30:00"],
            ["WB001", "12000", "4000", "8000", "2026-10-20T09:00:00"],
        ],
    )

    report = validate_csv(csv_path, make_contract())

    assert report["status"] == "NOT_READY"
    assert any(
        issue["code"] == "DUPLICATE_VALUE"
        for issue in report["issues"]
    )


def test_invalid_number_and_weight_mismatch_are_reported(tmp_path):
    csv_path = tmp_path / "invalid.csv"

    write_csv(
        csv_path,
        ["ticket_id", "gross_weight", "tare_weight", "net_weight", "timestamp"],
        [
            ["WB001", "-500", "200", "100", "invalid-date"],
        ],
    )

    report = validate_csv(csv_path, make_contract())

    issue_codes = {issue["code"] for issue in report["issues"]}

    assert report["status"] == "NOT_READY"
    assert "BELOW_MINIMUM" in issue_codes
    assert "INVALID_DATETIME" in issue_codes
    assert "WEIGHT_MISMATCH" in issue_codes


def test_missing_column_is_reported(tmp_path):
    csv_path = tmp_path / "missing_column.csv"

    write_csv(
        csv_path,
        ["ticket_id", "gross_weight", "tare_weight", "timestamp"],
        [
            ["WB001", "10000", "3000", "2026-10-20T08:30:00"],
        ],
    )

    report = validate_csv(csv_path, make_contract())

    assert any(
        issue["code"] == "MISSING_COLUMN"
        and issue["field"] == "net_weight"
        for issue in report["issues"]
    )


def test_validate_csv_rejects_duplicate_headers(tmp_path):
    csv_path = tmp_path / "duplicate_headers.csv"

    csv_path.write_text(
        "ticket_id,ticket_id,gross_weight\n"
        "WB001,WB999,15000\n",
        encoding="utf-8",
    )

    contract = {
        "fields": {
            "ticket_id": {"type": "string"},
            "gross_weight": {"type": "number"},
        }
    }

    with pytest.raises(ValueError, match="duplicate column names"):
        validate_csv(csv_path, contract)


def test_missing_csv_raises_error(tmp_path):
    csv_path = tmp_path / "does_not_exist.csv"

    try:
        validate_csv(csv_path, make_contract())
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected FileNotFoundError")


@pytest.mark.parametrize(
    "gross_weight",
    [
        "NaN",
        "nan",
        "Infinity",
        "-Infinity",
        "1e309",
    ],
)
def test_validate_csv_rejects_non_finite_numbers(
    tmp_path,
    gross_weight,
):
    csv_path = tmp_path / "non_finite_weight.csv"

    csv_path.write_text(
        "ticket_id,gross_weight,tare_weight,net_weight,timestamp\n"
        f"T-001,{gross_weight},5000,10000,2026-10-20T08:30:00\n",
        encoding="utf-8",
    )

    contract = load_contract("weighbridge")
    report = validate_csv(csv_path, contract)

    issue_codes = {
        issue["code"]
        for issue in report["issues"]
    }

    assert report["status"] == "NOT_READY"
    assert report["invalid_records"] == 1
    assert "INVALID_NUMBER" in issue_codes
    assert "WEIGHT_MISMATCH" not in issue_codes