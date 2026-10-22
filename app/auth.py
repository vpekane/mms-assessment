from functools import wraps

from clerk_backend_api import (
    AuthenticateRequestOptions,
    authenticate_request,
)
from flask import current_app, g, jsonify, request


def clerk_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        state = authenticate_request(
            request,
            AuthenticateRequestOptions(
                secret_key=current_app.config["CLERK_SECRET_KEY"],
                jwt_key=current_app.config.get("CLERK_JWT_KEY"),
                authorized_parties=current_app.config[
                    "CLERK_AUTHORIZED_PARTIES"
                ],
                accepts_token=["session_token"],
            ),
        )

        if not state.is_signed_in:
            reason = (
                state.reason.name
                if state.reason
                else "unauthorized"
            )

            current_app.logger.warning(
                "Clerk authentication rejected request: %s",
                reason,
            )

            return jsonify({
                "error": "Unauthorized",
                "details": reason,
            }), 401

        user_id = state.payload.get("sub")

        if not user_id:
            current_app.logger.warning(
                "Clerk authentication succeeded without a user ID."
            )

            return jsonify({
                "error": "Unauthorized",
                "details": "User identity missing",
            }), 401

        g.auth_state = state
        g.user_id = user_id

        return view(*args, **kwargs)

    return wrapper