import pytest
import yaml

from app.contracts import validate_contract, load_contract

def valid_contract():
    return {
        "name": "weighbridge_tickets",
        "version": "1.0",
        "fields": {
            "ticket_id":{
                "type": "string",
                "required": "true",
                "unique": "true"
                },
            "gross_weight":{
                "type": "number",
                "required": "true",
                "minimum": 0
                },
            "tare_weight":{
                "type": "number",
                "required": "true",
                "minimum": 0
                },
            "net_weight":{
                "type": "number",
                "required": "true",
                "minimum": 0
                },
            "timestamp":{
                "type": "datetime",
                "required": "true"
                }
            }
        }


def test_validate_contract_rejects_non_dictionary():
    contract = ["not", "a", "dictionary"]

    with pytest.raises(ValueError):
        validate_contract(contract)

def test_validate_contract_raises_error_for_missing_field():
    contract = valid_contract()

    del contract["name"]    

    with pytest.raises(ValueError, match="name"):
        validate_contract(contract)


def test_load_contract_is_successful_for_valid_contract():

    contract = load_contract("weighbridge")

    assert contract["name"] == "weighbridge_tickets"


def test_load_contract_fails_when_yaml_is_invalid(tmp_path, monkeypatch):
    contract_path = tmp_path / "broken.yaml"
    contract_path.write_text(
        "name: [Invalid structure,",
        encoding="utf-8"
    )

    monkeypatch.setattr(
        "app.contracts.CONTRACTS_DIR",
        tmp_path
    )

    with pytest.raises(ValueError, match="contains invalid YAML"):
        load_contract("broken")


def test_load_contract_fails_when_file_is_not_found():
    with pytest.raises(FileNotFoundError, match="'notfound.yaml'"):
        load_contract("notfound")