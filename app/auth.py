from functools import wraps

from clerk_backend_api import (
    AuthenticateRequestOptions,
    authenticate_request,
)
from flask import abort, current_app, g, request


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
            abort(401, description=reason)

        user_id = state.payload.get("sub")

        if not user_id:
            abort(401, description="User identity missing")

        g.auth_state = state
        g.user_id = user_id

        return view(*args, **kwargs)

    return wrapper