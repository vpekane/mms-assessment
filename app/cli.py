import argparse
import json
import sys
from pathlib import Path

from app.contracts import load_contract
from app.validator import validate_csv


def build_parser():
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Validate datasets against Sentinel data contracts.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a CSV file against a YAML contract.",
    )

    validate_parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the CSV file to validate.",
    )

    validate_parser.add_argument(
        "--contract",
        required=True,
        help="Contract identifier such as 'weighbridge'.",
    )

    validate_parser.add_argument(
        "--contract_version",
        required=True,
        help="Explicit contract version, such as '1.0'."
    )

    validate_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print the result as JSON.",
    )

    return parser


def print_report(contract, csv_path, report):
    """Print a human-readable validation report."""
    print(
        f"Contract: {contract['name']} "
        f"(version {contract['version']})"
    )
    print(f"File: {csv_path}")
    print(f"Status: {report['status']}")
    print(f"Total records: {report['total_records']}")
    print(f"Valid records: {report['valid_records']}")
    print(f"Invalid records: {report['invalid_records']}")
    print(f"Total issues: {len(report['issues'])}")

    for issue in report["issues"]:
        if issue["row"] is None:
            location = "dataset"
        else:
            location = f"row {issue['row']}"

        if issue["field"]:
            location += f", field '{issue['field']}'"

        print(
            f"- [{issue['code']}] {location}: "
            f"{issue['message']}"
        )


def main(argv=None):
    """Run a Sentinel CLI command and return its exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        contract = load_contract(args.contract, args.contract_version)

        report = validate_csv(
            args.csv_path,
            contract,
        )

    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        output = {
            "contract": {
                "name": contract["name"],
                "version": contract["version"],
            },
            "csv_path": str(args.csv_path),
            "report": report,
        }

        print(json.dumps(output, indent=2))

    else:
        print_report(
            contract=contract,
            csv_path=args.csv_path,
            report=report,
        )

    if report["status"] == "READY":
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())