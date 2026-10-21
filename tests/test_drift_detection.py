import pytest
from app.drift_detection import infer_type, inspect_csv_schema


def test_infer_type_is_correct_for_all_types():
    assert infer_type("WB001") == "string"
    assert infer_type("12000") == "number"
    assert infer_type("15.199") == "number"
    assert infer_type("true") == "boolean"
    assert infer_type("2026-10-20T08:30:00") == "datetime"
    assert infer_type("") == "unknown"


def test_inspect_csv_schema_is_valid(tmp_path):
    csv_path = tmp_path / "weighbridge.csv"

    csv_path.write_text(
        (
            "ticket_id,gross_weight,tare_weight,net_weight,timestamp\n"
            "WB001,15000,5000,10000,2026-10-20T08:30:00\n"
            "WB002,16000,5000,11000,2026-10-20T09:30:00\n"
        ),
        encoding="utf-8",
    )

    schema = inspect_csv_schema(csv_path)

    assert schema == {
        "ticket_id": "string",
        "gross_weight": "number",
        "tare_weight": "number",
        "net_weight": "number",
        "timestamp": "datetime",
    }


def test_inspect_csv_detects_mixed_types(tmp_path):
    csv_path = tmp_path / "mixed.csv"

    csv_path.write_text(
        "gross_weight\n15000\nunknown\n",
        encoding="utf-8",
    )

    schema = inspect_csv_schema(csv_path)

    assert schema["gross_weight"] == "mixed"


def test_inspect_csv_detects_empty_column(tmp_path):
    csv_path = tmp_path / "empty.csv"

    csv_path.write_text(
        "ticket_id,gross_weight\nWB001,\nWB002,\n",
        encoding="utf-8",
    )

    schema = inspect_csv_schema(csv_path)

    assert schema == {
        "ticket_id": "string",
        "gross_weight": "unknown",
    }


def test_csv_inspection_fails_because_file_not_found(tmp_path):
    csv_path = tmp_path / ""

    # schema = inspect_csv_schema(csv_path)

    # assert schema
    with pytest.raises(FileNotFoundError, match="CSV file not found"):
        inspect_csv_schema(csv_path)


def test_csv_inspection_catches_invalid_csv(tmp_path):
    csv_path = tmp_path / "invalid.csv"

    csv_path.write_text(
        "",
        encoding="utf-8")

    with pytest.raises(ValueError, match="CSV file is empty"):
        inspect_csv_schema(csv_path)