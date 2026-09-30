import pytest
from argon2 import PasswordHasher, Type
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Tenant
from app.services.account_authentication_service import (
    AccountAuthenticationService,
    InvalidCredentialsError,
)
from app.services.password_service import PasswordService


def create_tenant(db_session: Session) -> Tenant:
    tenant = Tenant(name="Holzwerk", email="holzwerk@example.com")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def create_account(
    db_session: Session,
    *,
    tenant: Tenant,
    account_id: str,
    role: AccountRole,
    password: str,
    email: str | None = None,
    password_change_required: bool = True,
    password_hash: str | None = None,
) -> Account:
    account = Account(
        tenant_id=tenant.id,
        account_id=account_id,
        name=f"{role.value} account",
        email=email,
        role=role,
        password_hash=password_hash or PasswordService().hash_password(password),
        password_change_required=password_change_required,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def test_authenticates_employee_by_account_id(db_session: Session):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="EM-000001",
        role=AccountRole.EMPLOYEE,
        password="employee-password",
    )

    authenticated = AccountAuthenticationService(db_session).authenticate(
        identifier="EM-000001", password="employee-password"
    )

    assert authenticated.id == account.id
    assert authenticated.tenant_id == tenant.id


def test_authenticates_admin_by_account_id(db_session: Session):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    authenticated = AccountAuthenticationService(db_session).authenticate(
        identifier="AD-000001", password="admin-password"
    )

    assert authenticated.id == account.id


def test_authenticates_admin_by_email(db_session: Session):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    authenticated = AccountAuthenticationService(db_session).authenticate(
        identifier="admin@example.com", password="admin-password"
    )

    assert authenticated.id == account.id


def test_authenticates_owner_by_account_id_and_email(db_session: Session):
    """OWNER setup is direct because onboarding intentionally forbids OWNER."""

    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="OW-000001",
        role=AccountRole.OWNER,
        email="owner@example.com",
        password="owner-password",
    )
    service = AccountAuthenticationService(db_session)

    by_account_id = service.authenticate(
        identifier="OW-000001", password="owner-password"
    )
    by_email = service.authenticate(
        identifier="owner@example.com", password="owner-password"
    )

    assert by_account_id.id == account.id
    assert by_email.id == account.id


def test_rejects_employee_email_login_with_the_generic_error(db_session: Session):
    tenant = create_tenant(db_session)
    create_account(
        db_session,
        tenant=tenant,
        account_id="EM-000001",
        role=AccountRole.EMPLOYEE,
        email="employee@example.com",
        password="employee-password",
    )

    with pytest.raises(InvalidCredentialsError, match="^Invalid credentials$"):
        AccountAuthenticationService(db_session).authenticate(
            identifier="employee@example.com", password="employee-password"
        )


@pytest.mark.parametrize(
    ("identifier", "password"),
    [
        ("ZZ-999999", "any-password"),
        ("missing@example.com", "any-password"),
        ("AD-000001", "wrong-password"),
        ("AD-000001", ""),
        ("' OR 1=1 --", "any-password"),
    ],
)
def test_credential_failures_share_the_same_generic_error(
    db_session: Session, identifier: str, password: str
):
    """Unknown IDs/emails, bad passwords, empty passwords, and syntax-like input leak no cause."""

    tenant = create_tenant(db_session)
    create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    with pytest.raises(InvalidCredentialsError, match="^Invalid credentials$"):
        AccountAuthenticationService(db_session).authenticate(
            identifier=identifier, password=password
        )


@pytest.mark.parametrize("password_change_required", [True, False])
def test_authentication_preserves_password_change_state(
    db_session: Session, password_change_required: bool
):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
        password_change_required=password_change_required,
    )

    authenticated = AccountAuthenticationService(db_session).authenticate(
        identifier="AD-000001", password="admin-password"
    )

    assert authenticated.id == account.id
    assert authenticated.password_change_required is password_change_required


def test_rehashes_an_authenticated_legacy_hash(db_session: Session):
    tenant = create_tenant(db_session)
    password = "legacy-password"
    legacy_hasher = PasswordHasher(
        time_cost=2,
        memory_cost=32 * 1024,
        parallelism=2,
        hash_len=16,
        salt_len=16,
        type=Type.ID,
    )
    legacy_hash = legacy_hasher.hash(password)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password=password,
        password_hash=legacy_hash,
    )
    password_service = PasswordService()

    assert password_service.needs_rehash(account.password_hash) is True

    authenticated = AccountAuthenticationService(db_session).authenticate(
        identifier="AD-000001", password=password
    )
    db_session.refresh(account)

    assert authenticated.id == account.id
    assert account.password_hash != legacy_hash
    assert password_service.verify_password(password, account.password_hash) is True
    assert password_service.needs_rehash(account.password_hash) is False


def test_does_not_rehash_after_a_failed_verification(db_session: Session):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="correct-password",
    )
    original_hash = account.password_hash

    with pytest.raises(InvalidCredentialsError):
        AccountAuthenticationService(db_session).authenticate(
            identifier="AD-000001", password=" wrong-password "
        )

    db_session.refresh(account)
    assert account.password_hash == original_hash
