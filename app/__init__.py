import os
from pathlib import Path

from flask_cors import CORS
from dotenv import load_dotenv
from flask import Flask


def create_app():
    # Load the .env file from the project root.
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    app = Flask(__name__)

    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    # Clerk authentication configuration.
    app.config["CLERK_SECRET_KEY"] = os.getenv(
        "CLERK_SECRET_KEY"
    )

    app.config["CLERK_JWT_KEY"] = os.getenv(
        "CLERK_JWT_KEY"
    )

    app.config["CLERK_AUTHORIZED_PARTIES"] = [
        origin.strip()
        for origin in os.getenv(
            "CLERK_AUTHORIZED_PARTIES", ""
        ).split(",")
        if origin.strip()
    ]

    CORS(
    app,
    resources={
        r"/*": {
            "origins": app.config["CLERK_AUTHORIZED_PARTIES"]
        }
    },
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    from app.api import api_bp

    app.register_blueprint(api_bp)

    return app