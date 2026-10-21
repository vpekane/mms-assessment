import csv
from datetime import datetime
from pathlib import Path


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
