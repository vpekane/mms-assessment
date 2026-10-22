import json
import yaml

from app.cli import main


def write_test_contract(directory, fields):
    contract = {
        "name": "test_dataset",
        "version": "1.0",
        "fields": fields,
    }

    contract_directory = directory / "test_dataset"
    contract_directory.mkdir(parents=True, exist_ok=True)

    contract_path = (
        contract_directory / "test_dataset_1.0.yaml"
    )

    contract_path.write_text(
        yaml.safe_dump(contract),
        encoding="utf-8",
    )

def test_cli_validates_csv_successfully(
    tmp_path,
    monkeypatch,
    capsys,
):
    write_test_contract(
        tmp_path,
        {
            "ticket_id": {
                "type": "string",
                "required": True,
            },
        },
    )

    csv_path = tmp_path / "input.csv"
    csv_path.write_text(
        "ticket_id\n"
        "WB001\n"
        "WB002\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.contracts.CONTRACTS_DIR",
        tmp_path,
    )

    exit_code = main([
        "validate",
        "--contract",
        "test_dataset",
        "--contract_version",
        "1.0",
        str(csv_path),
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Status: READY" in captured.out
    assert "Total records: 2" in captured.out
    assert captured.err == ""


def test_cli_returns_nonzero_for_invalid_data(
    tmp_path,
    monkeypatch,
    capsys,
):
    write_test_contract(
        tmp_path,
        {
            "amount": {
                "type": "number",
                "required": True,
                "minimum": 0,
            },
        },
    )

    csv_path = tmp_path / "input.csv"
    csv_path.write_text(
        "amount\n"
        "not-a-number\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.contracts.CONTRACTS_DIR",
        tmp_path,
    )

    exit_code = main([
        "validate",
        "--contract",
        "test_dataset",
        "--contract_version",
        "1.0",
        str(csv_path),
        "--json",
    ])

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert exit_code == 1
    assert output["report"]["status"] == "NOT_READY"

    issue_codes = {
        issue["code"]
        for issue in output["report"]["issues"]
    }

    assert "INVALID_NUMBER" in issue_codes