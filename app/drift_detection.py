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