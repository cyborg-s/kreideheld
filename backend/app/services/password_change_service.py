"""Internal password changes for already authenticated accounts."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Account
from app.services.password_policy import PasswordValidationResult, validate_password
from app.services.password_service import PasswordService
from app.services.session_service import SessionPersistenceError, SessionService


class PasswordChangeError(Exception):
    """Base class for controlled password-change failures."""


class InvalidCurrentPasswordError(PasswordChangeError):
    """Raised when the supplied current password cannot verify the account hash."""


class InvalidNewPasswordError(PasswordChangeError):
    """Raised when the new password does not satisfy the existing policy."""

    def __init__(self, validation_result: PasswordValidationResult) -> None:
        super().__init__("The new password does not satisfy the password policy")
        self.validation_result = validation_result


class PasswordUnchangedError(PasswordChangeError):
    """Raised when a password change would retain the current password."""


class PasswordChangePersistenceError(PasswordChangeError):
    """Raised when a password change cannot be committed atomically."""


class PasswordChangeService:
    """Verify, validate, hash, and persist a password change without HTTP concerns.

    A password change is distinct from authentication-time rehashing: it always
    hashes a user-selected new password with the current PasswordService settings.
    """

    def __init__(
        self, db: Session, *, password_service: PasswordService | None = None
    ) -> None:
        self._db = db
        self._password_service = password_service or PasswordService()

    def change_password(
        self, *, account: Account, current_password: str, new_password: str
    ) -> Account:
        """Atomically replace credentials, clear the requirement, and revoke sessions."""

        if not self._password_service.verify_password(
            current_password, account.password_hash
        ):
            raise InvalidCurrentPasswordError("The current password is invalid")

        validation_result = validate_password(new_password)
        if not validation_result.is_valid:
            raise InvalidNewPasswordError(validation_result)

        if new_password == current_password:
            raise PasswordUnchangedError("The new password must differ from the current password")

        account.password_hash = self._password_service.hash_password(new_password)
        account.password_change_required = False
        try:
            SessionService(self._db).revoke_all_sessions_for_account(account.id, commit=False)
            self._db.commit()
        except (SQLAlchemyError, SessionPersistenceError) as error:
            self._db.rollback()
            raise PasswordChangePersistenceError(
                "The password change could not be persisted"
            ) from error
        self._db.refresh(account)
        return account
