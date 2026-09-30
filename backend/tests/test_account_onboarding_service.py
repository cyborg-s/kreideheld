import re

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Tenant
from app.services.account_onboarding_service import (
    AccountOnboardingService,
    EmailAlreadyInUseError,
    InvalidAccountDataError,
    TenantNotFoundError,
    UnsupportedTargetRoleError,
)
from app.services.password_service import PasswordService


def create_tenant(db_session: Session, *, name: str = "Holzwerk") -> Tenant:
    tenant = Tenant(name=name, email=f"{name.lower()}@example.com")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def account_count(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Account)) or 0


def test_onboards_employee_without_email_for_the_explicit_tenant(db_session: Session):
    """Employees may omit an email, but the caller-selected tenant is retained."""

    first_tenant = create_tenant(db_session, name="First")
    target_tenant = create_tenant(db_session, name="Target")

    result = AccountOnboardingService(db_session).onboard(
        tenant_id=target_tenant.id,
        name="Mitarbeiterin",
        role=AccountRole.EMPLOYEE,
    )

    assert result.account.tenant_id == target_tenant.id
    assert result.account.tenant_id != first_tenant.id
    assert result.account.role is AccountRole.EMPLOYEE
    assert result.account.email is None
    assert result.account.password_change_required is True
    assert re.fullmatch(r"[A-Z]{2}-\d{6}", result.account.account_id)
    assert result.account.password_hash


def test_onboards_employee_with_email(db_session: Session):
    tenant = create_tenant(db_session)

    result = AccountOnboardingService(db_session).onboard(
        tenant_id=tenant.id,
        name="Mitarbeiter",
        role=AccountRole.EMPLOYEE,
        email="employee@example.com",
    )

    assert result.account.email == "employee@example.com"


def test_onboards_admin_with_email(db_session: Session):
    tenant = create_tenant(db_session)

    result = AccountOnboardingService(db_session).onboard(
        tenant_id=tenant.id,
        name="Administration",
        role=AccountRole.ADMIN,
        email="admin@example.com",
    )

    assert result.account.role is AccountRole.ADMIN
    assert result.account.email == "admin@example.com"


def test_rejects_admin_without_email_without_persisting_an_account(db_session: Session):
    tenant = create_tenant(db_session)

    with pytest.raises(InvalidAccountDataError):
        AccountOnboardingService(db_session).onboard(
            tenant_id=tenant.id,
            name="Administration",
            role=AccountRole.ADMIN,
        )

    assert account_count(db_session) == 0


def test_rejects_owner_without_persisting_an_account(db_session: Session):
    tenant = create_tenant(db_session)

    with pytest.raises(UnsupportedTargetRoleError):
        AccountOnboardingService(db_session).onboard(
            tenant_id=tenant.id,
            name="Eigentümer",
            role=AccountRole.OWNER,
            email="owner@example.com",
        )

    assert account_count(db_session) == 0


def test_rejects_unknown_tenant_without_persisting_an_account(db_session: Session):
    with pytest.raises(TenantNotFoundError):
        AccountOnboardingService(db_session).onboard(
            tenant_id="missing-tenant",
            name="Mitarbeiter",
            role=AccountRole.EMPLOYEE,
        )

    assert account_count(db_session) == 0


def test_hashes_the_initial_password_without_persisting_plaintext(db_session: Session):
    tenant = create_tenant(db_session)

    result = AccountOnboardingService(db_session).onboard(
        tenant_id=tenant.id,
        name="Mitarbeiter",
        role=AccountRole.EMPLOYEE,
    )
    persisted_account = db_session.get(Account, result.account.id)

    assert PasswordService().verify_password(
        result.temporary_password, result.account.password_hash
    )
    assert result.account.password_hash != result.temporary_password
    assert "temporary_password" not in Account.__table__.columns
    assert not hasattr(persisted_account, "temporary_password")


def test_retries_a_database_confirmed_account_id_collision(db_session: Session):
    tenant = create_tenant(db_session)

    AccountOnboardingService(
        db_session, account_id_generator=lambda: "AB-000001"
    ).onboard(
        tenant_id=tenant.id,
        name="Existing",
        role=AccountRole.EMPLOYEE,
    )
    generated_ids = iter(("AB-000001", "CD-000002"))

    result = AccountOnboardingService(
        db_session, account_id_generator=lambda: next(generated_ids)
    ).onboard(
        tenant_id=tenant.id,
        name="Retried",
        role=AccountRole.EMPLOYEE,
    )

    assert result.account.account_id == "CD-000002"
    assert account_count(db_session) == 2


def test_rejects_a_duplicate_email_and_preserves_the_existing_account(db_session: Session):
    tenant = create_tenant(db_session)
    service = AccountOnboardingService(db_session)
    first_result = service.onboard(
        tenant_id=tenant.id,
        name="First",
        role=AccountRole.EMPLOYEE,
        email="duplicate@example.com",
    )

    with pytest.raises(EmailAlreadyInUseError):
        service.onboard(
            tenant_id=tenant.id,
            name="Second",
            role=AccountRole.EMPLOYEE,
            email="duplicate@example.com",
        )

    assert account_count(db_session) == 1
    assert db_session.get(Account, first_result.account.id).name == "First"


def test_persists_unusual_name_characters_as_data(db_session: Session):
    """Bound SQLAlchemy parameters preserve syntax-like characters as plain data."""

    tenant = create_tenant(db_session)
    unusual_name = "O'Connor; --"

    result = AccountOnboardingService(db_session).onboard(
        tenant_id=tenant.id,
        name=unusual_name,
        role=AccountRole.EMPLOYEE,
    )

    persisted = db_session.scalar(select(Account).where(Account.id == result.account.id))
    assert persisted.name == unusual_name


def test_two_accounts_receive_distinct_database_enforced_account_ids(db_session: Session):
    tenant = create_tenant(db_session)
    service = AccountOnboardingService(db_session)

    first_result = service.onboard(
        tenant_id=tenant.id,
        name="First",
        role=AccountRole.EMPLOYEE,
    )
    second_result = service.onboard(
        tenant_id=tenant.id,
        name="Second",
        role=AccountRole.EMPLOYEE,
    )

    assert first_result.account.account_id != second_result.account.account_id
