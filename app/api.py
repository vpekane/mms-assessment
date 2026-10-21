import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from app.contracts import load_contract
from app.validator import validate_csv


api_bp = Blueprint("api", __name__)

@api_bp.route("/validate", methods=["POST"])
def validate_dataset():
    uploaded_file = request.files.get("file")
    contract_name = request.form.get("contract_name", "").strip()

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "error": "A CSV file is required in the 'file' field"
        }), 400

    if not contract_name:
        return jsonify({
            "error": "The 'contract_name' field is required"
        }), 400

    try:
        contract = load_contract(contract_name)
    except FileNotFoundError:
        return jsonify({
            "error": f"Contract {contract_name} was not found"
        }), 404
    except ValueError as exc:
        # The contract exists but its contents are invalid
        return jsonify({
            "error": f"Contract '{contract_name}' is invalid",
            "details": str(exc)
        }), 500

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "uploaded.csv"
            uploaded_file.save(csv_path)

            report = validate_csv(csv_path, contract)

    except ValueError as exc:
        return jsonify({
            "error": "The uploaded CSV could not be processed",
            "details": str(exc)
        }), 400

    return jsonify(report), 200