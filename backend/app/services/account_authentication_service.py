"""Internal authentication of existing accounts without HTTP or session concerns."""

import re

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Account, AccountRole
from app.services.password_service import PasswordService


ACCOUNT_ID_PATTERN = re.compile(r"^[A-Z]{2}-\d{6}$")
_TIMING_HARDENING_HASH = PasswordService().hash_password("not-an-account-credential")


class AccountAuthenticationError(Exception):
    """Base class for controlled authentication failures."""


class InvalidCredentialsError(AccountAuthenticationError):
    """Raised for every public credential failure without revealing its cause."""


class AuthenticationPersistenceError(AccountAuthenticationError):
    """Raised when a successful authentication cannot persist a required rehash."""


class AccountAuthenticationService:
    """Authenticate by account ID or role-appropriate email address.

    This service proves identity only. It does not create a session, authorize an
    action, or accept a tenant or role from a client.
    """

    def __init__(
        self, db: Session, *, password_service: PasswordService | None = None
    ) -> None:
        self._db = db
        self._password_service = password_service or PasswordService()

    def authenticate(self, *, identifier: str, password: str) -> Account:
        """Return the authenticated account or raise a generic credential error.

        Identifiers are deliberately matched exactly: generated account IDs use
        uppercase, and no project-wide email normalization rule exists. Passwords
        are never stripped or normalized before verification.
        """

        if not isinstance(identifier, str) or not isinstance(password, str):
            raise InvalidCredentialsError("Invalid credentials")

        is_account_id = ACCOUNT_ID_PATTERN.fullmatch(identifier) is not None
        account = self._find_account(identifier=identifier, is_account_id=is_account_id)
        if account is None:
            self._password_service.verify_password(password, _TIMING_HARDENING_HASH)
            raise InvalidCredentialsError("Invalid credentials")

        if not is_account_id and account.role is AccountRole.EMPLOYEE:
            self._password_service.verify_password(password, account.password_hash)
            raise InvalidCredentialsError("Invalid credentials")

        if not self._password_service.verify_password(password, account.password_hash):
            raise InvalidCredentialsError("Invalid credentials")

        self._rehash_after_successful_verification(account=account, password=password)
        return account

    def _find_account(self, *, identifier: str, is_account_id: bool) -> Account | None:
        if is_account_id:
            statement = select(Account).where(Account.account_id == identifier)
        else:
            statement = select(Account).where(Account.email == identifier)
        return self._db.scalar(statement)

    def _rehash_after_successful_verification(self, *, account: Account, password: str) -> None:
        if not self._password_service.needs_rehash(account.password_hash):
            return

        account.password_hash = self._password_service.hash_password(password)
        try:
            self._db.commit()
        except SQLAlchemyError as error:
            self._db.rollback()
            raise AuthenticationPersistenceError(
                "The authenticated account could not be updated"
            ) from error
        self._db.refresh(account)
