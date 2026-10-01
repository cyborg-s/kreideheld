import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies.auth import SESSION_COOKIE_NAME
from app.models import Account, AccountRole, AccountSession, Tenant
from app.services.password_service import PasswordService
from app.services.session_service import InvalidSessionError, SessionService


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
) -> Account:
    account = Account(
        tenant_id=tenant.id,
        account_id=account_id,
        name=f"{role.value} account",
        email=email,
        role=role,
        password_hash=PasswordService().hash_password(password),
        password_change_required=password_change_required,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def login(client: TestClient, *, identifier: str, password: str):
    return client.post(
        "/auth/login", json={"identifier": identifier, "password": password}
    )


def assert_minimal_login_response(response, account: Account) -> None:
    assert response.status_code == 200
    assert response.json() == {
        "account_id": account.account_id,
        "role": account.role.value,
        "password_change_required": account.password_change_required,
    }
    assert not {"password_hash", "password", "tenant_id", "id", "email"}.intersection(
        response.json()
    )
    set_cookie = response.headers["set-cookie"].lower()
    assert f"{SESSION_COOKIE_NAME}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/" in set_cookie
    assert "max-age=28800" in set_cookie
    assert "secure" in set_cookie


def test_employee_can_log_in_with_account_id_and_gets_a_minimal_response(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="EM-000001",
        role=AccountRole.EMPLOYEE,
        password="employee-password",
    )

    response = login(client, identifier="EM-000001", password="employee-password")

    assert_minimal_login_response(response, account)


def test_admin_can_log_in_with_account_id_and_email(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    by_account_id = login(client, identifier="AD-000001", password="admin-password")
    by_email = login(client, identifier="admin@example.com", password="admin-password")

    assert_minimal_login_response(by_account_id, account)
    assert_minimal_login_response(by_email, account)


def test_owner_can_log_in_with_account_id_and_email(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="OW-000001",
        role=AccountRole.OWNER,
        email="owner@example.com",
        password="owner-password",
    )

    by_account_id = login(client, identifier="OW-000001", password="owner-password")
    by_email = login(client, identifier="owner@example.com", password="owner-password")

    assert_minimal_login_response(by_account_id, account)
    assert_minimal_login_response(by_email, account)


def test_employee_email_login_uses_the_same_generic_401_as_other_failures(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    create_account(
        db_session,
        tenant=tenant,
        account_id="EM-000001",
        role=AccountRole.EMPLOYEE,
        email="employee@example.com",
        password="employee-password",
    )

    employee_email_response = login(
        client, identifier="employee@example.com", password="employee-password"
    )
    wrong_password_response = login(
        client, identifier="EM-000001", password="wrong-password"
    )
    unknown_identifier_response = login(
        client, identifier="ZZ-999999", password="any-password"
    )

    for response in (
        employee_email_response,
        wrong_password_response,
        unknown_identifier_response,
    ):
        assert response.status_code == 401
        assert response.json() == {"detail": "Ungültige Anmeldedaten."}


@pytest.mark.parametrize(
    ("identifier", "password"),
    [
        ("AD-000001", ""),
        ("' OR 1=1 --", "any-password"),
    ],
)
def test_invalid_login_inputs_are_generic_401_and_cannot_change_data(
    client: TestClient, db_session: Session, identifier: str, password: str
):
    tenant = create_tenant(db_session)
    create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    response = login(client, identifier=identifier, password=password)

    assert response.status_code == 401
    assert response.json() == {"detail": "Ungültige Anmeldedaten."}
    assert db_session.scalar(select(func.count()).select_from(Account)) == 1


def test_login_returns_password_change_state_false(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
        password_change_required=False,
    )

    response = login(client, identifier="AD-000001", password="admin-password")

    assert_minimal_login_response(response, account)


def test_login_persists_only_a_hash_of_the_cookie_token(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    response = login(client, identifier="AD-000001", password="admin-password")
    token = response.cookies.get(SESSION_COOKIE_NAME)
    stored_session = db_session.scalar(select(AccountSession))

    assert token
    assert token not in response.text
    assert stored_session.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert stored_session.token_hash != token


def test_failed_login_creates_neither_cookie_nor_session(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    response = login(client, identifier="AD-000001", password="wrong-password")

    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert db_session.scalar(select(func.count()).select_from(AccountSession)) == 0


def test_login_rejects_role_and_tenant_request_fields(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
        password="admin-password",
    )

    response = client.post(
        "/auth/login",
        json={
            "identifier": "AD-000001",
            "password": "admin-password",
            "role": "OWNER",
            "tenant_id": "client-controlled",
            "login_type": "email",
        },
    )

    assert response.status_code == 422


def assert_deleted_session_cookie(response) -> None:
    assert response.status_code == 204
    assert response.content == b""
    cookie = response.headers["set-cookie"].lower()
    for attribute in (f"{SESSION_COOKIE_NAME}=", "max-age=0", "path=/", "httponly", "secure", "samesite=lax"):
        assert attribute in cookie


def test_logout_revokes_only_current_session_and_is_repeatable(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session)
    owner = create_account(
        db_session, tenant=tenant, account_id="OW-000001", role=AccountRole.OWNER,
        email="owner@example.com", password="InitialPass1!",
    )
    other = create_account(
        db_session, tenant=tenant, account_id="EM-000001", role=AccountRole.EMPLOYEE,
        password="OtherSecure1!",
    )
    service = SessionService(db_session)
    second_token = service.create_session(owner).token
    other_token = service.create_session(other).token
    client.base_url = "https://testserver"
    assert login(client, identifier=owner.account_id, password="InitialPass1!").status_code == 200
    token = client.cookies.get(SESSION_COOKIE_NAME)

    response = client.post("/auth/logout")
    assert_deleted_session_cookie(response)
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    with pytest.raises(InvalidSessionError):
        service.get_account_for_token(token)
    assert service.get_account_for_token(second_token).id == owner.id
    assert service.get_account_for_token(other_token).id == other.id
    assert client.get("/accounts").status_code == 401
    assert client.get("/accounts", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"}).status_code == 401
    assert_deleted_session_cookie(client.post("/auth/logout"))
    assert_deleted_session_cookie(client.post("/auth/logout", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"}))


@pytest.mark.parametrize("token", [None, "unknown-token", "' OR 1=1 --"])
def test_logout_without_valid_session_is_idempotent(client: TestClient, token: str | None):
    client.base_url = "https://testserver"
    if token is not None:
        client.cookies.set(SESSION_COOKIE_NAME, token, domain="testserver.local", path="/")
    assert_deleted_session_cookie(client.post("/auth/logout"))
    assert client.cookies.get(SESSION_COOKIE_NAME) is None


def test_logout_commit_failure_is_not_reported_as_success(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    tenant = create_tenant(db_session)
    account = create_account(
        db_session, tenant=tenant, account_id="EM-000001", role=AccountRole.EMPLOYEE,
        password="InitialPass1!",
    )
    client.base_url = "https://testserver"
    login(client, identifier=account.account_id, password="InitialPass1!")
    token = client.cookies.get(SESSION_COOKIE_NAME)

    def fail(self):
        raise SQLAlchemyError("simulated commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail)
        response = client.post("/auth/logout")
    assert response.status_code == 500
    assert response.json() == {"detail": "Abmeldung derzeit nicht möglich."}
    assert "set-cookie" not in response.headers
    assert client.cookies.get(SESSION_COOKIE_NAME) == token
    assert SessionService(db_session).get_account_for_token(token).id == account.id
