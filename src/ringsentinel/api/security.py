"""Replaceable principal boundary; development headers are NOT authentication."""

import re

from fastapi import Request

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.service import Principal


def current_principal(request: Request) -> Principal:
    settings = request.app.state.settings
    if settings.auth_mode == "jwt":
        return request.app.state.token_verifier.verify(request.headers.get("Authorization", ""))
    if settings.environment not in {"development", "test"} or settings.auth_mode != "development":
        raise ProductError("UNAUTHORIZED")
    user_id = request.headers.get("X-Development-User", settings.development_user_id)
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", user_id):
        raise ProductError("UNAUTHORIZED")
    return Principal(user_id)
