# Sentinel — Integration Readiness & Drift Sentinel

Sentinel is a contract-driven CSV validation service. It checks uploaded datasets against an explicitly selected, versioned YAML contract and reports whether the data satisfies the expected structure, types, and business rules.

The current application includes a React/TypeScript frontend, a Flask API, Clerk authentication, a shared Python validation engine, a background worker, SQLite job persistence, local upload storage, and a command-line validation entry point.

> **Implementation status:** This README documents the current local-development workflow. Scheduled ingestion, external-system connectors, automatic correction of customer data, automatic recovery of abandoned `RUNNING` jobs, and production-scale capacity guarantees are not currently implemented.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Run Sentinel locally](#run-sentinel-locally)
- [Use the application](#use-the-application)
- [API overview](#api-overview)
- [Command-line validation](#command-line-validation)
- [Run the tests](#run-the-tests)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)

## Features

- **Contract-driven validation:** Check CSV headers, field types, required fields, and supported business rules against a selected contract.
- **Versioned contracts:** Select the contract version explicitly. Incoming files never become the schema or silently update a contract.
- **Validation reports:** Return `READY` or `NOT_READY`, record counts, and structured issues.
- **Schema-drift findings:** Report missing and unexpected columns relative to the selected contract.
- **Asynchronous jobs:** Submit a validation job, receive a job ID, and retrieve its result after processing.
- **Reusable validation engine:** Reuse the same core validation logic through the API, worker, and CLI.
- **Authentication and ownership:** Clerk provides user identity; the backend restricts job retrieval to the user who submitted the job.
- **Persistent job state:** Save job metadata, contract snapshots, status, results, errors, and timestamps in SQLite.

Sentinel reports data-quality issues rather than automatically correcting customer data. A `NOT_READY` validation result is not the same as a processing failure.

## Architecture

1. The React frontend lets a user sign in, select a contract and version, upload a CSV, and monitor a job.
2. The Flask API authenticates requests and either validates synchronously or creates an asynchronous job.
3. For an asynchronous job, the API saves the upload and creates a SQLite record containing the owner and a snapshot of the selected contract.
4. The background worker claims queued jobs and calls the shared validation engine.
5. The worker saves the report and final job status. The frontend polls the API to retrieve the status and result.

SQLite stores job records and local filesystem storage holds uploaded CSV files and contract files. The application does not require a separate database server for local development.

## Requirements

- Python **3.12** recommended.
- Node.js and npm (use a current supported LTS release).
- Git, if cloning from a repository.
- A Clerk application with development keys for sign-in and backend authentication.

Check your installed tools:

```bash
python3 --version
node --version
npm --version
git --version
```

The backend and frontend are run as separate processes during development. The background worker must also be running to process asynchronously submitted jobs.

## Installation

### 1. Get the source code

Clone the repository and enter its root directory. Replace the placeholder with the repository URL:

```bash
git clone <repository-url>
cd <repository-directory>
```

The repository root is the directory containing the Python dependency file and the `frontend/` directory.

### 2. Create a Python virtual environment

From the repository root, run:

**Linux/macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents virtual-environment activation, use an approved local execution-policy setting or activate the environment from Command Prompt with `.venv\Scripts\activate.bat`.

Keep the virtual environment activated when running the API, worker, CLI, or tests.

### 3. Install frontend dependencies

Open a terminal at the repository root and run:

```bash
cd frontend
npm install
cd ..
```

`npm install` reads the frontend's `package.json` and lockfile, if present, to install the JavaScript dependencies.

## Configuration

Sentinel uses Clerk for authentication. You must configure development keys before signing in and calling protected API endpoints.

### Backend environment

Provide the Clerk secret key to the backend environment. The key is available in your Clerk dashboard for your development application.

For a shell session, set it before starting the API and worker:

**Linux/macOS**

```bash
export CLERK_SECRET_KEY="sk_test_replace_with_your_development_secret_key"
```

**Windows PowerShell**

```powershell
$env:CLERK_SECRET_KEY = "sk_test_replace_with_your_development_secret_key"
```

If the application is configured to load a root `.env` file, you can store the setting there instead. Do not commit `.env` files or real secrets to version control.

### Frontend environment

Create `frontend/.env.local` and add your Clerk **publishable** key:

```dotenv
VITE_CLERK_PUBLISHABLE_KEY=pk_test_replace_with_your_development_publishable_key
```

Use the matching development keys from the same Clerk application. Restart the Vite development server after changing environment variables. Variables prefixed with `VITE_` are exposed to frontend code; never put a secret key in a frontend environment file.

If your project configuration uses a different variable name, use the name referenced by the frontend entry point and Clerk provider configuration.

### Contracts and local data

Contract definitions are maintained as versioned YAML files in the configured contracts directory. Review the sample contract files before submitting data and select a contract name and version that match your CSV.

Uploaded files and the SQLite job store are created or accessed by the application using its configured local paths. Ensure the application has permission to write to the data directories. Do not delete the job database or uploaded files while jobs are being processed.

## Run Sentinel locally

Start the API, worker, and frontend in **three separate terminals**. Keep the Python virtual environment activated in both Python terminals.

### Terminal 1: Flask API

From the repository root:

```bash
flask --app app run --debug --host 127.0.0.1 --port 5000
```

The API should be available at `http://127.0.0.1:5000`. Keep debug mode for local development only; do not use it as a production server configuration.

If Flask cannot locate the application factory, check the package structure and application-factory name in the repository, then adjust the `--app` target to match it.

### Terminal 2: Background worker

From the repository root, with the virtual environment activated and the same backend environment variables set:

```bash
python -m app.worker
```

The worker is required for jobs submitted through `POST /jobs`. Without a running worker, jobs may remain queued. Stop the worker with `Ctrl+C` when shutting down the local application.

### Terminal 3: Frontend

From the repository root:

```bash
cd frontend
npm run dev
```

Open the local URL printed by Vite, commonly `http://localhost:5173`. Keep the terminal running while using the frontend.

The frontend calls API routes such as `/contracts` and `/jobs`. The development setup must proxy these requests to the Flask API. If the frontend loads but API requests fail, check the repository's Vite configuration and make sure the API is running on the configured port.

## Use the application

1. Open the frontend URL printed by Vite.
2. Sign up or sign in using the configured Clerk development application.
3. Select the appropriate contract and version.
4. Choose a CSV file. The file must conform to the selected contract's expected headers and rules.
5. Submit the validation job.
6. The frontend displays the job status while the worker processes it, then shows the validation report.

### Understand the statuses

**Job status** describes processing progress:

- `QUEUED` — waiting for a worker.
- `RUNNING` — currently being processed.
- `COMPLETED` — processing finished and a report was saved.
- `FAILED` — processing could not be completed successfully.

**Validation status** describes the data-quality result:

- `READY` — the file satisfies the evaluated contract requirements.
- `NOT_READY` — the report contains contract violations.

A job can be `COMPLETED` with validation status `NOT_READY`. This means Sentinel successfully checked the file and reported issues; it does not mean the worker failed.

### Example CSV

The following is an illustrative weighbridge-style CSV. Use it only if the selected contract expects these columns and values:

```csv
ticket_id,gross_weight,tare_weight,net_weight,timestamp
WB001,15000,5000,10000,2026-10-20T08:30:00
```

The selected YAML contract, not this example, is the authoritative definition of valid input.

## API overview

Protected endpoints require authentication. The frontend handles the normal signed-in user flow.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/contracts` | Lists available contract names, display names, and versions. |
| `POST` | `/validate` | Validates a CSV synchronously and returns a report. |
| `POST` | `/detect-drift` | Returns schema-drift findings and associated data-quality information. |
| `POST` | `/jobs` | Accepts multipart fields `file`, `contract_name`, and `contract_version`; creates an asynchronous job and returns `202 Accepted`. |
| `GET` | `/jobs/<job_id>` | Returns the authenticated owner's job status and available result or error. |
| `GET` | `/me` | Returns the user identity recognised by the backend. |

The asynchronous flow uses `POST /jobs`, then polls `GET /jobs/<job_id>` until the job reaches a final state. A request for a job that does not exist or belongs to another user returns `404 Not Found`.

The current request-size limit is 10 MiB. The synchronous endpoints perform their work inside the HTTP request; use the asynchronous job endpoint for the background-processing workflow.

## Command-line validation

The CLI uses the shared contract loader and validation engine without requiring the frontend. From the repository root, with the Python environment activated, view the options supported by the current CLI:

```bash
python -m app.cli --help
```

Follow the displayed CLI syntax and provide the CSV path, contract name, and contract version explicitly. Do not rely on inferred schemas or automatically select a different contract version.

## Run the tests

From the repository root, with the Python virtual environment activated:

```bash
pytest
```

The test suite covers the API, CLI, contract loading, job persistence, validation engine, and worker. Tests should not require real Clerk credentials; API tests should use the project's authentication test fixtures or mocks.

To run a specific test module:

```bash
pytest tests/test_validator.py
pytest tests/test_job_store.py
pytest tests/test_worker.py
pytest tests/test_cli.py
pytest tests/test_api.py
```

To build the frontend and check that the TypeScript/Vite build succeeds:

```bash
cd frontend
npm run build
```

## Project layout

The main areas of the repository are:

```text
.
├── app/                 # Flask application, auth, contracts, validation, job store, worker and CLI
├── contracts/           # Versioned YAML contract definitions (configured location)
├── data/                # Local uploads and runtime data (generated/used by the app)
├── frontend/            # React + TypeScript frontend
├── tests/               # Python test suite
├── requirements.txt     # Python dependencies
└── README.md
```

This is a high-level guide; some supporting files may be named or arranged differently in the actual repository.

## Troubleshooting

### The API returns `401 Unauthorized`

- Confirm that the Clerk frontend publishable key and backend secret key come from the same Clerk application and environment.
- Sign in again in the frontend and retry.
- Confirm the backend can read `CLERK_SECRET_KEY` and that the frontend is configured to pass authenticated requests as expected.
- Never work around authentication by disabling the backend ownership checks.

### No contracts appear in the frontend

- Confirm that contract YAML files exist in the configured contracts directory.
- Check that the files follow the expected contract structure and naming/version convention.
- Review the API terminal for YAML parsing or contract-loading errors.

### Jobs remain `QUEUED`

- Confirm that the background worker is running in a separate terminal.
- Ensure the worker and API use the same project environment and the same configured SQLite job-store path.
- Check both terminal outputs for startup or database errors.

### Jobs remain `RUNNING`

The current implementation does not automatically recover jobs abandoned after a worker crash. Check the worker logs and job state. Do not assume the job will recover automatically after a restart.

### The frontend cannot reach the API

- Confirm the Flask API is running on the port configured in the Vite development proxy.
- Inspect browser developer tools for failed requests.
- Check the Vite terminal for proxy errors, and restart Vite after configuration changes.

### Python or npm dependencies fail to install

- Check Python and Node.js versions.
- Activate the Python virtual environment before installing or running Python packages.
- Run `python -m pip install -r requirements.txt` from the repository root and `npm install` from `frontend/`.

## Known limitations

- The current upload/request limit is 10 MiB.
- The application has not been load-tested; supported throughput and concurrency have not been established.
- SQLite and local file storage are intended for the current implementation and have not been demonstrated as a distributed production setup.
- Automatic recovery of jobs left in `RUNNING` is not implemented.
- Scheduled ingestion, external-system connectors, downstream delivery, and automatic data remediation are outside the current implementation.
- Contracts are maintained as files; users cannot manage contracts from the UI.
- Jobs are owned by individual users; shared organisation or team access is not implemented.

## Security notes

- Never commit backend secrets, frontend environment files containing sensitive configuration, or real customer CSV files.
- Only the Clerk publishable key belongs in frontend configuration. Keep the Clerk secret key on the backend.
- Do not treat frontend route visibility as an authorization boundary; the backend must enforce authentication and job ownership.
- Use Flask debug mode only for local development.

## License

No license is specified here. Add the project's chosen license and its terms before distributing the repository if required.
