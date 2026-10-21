from math import isfinite
from pathlib import Path

import yaml

SUPPORTED_FIELD_TYPES = {"string", "number", "datetime"}

SUPPORTED_RULE_TYPES = {"difference_equals"}

FIELD_RULE_KEYS = {"type", "required", "unique", "minimum"}

CROSS_FIELD_RULE_KEYS = {
    "name",
    "type",
    "left",
    "subtract",
    "result",
    "tolerance"
}

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


def validate_contract(contract: dict) -> None:
    """Validate the structure and supported rules of a parsed contract."""

    if not isinstance(contract, dict):
        raise ValueError("Contract must contain a YAML mapping")

    required_keys = ["name", "version", "fields"]

    for key in required_keys:
        if key not in contract:
            raise ValueError(
                f"Contract is missing required key: {key}"
            )

    if not isinstance(contract["name"], str) or not contract["name"].strip():
        raise ValueError("'name' must be a non-empty string")

    if (
        not isinstance(contract["version"], str)
        or not contract["version"].strip()
    ):
        raise ValueError("'version' must be a non-empty string")

    fields = contract["fields"]

    if not isinstance(fields, dict):
        raise ValueError("'fields' must be a mapping")

    if not fields:
        raise ValueError("Contract must define at least one field")

    # Validate each field definition.
    for field_name, field_rules in fields.items():
        if not isinstance(field_name, str) or not field_name.strip():
            raise ValueError("Contract field names must be non-empty strings")

        if not isinstance(field_rules, dict):
            raise ValueError(
                f"Definition for field '{field_name}' must be a mapping"
            )

        unknown_keys = set(field_rules) - FIELD_RULE_KEYS

        if unknown_keys:
            raise ValueError(
                f"Field '{field_name}' contains unsupported options: "
                f"{', '.join(sorted(unknown_keys))}"
            )

        if "type" not in field_rules:
            raise ValueError(
                f"Field '{field_name}' is missing required key: type"
            )

        field_type = field_rules["type"]

        if field_type not in SUPPORTED_FIELD_TYPES:
            raise ValueError(
                f"Unsupported field type '{field_type}' for '{field_name}'"
            )

        for option in ("required", "unique"):
            if option in field_rules and not isinstance(
                field_rules[option], bool
            ):
                raise ValueError(
                    f"'{option}' for field '{field_name}' must be a boolean"
                )

        if "minimum" in field_rules:
            minimum = field_rules["minimum"]

            if field_type != "number":
                raise ValueError(
                    f"'minimum' can only be used with number fields: "
                    f"'{field_name}'"
                )

            if (
                isinstance(minimum, bool)
                or not isinstance(minimum, (int, float))
                or not isfinite(minimum)
            ):
                raise ValueError(
                    f"'minimum' for field '{field_name}' "
                    "must be a finite number"
                )

    # Validate the contract's cross-field rules.
    rules = contract.get("rules", [])

    if not isinstance(rules, list):
        raise ValueError("'rules' must be a list")

    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(
                f"Contract rule at position {index} must be a mapping"
            )

        required_rule_keys = [
            "name",
            "type",
            "left",
            "subtract",
            "result",
        ]

        for key in required_rule_keys:
            if key not in rule:
                raise ValueError(
                    f"Contract rule at position {index} "
                    f"is missing required key: {key}"
                )

        rule_name = rule["name"]

        if not isinstance(rule_name, str) or not rule_name.strip():
            raise ValueError(
                f"Contract rule at position {index} "
                "must have a non-empty name"
            )

        unknown_keys = set(rule) - CROSS_FIELD_RULE_KEYS

        if unknown_keys:
            raise ValueError(
                f"Rule '{rule_name}' contains unsupported options: "
                f"{', '.join(sorted(unknown_keys))}"
            )

        rule_type = rule["type"]

        if rule_type not in SUPPORTED_RULE_TYPES:
            raise ValueError(
                f"Unsupported rule type '{rule_type}' "
                f"for rule '{rule_name}'"
            )

        for reference in ("left", "subtract", "result"):
            field_name = rule[reference]

            if not isinstance(field_name, str) or field_name not in fields:
                raise ValueError(
                    f"Rule '{rule_name}' references undefined field "
                    f"'{field_name}'"
                )

            if fields[field_name]["type"] != "number":
                raise ValueError(
                    f"Rule '{rule_name}' requires field '{field_name}' "
                    "to have type 'number'"
                )

        tolerance = rule.get("tolerance", 0)

        if (
            isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not isfinite(tolerance)
            or tolerance < 0
        ):
            raise ValueError(
                f"'tolerance' for rule '{rule_name}' "
                "must be a finite, non-negative number"
            )


def load_contract(contract_name: str) -> dict:
    """Load a YAML contract and validate its structure"""

    contract_path = CONTRACTS_DIR / f"{contract_name}.yaml"

    try:
        with contract_path.open('r', encoding="utf-8") as file:
            contract = yaml.safe_load(file)

    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Contract file: '{contract_name}.yaml' was not found"
                                ) from exc

    except yaml.YAMLError as exc:
        raise ValueError(f"Contract file '{contract_name}.yaml' contains invalid YAML"
                         ) from exc

    validate_contract(contract)

    return contract
