import tempfile
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request

from app.contracts import load_contract
from app.validator import validate_csv
from app.job_store import DATABASE_PATH, create_job, get_job

JOB_UPLOAD_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "uploads"
)


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


@api_bp.route("/detect-drift", methods=["POST"])
def detect_drift():
    uploaded_file = request.files.get("file")
    dataset_name = request.form.get("dataset_name", "").strip()

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "error": "A CSV file is required in the 'file' field"
        }), 400

    if not dataset_name:
        return jsonify({
            "error": "The 'dataset_name' field is required"
        }), 400

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "uploaded.csv"
            uploaded_file.save(csv_path)

            contract = load_contract(dataset_name)
            validation_report = validate_csv(csv_path, contract)

    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    except ValueError as exc:
        return jsonify({
            "error": "The uploaded CSV or contract could not be processed",
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
        "dataset_name": dataset_name,
        "has_drift": bool(findings),
        "findings": findings,
        "data_quality": validation_report,
    }), 200


@api_bp.route("/jobs", methods=["POST"])
def submit_job():
    uploaded_file = request.files.get("file")
    dataset_name = request.form.get("dataset_name", "").strip()

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "error": "A CSV file is required in the 'file' field"
        }), 400

    if not dataset_name:
        return jsonify({
            "error": "The 'dataset_name' field is required"
        }), 400

    try:
        contract = load_contract(dataset_name)

    except FileNotFoundError as exc:
        return jsonify({
            "error": str(exc)
        }), 404

    except ValueError as exc:
        return jsonify({
            "error": "The selected contract is invalid",
            "details": str(exc),
        }), 400

    JOB_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    upload_path = JOB_UPLOAD_DIR / f"{uuid.uuid4().hex}.csv"
    uploaded_file.save(upload_path)

    try:
        job = create_job(
            dataset_name=dataset_name,
            input_path=upload_path,
            contract=contract,
            db_path=DATABASE_PATH,
        )

    except Exception:
        # Avoid leaving an orphaned upload if job creation fails.
        upload_path.unlink(missing_ok=True)
        raise

    return jsonify({
        "job_id": job["id"],
        "dataset_name": job["dataset_name"],
        "status": job["status"],
        "created_at": job["created_at"],
        "status_url": f"/jobs/{job['id']}",
    }), 202


@api_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Return the public status and result of a submitted job"""

    job = get_job(job_id, db_path=DATABASE_PATH)

    if job is None:
        return jsonify({
            "error": f"Job '{job_id}' was not found"
        }), 404

    return jsonify({
        "job_id": job_id,
        "dataset_name": job["dataset_name"],
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "result": job["result"],
        "error": job["error"],
    }), 200