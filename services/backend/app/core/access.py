"""Request-scoped access rules. Owner: M3 (C-03/D09).

Two separate rules:

  - `candidate_scope` turns the session cookie into the candidate a request may
    read. Every candidate-scoped handler goes through it, so authorization is
    not something an individual route can forget.
  - `require_import_access` guards the manual job-import routes M2 builds. D09
    proposes team/admin-only imports; this is the server-side half of that. It
    is a shared bearer token compared in constant time, deliberately not an
    account system, and an unset token list keeps the route closed rather than
    open.
"""

from __future__ import annotations

import hmac

from fastapi import Request

from app.core.errors import Forbidden

SESSION_COOKIE = "acm_session"


def session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def set_session_cookie(response, session_id: str, settings, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=max_age,
        httponly=True,  # The token must never be readable by page scripts.
        samesite="lax",
        secure=settings.app_env == "production",
        path="/",
    )


def candidate_scope(request: Request, candidate_id: str) -> str:
    """Authorize a candidate-scoped read, or refuse it."""
    container = request.app.state.container
    return container.sessions.require_candidate(session_token(request), candidate_id)


def require_import_access(request: Request) -> None:
    """Guard the team-only manual import routes."""
    settings = request.app.state.settings
    allowed = settings.import_tokens
    if not allowed:
        raise Forbidden("Manual job import is not enabled on this deployment.")
    presented = _bearer(request)
    if presented is None or not any(hmac.compare_digest(presented, token) for token in allowed):
        raise Forbidden("Manual job import requires a team access token.")


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()
