import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies.auth import SESSION_COOKIE_NAME
from app.models import Account, AccountRole, Tenant
from app.services.password_service import PasswordService
from app.services.session_service import SessionService


def create_tenant(db_session: Session, *, name: str, email: str) -> Tenant:
    tenant = Tenant(name=name, email=email)
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
    email: str | None = None,
    password_change_required: bool = False,
) -> Account:
    account = Account(
        tenant_id=tenant.id,
        account_id=account_id,
        name=f"{role.value} actor",
        email=email,
        role=role,
        password_hash=PasswordService().hash_password("actor-password"),
        password_change_required=password_change_required,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def authenticate_client(client: TestClient, db_session: Session, account: Account) -> None:
    token = SessionService(db_session).create_session(account).token
    client.cookies.set(SESSION_COOKIE_NAME, token)


def account_count(db_session: Session) -> int:
    return db_session.scalar(select(func.count()).select_from(Account)) or 0


def test_owner_can_onboard_admin_with_one_time_temporary_password(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    owner = create_account(
        db_session,
        tenant=tenant,
        account_id="OW-000001",
        role=AccountRole.OWNER,
        email="owner@example.com",
    )
    authenticate_client(client, db_session, owner)

    response = client.post(
        "/accounts",
        json={"name": "Admin", "email": "admin@example.com", "role": "ADMIN"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Admin"
    assert payload["email"] == "admin@example.com"
    assert payload["role"] == "ADMIN"
    assert payload["password_change_required"] is True
    assert payload["temporary_password"]
    assert not {
        "id",
        "tenant_id",
        "password_hash",
        "session",
        "session_token",
    }.intersection(payload)

    created = db_session.scalar(
        select(Account).where(Account.account_id == payload["account_id"])
    )
    assert created is not None
    assert created.tenant_id == owner.tenant_id
    assert created.role is AccountRole.ADMIN
    assert PasswordService().verify_password(payload["temporary_password"], created.password_hash)


def test_owner_can_onboard_employee_without_email(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    owner = create_account(
        db_session,
        tenant=tenant,
        account_id="OW-000001",
        role=AccountRole.OWNER,
        email="owner@example.com",
    )
    authenticate_client(client, db_session, owner)

    response = client.post(
        "/accounts", json={"name": "Mitarbeiter", "role": "EMPLOYEE"}
    )

    assert response.status_code == 201
    assert response.json()["email"] is None
    assert response.json()["role"] == "EMPLOYEE"


def test_admin_can_onboard_employee_only_in_own_tenant(
    client: TestClient, db_session: Session
):
    tenant_a = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    tenant_b = create_tenant(
        db_session, name="Tenant B", email="tenant-b@example.com"
    )
    admin = create_account(
        db_session,
        tenant=tenant_a,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="admin@example.com",
    )
    authenticate_client(client, db_session, admin)

    response = client.post(
        "/accounts",
        json={"name": "Mitarbeiter", "role": "EMPLOYEE", "email": "employee@example.com"},
    )

    assert response.status_code == 201
    created = db_session.scalar(
        select(Account).where(Account.account_id == response.json()["account_id"])
    )
    assert created is not None
    assert created.tenant_id == tenant_a.id
    assert created.tenant_id != tenant_b.id


@pytest.mark.parametrize(
    ("actor_role", "target_role"),
    [
        (AccountRole.OWNER, AccountRole.OWNER),
        (AccountRole.ADMIN, AccountRole.ADMIN),
        (AccountRole.ADMIN, AccountRole.OWNER),
        (AccountRole.EMPLOYEE, AccountRole.EMPLOYEE),
        (AccountRole.EMPLOYEE, AccountRole.ADMIN),
        (AccountRole.EMPLOYEE, AccountRole.OWNER),
    ],
)
def test_forbidden_role_combinations_do_not_persist_accounts(
    client: TestClient,
    db_session: Session,
    actor_role: AccountRole,
    target_role: AccountRole,
):
    tenant = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    actor = create_account(
        db_session,
        tenant=tenant,
        account_id="OW-000001",
        role=actor_role,
        email=f"{actor_role.value.lower()}@example.com"
        if actor_role is not AccountRole.EMPLOYEE
        else None,
    )
    authenticate_client(client, db_session, actor)
    before = account_count(db_session)

    response = client.post(
        "/accounts",
        json={
            "name": "Nicht erlaubt",
            "email": "target@example.com",
            "role": target_role.value,
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Nicht berechtigt, diese Account-Rolle zu erstellen."
    }
    assert account_count(db_session) == before


def test_account_onboarding_requires_a_valid_session_cookie(client: TestClient):
    missing_cookie = client.post(
        "/accounts", json={"name": "Mitarbeiter", "role": "EMPLOYEE"}
    )
    client.cookies.set(SESSION_COOKIE_NAME, "unknown-token")
    invalid_cookie = client.post(
        "/accounts", json={"name": "Mitarbeiter", "role": "EMPLOYEE"}
    )

    for response in (missing_cookie, invalid_cookie):
        assert response.status_code == 401
        assert response.json() == {"detail": "Ungültige Sitzung."}


def test_client_cannot_choose_tenant_or_password_change_status(
    client: TestClient, db_session: Session
):
    tenant_a = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    tenant_b = create_tenant(
        db_session, name="Tenant B", email="tenant-b@example.com"
    )
    owner = create_account(
        db_session,
        tenant=tenant_a,
        account_id="OW-000001",
        role=AccountRole.OWNER,
        email="owner@example.com",
    )
    authenticate_client(client, db_session, owner)
    before = account_count(db_session)

    response = client.post(
        "/accounts",
        json={
            "name": "Eingeschleust",
            "role": "EMPLOYEE",
            "tenant_id": tenant_b.id,
            "password_change_required": False,
        },
    )

    assert response.status_code == 422
    assert account_count(db_session) == before


def test_duplicate_email_is_a_conflict_without_another_account(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    owner = create_account(
        db_session,
        tenant=tenant,
        account_id="OW-000001",
        role=AccountRole.OWNER,
        email="owner@example.com",
    )
    create_account(
        db_session,
        tenant=tenant,
        account_id="AD-000001",
        role=AccountRole.ADMIN,
        email="used@example.com",
    )
    authenticate_client(client, db_session, owner)
    before = account_count(db_session)

    response = client.post(
        "/accounts",
        json={"name": "Admin", "email": "used@example.com", "role": "ADMIN"},
    )

    assert response.status_code == 409
    assert account_count(db_session) == before


def test_required_password_change_blocks_then_releases_owner_after_new_login(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    owner = create_account(
        db_session,
        tenant=tenant,
        account_id="OW-000001",
        role=AccountRole.OWNER,
        email="owner@example.com",
        password_change_required=True,
    )
    client.base_url = "https://testserver"
    login_response = client.post(
        "/auth/login",
        json={"identifier": "OW-000001", "password": "actor-password"},
    )
    token = login_response.cookies.get(SESSION_COOKIE_NAME)
    assert login_response.status_code == 200
    assert token
    before = account_count(db_session)

    blocked = client.post(
        "/accounts", json={"name": "Mitarbeiter", "role": "EMPLOYEE"}
    )
    assert blocked.status_code == 403
    assert blocked.json() == {"detail": "Passwortänderung erforderlich."}
    assert account_count(db_session) == before

    changed = client.post(
        "/auth/change-password",
        json={
            "current_password": "actor-password",
            "new_password": "NewSecurePass2!",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["password_change_required"] is False
    assert changed.json()["login_required"] is True
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    assert client.post("/accounts", json={"name": "Mitarbeiter", "role": "EMPLOYEE"}).status_code == 401
    assert client.post(
        "/auth/login", json={"identifier": owner.account_id, "password": "NewSecurePass2!"}
    ).status_code == 200
    allowed = client.post(
        "/accounts", json={"name": "Mitarbeiter", "role": "EMPLOYEE"}
    )

    assert "max-age=0" in changed.headers["set-cookie"].lower()
    assert allowed.status_code == 201
    assert account_count(db_session) == before + 1


def test_required_password_change_and_rbac_remain_separate_for_employee(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(
        db_session, name="Tenant A", email="tenant-a@example.com"
    )
    employee = create_account(
        db_session,
        tenant=tenant,
        account_id="EM-000001",
        role=AccountRole.EMPLOYEE,
        password_change_required=True,
    )
    client.base_url = "https://testserver"
    assert client.post(
        "/auth/login", json={"identifier": employee.account_id, "password": "actor-password"}
    ).status_code == 200
    before = account_count(db_session)

    blocked = client.post(
        "/accounts", json={"name": "Ziel", "role": "EMPLOYEE"}
    )
    changed = client.post(
        "/auth/change-password",
        json={
            "current_password": "actor-password",
            "new_password": "NewSecurePass2!",
        },
    )
    assert client.post("/accounts", json={"name": "Ziel", "role": "EMPLOYEE"}).status_code == 401
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    assert client.post(
        "/auth/login", json={"identifier": employee.account_id, "password": "NewSecurePass2!"}
    ).status_code == 200
    rbac_denied = client.post(
        "/accounts", json={"name": "Ziel", "role": "EMPLOYEE"}
    )

    assert blocked.status_code == 403
    assert blocked.json() == {"detail": "Passwortänderung erforderlich."}
    assert changed.status_code == 200
    assert rbac_denied.status_code == 403
    assert rbac_denied.json() == {
        "detail": "Nicht berechtigt, diese Account-Rolle zu erstellen."
    }
    assert account_count(db_session) == before


@pytest.mark.parametrize("actor_role", [AccountRole.OWNER, AccountRole.ADMIN])
def test_account_list_is_tenant_scoped_and_contains_only_public_fields(
    client: TestClient, db_session: Session, actor_role: AccountRole
):
    tenant_a = create_tenant(db_session, name="A", email="a@example.com")
    tenant_b = create_tenant(db_session, name="B", email="b@example.com")
    accounts_a = [
        create_account(
            db_session, tenant=tenant_a, account_id=account_id,
            role=role, email=email,
        )
        for account_id, role, email in [
            ("OW-000001", AccountRole.OWNER, "owner-a@example.com"),
            ("AD-000001", AccountRole.ADMIN, "admin-a@example.com"),
            ("EM-000001", AccountRole.EMPLOYEE, None),
        ]
    ]
    for account_id, role, email in [
        ("OW-000002", AccountRole.OWNER, "owner-b@example.com"),
        ("AD-000002", AccountRole.ADMIN, "admin-b@example.com"),
    ]:
        create_account(
            db_session, tenant=tenant_b, account_id=account_id, role=role, email=email
        )
    actor = next(account for account in accounts_a if account.role is actor_role)
    authenticate_client(client, db_session, actor)

    for params in ({}, {"tenant_id": tenant_b.id}):
        response = client.get("/accounts", params=params)
        assert response.status_code == 200
        assert {row["account_id"] for row in response.json()} == {
            account.account_id for account in accounts_a
        }
        for row in response.json():
            assert set(row) == {
                "account_id", "name", "email", "role", "password_change_required"
            }
        assert "owner-b@example.com" not in response.text
        assert "admin-b@example.com" not in response.text


@pytest.mark.parametrize("token", [None, "unknown-session"])
def test_account_list_requires_valid_session(client: TestClient, token: str | None):
    if token is not None:
        client.cookies.set(SESSION_COOKIE_NAME, token)
    response = client.get("/accounts")
    assert response.status_code == 401
    assert response.json() == {"detail": "Ungültige Sitzung."}


def test_employee_cannot_read_account_administration_list(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session, name="A", email="a@example.com")
    employee = create_account(
        db_session, tenant=tenant, account_id="EM-000001", role=AccountRole.EMPLOYEE
    )
    authenticate_client(client, db_session, employee)
    response = client.get("/accounts")
    assert response.status_code == 403
    assert response.json() == {"detail": "Nicht berechtigt, die Account-Liste zu lesen."}


def test_account_list_unlocks_after_password_change_and_new_login(
    client: TestClient, db_session: Session
):
    tenant = create_tenant(db_session, name="A", email="a@example.com")
    owner = create_account(
        db_session, tenant=tenant, account_id="OW-000001", role=AccountRole.OWNER,
        email="owner@example.com", password_change_required=True,
    )
    client.base_url = "https://testserver"
    login_response = client.post(
        "/auth/login", json={"identifier": owner.account_id, "password": "actor-password"}
    )
    assert login_response.status_code == 200
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token

    blocked = client.get("/accounts")
    assert blocked.status_code == 403
    assert blocked.json() == {"detail": "Passwortänderung erforderlich."}
    changed = client.post(
        "/auth/change-password",
        json={"current_password": "actor-password", "new_password": "NewSecurePass2!"},
    )
    assert changed.status_code == 200
    assert "max-age=0" in changed.headers["set-cookie"].lower()
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    assert client.get("/accounts").status_code == 401
    assert client.get("/accounts", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"}).status_code == 401
    assert client.post(
        "/auth/login", json={"identifier": owner.account_id, "password": "NewSecurePass2!"}
    ).status_code == 200
    assert client.cookies.get(SESSION_COOKIE_NAME) != token
    allowed = client.get("/accounts")
    assert allowed.status_code == 200
    assert [row["account_id"] for row in allowed.json()] == [owner.account_id]
    assert allowed.json()[0]["password_change_required"] is False
