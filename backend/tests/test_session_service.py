import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, AccountSession, Tenant
from app.services.password_service import PasswordService
from app.services.session_service import InvalidSessionError, SessionPersistenceError, SessionService


def create_account(db_session: Session, *, account_id: str, role: AccountRole) -> Account:
    tenant = Tenant(name=f"Tenant {account_id}", email=f"{account_id}@example.com")
    account = Account(
        tenant=tenant,
        account_id=account_id,
        name=f"{role.value} account",
        email=f"{account_id.lower()}@example.com",
        role=role,
        password_hash=PasswordService().hash_password("test-password"),
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def test_creates_a_session_and_persists_only_its_token_hash(db_session: Session):
    account = create_account(
        db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE
    )

    result = SessionService(db_session).create_session(account)
    stored_session = db_session.get(AccountSession, result.session.id)

    assert result.token
    assert stored_session.account_id == account.id
    assert stored_session.token_hash == hashlib.sha256(result.token.encode("utf-8")).hexdigest()
    assert stored_session.token_hash != result.token
    assert "token" not in AccountSession.__table__.columns
    assert stored_session.created_at is not None
    assert stored_session.expires_at is not None
    assert stored_session.revoked_at is None


def test_resolves_a_token_to_its_own_account(db_session: Session):
    first_account = create_account(
        db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE
    )
    second_account = create_account(
        db_session, account_id="AD-000001", role=AccountRole.ADMIN
    )
    service = SessionService(db_session)
    token = service.create_session(first_account).token

    resolved_account = service.get_account_for_token(token)

    assert resolved_account.id == first_account.id
    assert resolved_account.id != second_account.id


@pytest.mark.parametrize("token", ["unknown-token", "unknown-token-tampered", "' OR 1=1 --"])
def test_unknown_or_manipulated_tokens_have_one_generic_error(
    db_session: Session, token: str
):
    with pytest.raises(InvalidSessionError, match="^Invalid session$"):
        SessionService(db_session).get_account_for_token(token)

    assert db_session.scalar(select(func.count()).select_from(AccountSession)) == 0


def test_expired_session_is_invalid(db_session: Session):
    account = create_account(
        db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE
    )
    service = SessionService(db_session)
    result = service.create_session(account)
    result.session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(InvalidSessionError, match="^Invalid session$"):
        service.get_account_for_token(result.token)


def test_revoked_session_is_invalid_and_revoke_is_idempotent(db_session: Session):
    account = create_account(
        db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE
    )
    service = SessionService(db_session)
    result = service.create_session(account)

    service.revoke_session(result.token)
    db_session.refresh(result.session)
    first_revoked_at = result.session.revoked_at
    service.revoke_session(result.token)
    db_session.refresh(result.session)

    assert first_revoked_at is not None
    assert result.session.revoked_at == first_revoked_at
    with pytest.raises(InvalidSessionError, match="^Invalid session$"):
        service.get_account_for_token(result.token)


def test_resolving_a_session_loads_current_account_role(db_session: Session):
    account = create_account(
        db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE
    )
    service = SessionService(db_session)
    token = service.create_session(account).token
    account.role = AccountRole.ADMIN
    db_session.commit()

    resolved_account = service.get_account_for_token(token)

    assert resolved_account.role is AccountRole.ADMIN


def test_multiple_sessions_receive_distinct_high_entropy_tokens(db_session: Session):
    account = create_account(
        db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE
    )
    service = SessionService(db_session)

    first = service.create_session(account)
    second = service.create_session(account)

    assert first.token != second.token
    assert first.session.token_hash != second.session.token_hash


def test_revoke_all_is_account_scoped_and_idempotent(db_session: Session):
    account = create_account(db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE)
    other = create_account(db_session, account_id="EM-000002", role=AccountRole.EMPLOYEE)
    service = SessionService(db_session)
    sessions = [service.create_session(account) for _ in range(3)]
    other_session = service.create_session(other)

    service.revoke_all_sessions_for_account(account.id)
    timestamps = []
    for result in sessions:
        db_session.refresh(result.session)
        assert result.session.revoked_at is not None
        timestamps.append(result.session.revoked_at)
        with pytest.raises(InvalidSessionError):
            service.get_account_for_token(result.token)
    service.revoke_all_sessions_for_account(account.id)
    for result, timestamp in zip(sessions, timestamps):
        db_session.refresh(result.session)
        assert result.session.revoked_at == timestamp
    assert service.get_account_for_token(other_session.token).id == other.id


def test_revoke_all_without_sessions_is_a_noop(db_session: Session):
    account = create_account(db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE)
    service = SessionService(db_session)
    service.revoke_all_sessions_for_account(account.id)
    service.revoke_all_sessions_for_account(account.id)
    assert db_session.scalar(select(func.count()).select_from(AccountSession)) == 0


@pytest.mark.parametrize("failure_method", ["execute", "commit"])
def test_revoke_all_database_failure_rolls_back(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, failure_method: str
):
    account = create_account(db_session, account_id="EM-000001", role=AccountRole.EMPLOYEE)
    service = SessionService(db_session)
    sessions = [service.create_session(account) for _ in range(3)]

    account_uuid = account.id

    def fail(*args, **kwargs):
        raise SQLAlchemyError("simulated database failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_session, failure_method, fail)
        with pytest.raises(SessionPersistenceError):
            service.revoke_all_sessions_for_account(account_uuid)
    for result in sessions:
        db_session.refresh(result.session)
        assert result.session.revoked_at is None
        assert service.get_account_for_token(result.token).id == account.id
