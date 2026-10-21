import pytest

from app.contracts import validate_contract, load_contract


def valid_contract():
    return {
        "name": "weighbridge_tickets",
        "version": "1.0",
        "fields": {
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


def test_validate_contract_accepts_valid_contract():
    contract = valid_contract()

    validate_contract(contract)


def test_validate_contract_rejects_unsupported_field_type():
    contract = valid_contract()
    contract["fields"]["gross_weight"]["type"] = "numbr"

    with pytest.raises(ValueError, match="Unsupported field type"):
        validate_contract(contract)


def test_validate_contract_rejects_missing_field_type():
    contract = valid_contract()
    del contract["fields"]["gross_weight"]["type"]

    with pytest.raises(ValueError, match="missing required key: type"):
        validate_contract(contract)


def test_validate_contract_rejects_undefined_rule_field():
    contract = valid_contract()
    contract["rules"][0]["result"] = "missing_weight"

    with pytest.raises(ValueError, match="references undefined field"):
        validate_contract(contract)


def test_validate_contract_rejects_unsupported_rule_type():
    contract = valid_contract()
    contract["rules"][0]["type"] = "unknown_rule"

    with pytest.raises(ValueError, match="Unsupported rule type"):
        validate_contract(contract)


def test_validate_contract_rejects_non_numeric_minimum():
    contract = valid_contract()
    contract["fields"]["gross_weight"]["minimum"] = "zero"

    with pytest.raises(ValueError, match="must be a finite number"):
        validate_contract(contract)


def test_validate_contract_rejects_negative_tolerance():
    contract = valid_contract()
    contract["rules"][0]["tolerance"] = -1

    with pytest.raises(ValueError, match="non-negative number"):
        validate_contract(contract)