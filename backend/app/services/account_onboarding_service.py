"""Internal onboarding of ADMIN and EMPLOYEE accounts.

The caller supplies ``tenant_id`` from trusted backend context. It must never be
accepted as a client-controlled HTTP field; later it will come from
``current_account.tenant_id`` after authentication and authorization exist.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Tenant, generate_account_id
from app.services.password_service import PasswordService
from app.services.temporary_password_generator import generate_temporary_password


class AccountOnboardingError(Exception):
    """Base class for controlled onboarding failures."""


class TenantNotFoundError(AccountOnboardingError):
    """Raised when the internally supplied tenant does not exist."""


class UnsupportedTargetRoleError(AccountOnboardingError):
    """Raised when onboarding is requested for a role other than ADMIN/EMPLOYEE."""


class InvalidAccountDataError(AccountOnboardingError):
    """Raised when required account data is missing or unusable."""


class EmailAlreadyInUseError(AccountOnboardingError):
    """Raised when the globally unique account email is already assigned."""


class AccountPersistenceError(AccountOnboardingError):
    """Raised when persistence fails for a reason other than a retryable ID collision."""


class AccountIdGenerationError(AccountOnboardingError):
    """Raised after the bounded retry budget for account-ID collisions is exhausted."""


@dataclass(frozen=True)
class AccountOnboardingResult:
    """The persisted account and its one-time plaintext initial password."""

    account: Account
    temporary_password: str


class AccountOnboardingService:
    """Create ADMIN or EMPLOYEE accounts for a trusted, existing tenant.

    This validates only the target role and input data. It deliberately does not
    authorize a creator: that later requires a trusted authenticated account and
    the OWNER/ADMIN role matrix.
    """

    _MAX_ACCOUNT_ID_ATTEMPTS = 5

    def __init__(
        self,
        db: Session,
        *,
        account_id_generator: Callable[[], str] = generate_account_id,
        password_service: PasswordService | None = None,
    ) -> None:
        self._db = db
        self._account_id_generator = account_id_generator
        self._password_service = password_service or PasswordService()

    def onboard(
        self,
        *,
        tenant_id: str,
        name: str,
        role: AccountRole,
        email: str | None = None,
    ) -> AccountOnboardingResult:
        """Persist an account and return its plaintext password exactly once."""

        self._validate_target_role(role)
        self._validate_account_data(name=name, role=role, email=email)

        if self._db.get(Tenant, tenant_id) is None:
            raise TenantNotFoundError("The supplied tenant does not exist")

        if email is not None and self._email_exists(email):
            raise EmailAlreadyInUseError("The email address is already in use")

        temporary_password = generate_temporary_password()
        password_hash = self._password_service.hash_password(temporary_password)

        for _ in range(self._MAX_ACCOUNT_ID_ATTEMPTS):
            account = Account(
                tenant_id=tenant_id,
                account_id=self._account_id_generator(),
                name=name,
                email=email,
                role=role,
                password_hash=password_hash,
                password_change_required=True,
            )
            self._db.add(account)
            try:
                self._db.commit()
            except IntegrityError as error:
                self._db.rollback()
                if self._is_account_id_collision(error):
                    continue
                if self._is_email_collision(error):
                    raise EmailAlreadyInUseError(
                        "The email address is already in use"
                    ) from error
                raise AccountPersistenceError("The account could not be persisted") from error

            self._db.refresh(account)
            return AccountOnboardingResult(
                account=account,
                temporary_password=temporary_password,
            )

        raise AccountIdGenerationError("Could not generate a unique account ID")

    @staticmethod
    def _validate_target_role(role: AccountRole) -> None:
        if role not in {AccountRole.ADMIN, AccountRole.EMPLOYEE}:
            raise UnsupportedTargetRoleError("Only ADMIN and EMPLOYEE can be onboarded")

    @staticmethod
    def _validate_account_data(
        *, name: str, role: AccountRole, email: str | None
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise InvalidAccountDataError("A non-empty name is required")
        if email is not None and (not isinstance(email, str) or not email.strip()):
            raise InvalidAccountDataError("An email address cannot be empty")
        if role is AccountRole.ADMIN and email is None:
            raise InvalidAccountDataError("ADMIN accounts require an email address")

    def _email_exists(self, email: str) -> bool:
        return self._db.scalar(select(Account.id).where(Account.email == email)) is not None

    @staticmethod
    def _is_account_id_collision(error: IntegrityError) -> bool:
        return "accounts.account_id" in str(error.orig).lower()

    @staticmethod
    def _is_email_collision(error: IntegrityError) -> bool:
        return "accounts.email" in str(error.orig).lower()
