import tempfile
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request

from app.contracts import list_contracts, load_contract
from app.validator import validate_csv
from app.jobs.job_store import DATABASE_PATH, create_job, get_job


api_bp = Blueprint("api", __name__)

JOB_UPLOAD_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "uploads"
)


def _load_requested_contract(contract_name, contract_version):
    """Load a selected contract and return any appropriate API error."""
    try:
        contract = load_contract(
            contract_name,
            contract_version,
        )
        return contract, None

    except FileNotFoundError as exc:
        return None, (
            jsonify({"error": str(exc)}),
            404,
        )

    except ValueError as exc:
        # An existing contract definition is invalid or inconsistent.
        return None, (
            jsonify({
                "error": "The selected contract is invalid",
                "details": str(exc),
            }),
            500,
        )


@api_bp.route("/contracts", methods=["GET"])
def get_contracts():
    """List the available contract versions."""
    try:
        contracts = list_contracts()

    except (OSError, ValueError) as exc:
        return jsonify({
            "error": "Available contracts could not be loaded",
            "details": str(exc),
        }), 500

    return jsonify({
        "contracts": contracts,
    }), 200


@api_bp.route("/validate", methods=["POST"])
def validate_dataset():
    """Validate an uploaded CSV against an explicit contract version."""
    uploaded_file = request.files.get("file")
    contract_name = request.form.get("contract_name", "").strip()
    contract_version = request.form.get(
        "contract_version",
        "",
    ).strip()

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "error": "A CSV file is required in the 'file' field"
        }), 400

    if not contract_name:
        return jsonify({
            "error": "The 'contract_name' field is required"
        }), 400

    if not contract_version:
        return jsonify({
            "error": "The 'contract_version' field is required"
        }), 400

    contract, error_response = _load_requested_contract(
        contract_name,
        contract_version,
    )

    if error_response is not None:
        return error_response

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "uploaded.csv"
            uploaded_file.save(csv_path)

            report = validate_csv(csv_path, contract)

    except (OSError, ValueError) as exc:
        return jsonify({
            "error": "The uploaded CSV could not be processed",
            "details": str(exc),
        }), 400

    return jsonify(report), 200


@api_bp.route("/detect-drift", methods=["POST"])
def detect_drift():
    """Report contract schema mismatches and data-quality issues."""
    uploaded_file = request.files.get("file")
    contract_name = request.form.get("contract_name", "").strip()
    contract_version = request.form.get(
        "contract_version",
        "",
    ).strip()

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "error": "A CSV file is required in the 'file' field"
        }), 400

    if not contract_name:
        return jsonify({
            "error": "The 'contract_name' field is required"
        }), 400

    if not contract_version:
        return jsonify({
            "error": "The 'contract_version' field is required"
        }), 400

    contract, error_response = _load_requested_contract(
        contract_name,
        contract_version,
    )

    if error_response is not None:
        return error_response

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "uploaded.csv"
            uploaded_file.save(csv_path)

            validation_report = validate_csv(
                csv_path,
                contract,
            )

    except (OSError, ValueError) as exc:
        return jsonify({
            "error": "The uploaded CSV could not be processed",
            "details": str(exc),
        }), 400

    schema_issue_codes = {
        "MISSING_COLUMN",
        "UNEXPECTED_COLUMN",
    }

    findings = [
        issue
        for issue in validation_report["issues"]
        if issue["code"] in schema_issue_codes
    ]

    return jsonify({
        "contract_name": contract_name,
        "contract_version": contract_version,
        "has_drift": bool(findings),
        "findings": findings,
        "data_quality": validation_report,
    }), 200


@api_bp.route("/jobs", methods=["POST"])
def submit_job():
    """Accept a CSV for asynchronous validation."""
    uploaded_file = request.files.get("file")
    contract_name = request.form.get("contract_name", "").strip()
    contract_version = request.form.get(
        "contract_version",
        "",
    ).strip()

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "error": "A CSV file is required in the 'file' field"
        }), 400

    if not contract_name:
        return jsonify({
            "error": "The 'contract_name' field is required"
        }), 400

    if not contract_version:
        return jsonify({
            "error": "The 'contract_version' field is required"
        }), 400

    contract, error_response = _load_requested_contract(
        contract_name,
        contract_version,
    )

    if error_response is not None:
        return error_response

    JOB_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    upload_path = JOB_UPLOAD_DIR / f"{uuid.uuid4().hex}.csv"
    uploaded_file.save(upload_path)

    try:
        job = create_job(
            dataset_name=contract_name,
            input_path=upload_path,
            contract=contract,
            db_path=DATABASE_PATH,
        )

    except Exception:
        # Remove the uploaded file if job creation fails.
        upload_path.unlink(missing_ok=True)
        raise

    return jsonify({
        "job_id": job["id"],
        "contract_name": contract_name,
        "contract_version": contract_version,
        "status": job["status"],
        "created_at": job["created_at"],
        "status_url": f"/jobs/{job['id']}",
    }), 202


@api_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Return the public status and result of a submitted job."""
    job = get_job(
        job_id=job_id,
        db_path=DATABASE_PATH,
    )

    if job is None:
        return jsonify({
            "error": f"Job '{job_id}' was not found"
        }), 404

    return jsonify({
        "job_id": job["id"],
        "contract_name": job["dataset_name"],
        "contract_version": job["contract"]["version"],
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "result": job["result"],
        "error": job["error"],
    }), 200