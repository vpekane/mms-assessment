import csv
import json
from datetime import datetime
from pathlib import Path


BASELINES_DIR = Path(__file__).resolve().parent.parent / "baselines"


def save_baseline(dataset_name, schema):
    """Save an accepted schema as a JSON baseline."""

    if not dataset_name or Path(dataset_name).name != dataset_name:
        raise ValueError("Invalid dataset name")

    BASELINES_DIR.mkdir(parents=True, exist_ok=True)

    baseline_path = BASELINES_DIR / f"{dataset_name}.json"

    with baseline_path.open("w", encoding="utf-8") as file:
        json.dump(schema, file, indent=2, sort_keys=True)

    return baseline_path


def load_baseline(dataset_name):
    """Load a previously saved schema baseline."""

    if not dataset_name or Path(dataset_name).name != dataset_name:
        raise ValueError("Invalid dataset name")

    baseline_path = BASELINES_DIR / f"{dataset_name}.json"

    if not baseline_path.is_file():
        raise FileNotFoundError(
            f"Baseline for '{dataset_name}' was not found"
        )

    with baseline_path.open("r", encoding="utf-8") as file:
        baseline = json.load(file)

    if not isinstance(baseline, dict):
        raise ValueError("Baseline must contain a JSON object")

    return baseline


def infer_type(value) -> None:
    """Infer the likely data type of a non-empty CSV value."""

    value = value.strip()

    if not value:
        return "unknown"

    if value.lower() in {"true", "false"}:
        return "boolean"

    try:
        datetime.fromisoformat(value)
        return "datetime"
    except ValueError:
        pass

    try:
        float(value)
        return "number"
    except ValueError:
        pass

    return "string"


def inspect_csv_schema(csv_path: str) -> dict:
    """Inspect a CSV file and infer the type of each column."""

    csv_path = Path(csv_path)

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no header row")

        headers = reader.fieldnames

        if len(headers) != len(set(headers)):
            raise ValueError("CSV contains duplicate column names")

        column_values = {header: [] for header in headers}

        for row in reader:
            for header in headers:
                value = row.get(header)

                if value is not None and value.strip():
                    column_values[header].append(value)

    schema = {}

    for header, values in column_values.items():
        inferred_types = {
            infer_type(value)
            for value in values
        }

        if not inferred_types:
            schema[header] = "unknown"
        elif len(inferred_types) == 1:
            schema[header] = inferred_types.pop()
        else:
            schema[header] = "mixed"

    return schema


def compare_schemas(baseline, current_schema):
    """Compare a saved schema against a newly observed schema."""

    findings = []

    baseline_fields = set(baseline)
    current_fields = set(current_schema)

    # Detect columns that have been added.
    for field in sorted(current_fields - baseline_fields):
        findings.append({
            "code": "ADDED_COLUMN",
            "field": field,
            "expected": None,
            "actual": current_schema[field],
            "message": f"Column '{field}' was added",
        })

    # Detect columns that have been removed.
    for field in sorted(baseline_fields - current_fields):
        findings.append({
            "code": "REMOVED_COLUMN",
            "field": field,
            "expected": baseline[field],
            "actual": None,
            "message": f"Column '{field}' was removed",
        })

    # Compare types for columns present in both schemas.
    shared_fields = baseline_fields & current_fields

    for field in sorted(shared_fields):
        expected_type = baseline[field]
        actual_type = current_schema[field]

        if actual_type == "mixed":
            findings.append({
                "code": "MIXED_TYPE",
                "field": field,
                "expected": expected_type,
                "actual": actual_type,
                "message": (
                    f"Column '{field}' contains inconsistent data types"
                ),
            })

        elif actual_type != "unknown" and actual_type != expected_type:
            findings.append({
                "code": "TYPE_CHANGED",
                "field": field,
                "expected": expected_type,
                "actual": actual_type,
                "message": (
                    f"Column '{field}' changed type from "
                    f"'{expected_type}' to '{actual_type}'"
                ),
            })

    return {
        "has_drift": bool(findings),
        "findings": findings,
    }


def detect_schema_drift(csv_path, dataset_name):
    """Inspect a CSV and compare its schema with a saved baseline"""

    current_schema = inspect_csv_schema(csv_path)

    baseline = load_baseline(dataset_name)

    comparison = compare_schemas(baseline, current_schema)

    return {
        "dataset_name": dataset_name,
        "has_drift": comparison["has_drift"],
        "findings": comparison["findings"],
    }