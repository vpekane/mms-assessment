from pathlib import Path
import yaml

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


def validate_contract(contract: dict) -> None:
    """Validate the structure of a parsed contract"""

    if not isinstance(contract, dict):
        raise ValueError("Contract must contain a valid YAML mapping")

    required_fields = ["name", "version", "fields"]

    for key in required_fields:
        if key not in contract:
            raise ValueError(f"Contract is missing required key: {key}")

    if not isinstance(contract["fields"], dict):
        raise ValueError("'fields' must be a mapping")

    if not contract["fields"]:
        raise ValueError("Contract must define at least one field")

def load_contract(contract_name: str) -> dict:
    """Load a YAML contract and validate its structure"""

    contract_path = CONTRACTS_DIR / f"{contract_name}"

    try:
        with contract_path.open('r', encoding="utf-8") as file:
            contract = yaml.safe_load(file)

    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Contract file: '{contract_name}.yaml' was not found"
                                ) from exc

    except yaml.YAMLError as exc:
        raise ValueError(f"Contract file '{contract_name}.yaml' contains invalid YAML"
                         ) from exc

    validate_contract(contract_name)

    return contract


# print(load_contract('weighbridge.yaml'))