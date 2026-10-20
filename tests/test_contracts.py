import pytest

from app.contracts import validate_contract

def valid_contract():
    return {
        "name": "weighbridge_tickets",
        "version": "1.0",
        "fields": {
            "ticket_id": {
                "type": "string",
                "required": True
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

