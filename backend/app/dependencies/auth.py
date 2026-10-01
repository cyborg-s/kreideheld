"""HTTP dependencies and cookie settings for server-side account sessions.

Cookie credentials are sent automatically by browsers. ``SameSite=Lax`` reduces
cross-site exposure but does not replace CSRF protection for state-changing
requests; a dedicated CSRF design is required before production use.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Account
from app.services.session_service import (
    SESSION_LIFETIME,
    InvalidSessionError,
    SessionService,
)


SESSION_COOKIE_NAME = "kreideheld_session"


def session_cookie_settings(*, debug: bool | None = None) -> dict[str, object]:
    """Return centralized cookie attributes without placing identity data in it."""

    is_debug = settings.debug if debug is None else debug
    return {
        "httponly": True,
        "secure": not is_debug,
        "samesite": "lax",
        "path": "/",
        "max_age": int(SESSION_LIFETIME.total_seconds()),
    }


def get_current_account(
    request: Request, db: Session = Depends(get_db)
) -> Account:
    """Resolve a valid session cookie to the current account without RBAC checks."""

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise _invalid_session_http_error()

    try:
        return SessionService(db).get_account_for_token(token)
    except InvalidSessionError as error:
        raise _invalid_session_http_error() from error


def require_password_change_completed(
    current_account: Account = Depends(get_current_account),
) -> Account:
    """Allow normal protected actions only after a required password change."""

    if current_account.password_change_required:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Passwortänderung erforderlich.",
        )
    return current_account


def _invalid_session_http_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültige Sitzung.",
    )
