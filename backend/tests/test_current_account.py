from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies.auth import (
    SESSION_COOKIE_NAME,
    get_current_account,
    session_cookie_settings,
)
from app.main import app
from app.models import Account, AccountRole, Tenant
from app.services.password_service import PasswordService
from app.services.session_service import SessionService


@app.get("/_test/current-account")
def current_account_for_test(
    current_account: Account = Depends(get_current_account),
):
    """Test-only route; production routers do not expose current-account data."""

    return {
        "account_id": current_account.account_id,
        "role": current_account.role.value,
        "tenant_id": current_account.tenant_id,
        "password_change_required": current_account.password_change_required,
        "name": current_account.name,
    }


def create_account(db_session: Session, *, account_id: str) -> Account:
    tenant = Tenant(name="Holzwerk", email=f"tenant-{account_id}@example.com")
    account = Account(
        tenant=tenant,
        account_id=account_id,
        name="Mitarbeiter",
        email=f"{account_id.lower()}@example.com",
        role=AccountRole.EMPLOYEE,
        password_hash=PasswordService().hash_password("test-password"),
        password_change_required=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def request_current_account(client: TestClient, token: str | None = None):
    if token is not None:
        client.cookies.set(SESSION_COOKIE_NAME, token)
    return client.get("/_test/current-account")


def assert_generic_session_401(response) -> None:
    assert response.status_code == 401
    assert response.json() == {"detail": "Ungültige Sitzung."}


def test_current_account_resolves_a_valid_cookie_to_current_account(
    client: TestClient, db_session: Session
):
    account = create_account(db_session, account_id="EM-000001")
    token = SessionService(db_session).create_session(account).token

    response = request_current_account(client, token)

    assert response.status_code == 200
    assert response.json()["account_id"] == account.account_id
    assert response.json()["tenant_id"] == account.tenant_id
    assert response.json()["password_change_required"] is True


@pytest.mark.parametrize("token", [None, "unknown-token", "unknown-token-tampered"])
def test_missing_or_invalid_cookie_uses_one_generic_401(
    client: TestClient, token: str | None
):
    assert_generic_session_401(request_current_account(client, token))


def test_expired_and_revoked_cookies_are_rejected_generically(
    client: TestClient, db_session: Session
):
    account = create_account(db_session, account_id="EM-000001")
    service = SessionService(db_session)
    expired = service.create_session(account)
    expired.session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    revoked = service.create_session(account)
    service.revoke_session(revoked.token)

    assert_generic_session_401(request_current_account(client, expired.token))
    assert_generic_session_401(request_current_account(client, revoked.token))


def test_current_account_loads_current_data_and_uses_account_tenant(
    client: TestClient, db_session: Session
):
    account = create_account(db_session, account_id="EM-000001")
    token = SessionService(db_session).create_session(account).token
    account.name = "Aktualisiert"
    account.role = AccountRole.ADMIN
    db_session.commit()

    response = request_current_account(client, token)

    assert response.status_code == 200
    assert response.json()["name"] == "Aktualisiert"
    assert response.json()["role"] == "ADMIN"
    assert response.json()["tenant_id"] == account.tenant_id


def test_cookie_security_changes_only_with_the_debug_configuration():
    development = session_cookie_settings(debug=True)
    production = session_cookie_settings(debug=False)

    assert development["secure"] is False
    assert production["secure"] is True
    assert development["httponly"] is True
    assert development["samesite"] == "lax"
    assert development["path"] == "/"
    assert development["max_age"] == 8 * 60 * 60
