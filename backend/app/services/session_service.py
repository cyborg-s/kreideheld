"""Server-side session persistence without HTTP cookie integration."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Account, AccountSession


SESSION_LIFETIME = timedelta(hours=8)
SESSION_TOKEN_BYTES = 32


class SessionServiceError(Exception):
    """Base class for controlled session-service failures."""


class InvalidSessionError(SessionServiceError):
    """Raised for unknown, expired, revoked, or otherwise unusable sessions."""


class SessionPersistenceError(SessionServiceError):
    """Raised when a session change cannot be persisted atomically."""


@dataclass(frozen=True)
class SessionCreationResult:
    """The persisted session and its one-time plaintext token."""

    session: AccountSession
    token: str


class SessionService:
    """Create, resolve, and revoke server-side sessions for existing accounts."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_session(self, account: Account) -> SessionCreationResult:
        """Persist a token hash and return the plaintext token exactly once."""

        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        now = _utc_now()
        session = AccountSession(
            account_id=account.id,
            token_hash=_hash_token(token),
            created_at=now,
            expires_at=now + SESSION_LIFETIME,
        )
        self._db.add(session)
        try:
            self._db.commit()
        except SQLAlchemyError as error:
            self._db.rollback()
            raise SessionPersistenceError("The session could not be persisted") from error
        self._db.refresh(session)
        return SessionCreationResult(session=session, token=token)

    def get_account_for_token(self, token: str) -> Account:
        """Resolve a non-revoked, non-expired token to the current account record."""

        session = self._find_session(token)
        if session is None or session.revoked_at is not None or _is_expired(session.expires_at):
            raise InvalidSessionError("Invalid session")

        account = self._db.get(Account, session.account_id, populate_existing=True)
        if account is None:
            raise InvalidSessionError("Invalid session")
        return account

    def revoke_session(self, token: str) -> None:
        """Revoke a known session; unknown and already-revoked tokens are no-ops."""

        session = self._find_session(token)
        if session is None or session.revoked_at is not None:
            return

        session.revoked_at = _utc_now()
        try:
            self._db.commit()
        except SQLAlchemyError as error:
            self._db.rollback()
            raise SessionPersistenceError("The session could not be revoked") from error

    def revoke_all_sessions_for_account(
        self, account_id: str, *, commit: bool = True
    ) -> None:
        """Revoke all sessions by internal account UUID.

        With commit=False the caller owns the transaction and must commit or
        roll back both this update and its other changes together.
        """

        try:
            self._db.execute(
                update(AccountSession)
                .where(
                    AccountSession.account_id == account_id,
                    AccountSession.revoked_at.is_(None),
                )
                .values(revoked_at=_utc_now())
                .execution_options(synchronize_session="fetch")
            )
            if commit:
                self._db.commit()
        except SQLAlchemyError as error:
            self._db.rollback()
            raise SessionPersistenceError("The account sessions could not be revoked") from error

    def _find_session(self, token: str) -> AccountSession | None:
        if not isinstance(token, str):
            return None
        return self._db.scalar(
            select(AccountSession).where(AccountSession.token_hash == _hash_token(token))
        )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _utc_now()
