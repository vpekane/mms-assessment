import json
import pytest
from app.drift_detection import infer_type, inspect_csv_schema, compare_schemas
import app.drift_detection as drift


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


def test_save_baseline_creates_json_file(tmp_path, monkeypatch):
    monkeypatch.setattr(drift, "BASELINES_DIR", tmp_path)

    schema = {
        "ticket_id": "string",
        "gross_weight": "number",
    }

    baseline_path = drift.save_baseline("weighbridge", schema)

    assert baseline_path.is_file()

    saved_schema = json.loads(
        baseline_path.read_text(encoding="utf-8")
    )

    assert saved_schema == schema


def test_load_baseline_returns_saved_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(drift, "BASELINES_DIR", tmp_path)

    schema = {
        "ticket_id": "string",
        "gross_weight": "number",
    }

    drift.save_baseline("weighbridge", schema)

    loaded_schema = drift.load_baseline("weighbridge")

    assert loaded_schema == schema


def test_load_baseline_fails_when_baseline_does_not_exist(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(drift, "BASELINES_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="was not found"):
        drift.load_baseline("unknown_dataset")


def test_save_baseline_rejects_invalid_dataset_name():
    with pytest.raises(ValueError, match="Invalid dataset name"):
        drift.save_baseline("../outside", {"ticket_id": "string"})


def test_comparing_schemas_detects_no_changes_when_schemas_match():
    baseline = {
        "ticket_id": "string",
        "gross_weight": "number",
    }

    current_schema = {
        "ticket_id": "string",
        "gross_weight": "number",
    }

    result = compare_schemas(baseline, current_schema)

    assert result["has_drift"] == False
    assert result["findings"] == []


def test_compare_schemas_detects_added_column():
    baseline = {
        "ticket_id": "string",
    }

    current_schema = {
        "ticket_id": "string",
        "vehicle_type": "string",
    }

    report = compare_schemas(baseline, current_schema)

    assert report["has_drift"] is True
    assert report["findings"] == [
        {
            "code": "ADDED_COLUMN",
            "field": "vehicle_type",
            "expected": None,
            "actual": "string",
            "message": "Column 'vehicle_type' was added",
        }
    ]


def test_compare_schemas_detects_removed_column():
    baseline = {
        "ticket_id": "string",
        "gross_weight": "number",
    }

    current_schema = {
        "ticket_id": "string",
    }

    report = compare_schemas(baseline, current_schema)

    assert report["has_drift"] is True
    assert report["findings"][0]["code"] == "REMOVED_COLUMN"
    assert report["findings"][0]["field"] == "gross_weight"
    assert report["findings"][0]["expected"] == "number"
    assert report["findings"][0]["actual"] is None


def test_compare_schemas_detects_type_change():
    baseline = {
        "gross_weight": "number",
    }

    current_schema = {
        "gross_weight": "string",
    }

    report = compare_schemas(baseline, current_schema)

    assert report["has_drift"] is True
    assert report["findings"][0]["code"] == "TYPE_CHANGED"
    assert report["findings"][0]["field"] == "gross_weight"
    assert report["findings"][0]["expected"] == "number"
    assert report["findings"][0]["actual"] == "string"


def test_compare_schemas_detects_mixed_types():
    baseline = {
        "gross_weight": "number",
    }

    current_schema = {
        "gross_weight": "mixed",
    }

    report = compare_schemas(baseline, current_schema)

    assert report["has_drift"] is True
    assert report["findings"][0]["code"] == "MIXED_TYPE"


def test_compare_schemas_does_not_report_type_change_for_unknown():
    baseline = {
        "gross_weight": "number",
    }

    current_schema = {
        "gross_weight": "unknown",
    }

    report = compare_schemas(baseline, current_schema)

    assert report["has_drift"] is False
    assert report["findings"] == []

def test_detect_schema_drift_no_changes(tmp_path, monkeypatch):
    baseline_dir = tmp_path / "baselines"
    monkeypatch.setattr(drift, "BASELINES_DIR", baseline_dir)

    drift.save_baseline("weighbridge", {
        "ticket_id": "string",
        "gross_weight": "number",
    })

    csv_path = tmp_path / "incoming.csv"
    csv_path.write_text(
        "ticket_id,gross_weight\n"
        "T-001,1200.5\n"
        "T-002,1350.0\n",
        encoding="utf-8",
    )

    report = drift.detect_schema_drift(csv_path, "weighbridge")

    assert report["dataset_name"] == "weighbridge"
    assert report["has_drift"] is False
    assert report["findings"] == []


def test_detect_schema_drift_detects_type_change(tmp_path, monkeypatch):
    baseline_dir = tmp_path / "baselines"
    monkeypatch.setattr(drift, "BASELINES_DIR", baseline_dir)

    drift.save_baseline("weighbridge", {
        "ticket_id": "string",
        "gross_weight": "number",
    })

    csv_path = tmp_path / "incoming.csv"
    csv_path.write_text(
        "ticket_id,gross_weight\n"
        "T-001,not-a-number\n"
        "T-002,also-not-a-number\n",
        encoding="utf-8",
    )

    report = drift.detect_schema_drift(csv_path, "weighbridge")

    assert report["has_drift"] is True
    assert report["findings"][0]["code"] == "TYPE_CHANGED"
    assert report["findings"][0]["field"] == "gross_weight"
    assert report["findings"][0]["expected"] == "number"
    assert report["findings"][0]["actual"] == "string"


def test_detect_schema_drift_fails_when_baseline_is_missing(
    tmp_path, monkeypatch
):
    baseline_dir = tmp_path / "baselines"
    monkeypatch.setattr(drift, "BASELINES_DIR", baseline_dir)

    csv_path = tmp_path / "incoming.csv"
    csv_path.write_text(
        "ticket_id,gross_weight\n"
        "T-001,1200.5\n",
        encoding="utf-8",
    )

    with pytest.raises(
        FileNotFoundError,
        match="Baseline for 'weighbridge' was not found",
    ):
        drift.detect_schema_drift(csv_path, "weighbridge")


