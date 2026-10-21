import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def add_issue(issues, row, field, code, message):

    issues.append({
        "row": row,
        "field": field,
        "code": code,
        "message": message,
    })


def validate_headers(headers, contract, issues):
    """Check that the CSV containd headers a contract expected coloumns"""

    expected_headers = set(contract["fields"])
    actual_headers = set(headers)

    for field in sorted(expected_headers - actual_headers):
        add_issue(
            issues,
            row=1,
            field=field,
            code="MISSING_COLUMN",
            message=f"Required column '{field}' is missing"
        )

    for field in sorted(actual_headers - expected_headers):
        add_issue(
            issues,
            row=1,
            field=field,
            code="UNEXPECTED_COLUMN",
            message=f"Column '{field}' is not defined in the contract"
        )


def validate_field_value(value, field_name, rules, row, issues):
    """Validate one field value against its contract definition."""

    if value is None or not value.strip():
        if rules.get("required", False):
            add_issue(
                issues,
                row,
                field_name,
                "REQUIRED",
                f"'{field_name}' is required",
            )
        return

    field_type = rules.get("type")

    if field_type == "string":
        return

    if field_type == "number":
        try:
            number = float(value)
        except ValueError:
            add_issue(
                issues,
                row,
                field_name,
                "INVALID_NUMBER",
                f"'{field_name}' must be numeric",
            )
            return

        minimum = rules.get("minimum")

        if minimum is not None and number < minimum:
            add_issue(
                issues,
                row,
                field_name,
                "BELOW_MINIMUM",
                f"'{field_name}' must be at least {minimum}",
            )

    elif field_type == "datetime":
        try:
            datetime.fromisoformat(value)
        except ValueError:
            add_issue(
                issues,
                row,
                field_name,
                "INVALID_DATETIME",
                f"'{field_name}' must be a valid ISO-format datetime",
            )

    else:
        add_issue(
            issues,
            row,
            field_name,
            "UNKNOWN_TYPE",
            f"Unsupported field type '{field_type}' for '{field_name}'",
        )


def validate_unique_values(records, contract, issues):
    """Detect duplicate values in fields marked as unique."""

    for field_name, rules in contract["fields"].items():
        if not rules.get("unique", False):
            continue

        seen = set()

        for row_number, record in enumerate(records, start=2):
            value = record.get(field_name)

            if value is None or not value.strip():
                continue

            if value in seen:
                add_issue(
                    issues,
                    row_number,
                    field_name,
                    "DUPLICATE_VALUE",
                    f"'{field_name}' contains duplicate value '{value}'",
                )
            else:
                seen.add(value)


def validate_cross_field_rules(records, contract, issues):
    """Apply supported cross-field consistency rules."""

    for rule in contract.get("rules", []):
        if rule.get("type") != "difference_equals":
            continue

        left = rule["left"]
        subtract = rule["subtract"]
        result = rule["result"]
        tolerance = rule.get("tolerance", 0)

        for row_number, record in enumerate(records, start=2):
            try:
                left_value = float(record[left])
                subtract_value = float(record[subtract])
                result_value = float(record[result])
            except (KeyError, TypeError, ValueError):
                # Individual field checks report missing or invalid values.
                continue

            expected = left_value - subtract_value

            if abs(expected - result_value) > tolerance:
                add_issue(
                    issues,
                    row_number,
                    result,
                    "WEIGHT_MISMATCH",
                    (
                        f"Expected {result} to equal "
                        f"{left} - {subtract} "
                        f"({expected}), but got {result_value}"
                    ),
                )


def validate_csv(csv_path, contract):
    """Validate a CSV file against a loaded contract."""

    csv_path = Path(csv_path)

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    issues = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        headers = reader.fieldnames

        if not headers:
            raise ValueError("CSV file is empty or has no header row")

        header_counts = Counter(headers)

        duplicate_headers = sorted(
            header
            for header, count in header_counts.items()
            if count > 1
        )

        if duplicate_headers:
            raise ValueError(
                "CSV contains duplicate column names: "
                + ", ".join(duplicate_headers)
            )

        validate_headers(headers, contract, issues)


        records = list(reader)

    # A missing contract column means the associated checks cannot run.
    available_fields = set(headers)

    for row_number, record in enumerate(records, start=2):
        for field_name, rules in contract["fields"].items():
            if field_name not in available_fields:
                continue

            validate_field_value(
                record.get(field_name),
                field_name,
                rules,
                row_number,
                issues,
            )

    validate_unique_values(records, contract, issues)
    validate_cross_field_rules(records, contract, issues)

    invalid_rows = {
        issue["row"]
        for issue in issues
        if issue["row"] > 1
    }

    total_records = len(records)
    invalid_records = len(invalid_rows)
    valid_records = total_records - invalid_records

    status = "READY" if not issues else "NOT_READY"

    return {
        "status": status,
        "total_records": total_records,
        "valid_records": valid_records,
        "invalid_records": invalid_records,
        "issues": issues,
    }
