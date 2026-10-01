import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.dependencies.auth import SESSION_COOKIE_NAME
from app.models import Account, AccountRole, Tenant
from app.services.password_service import PasswordService
from app.services.session_service import InvalidSessionError, SessionService


SUCCESS_RESPONSE = {
    "password_change_required": False,
    "login_required": True,
    "message": "Passwort erfolgreich geändert. Erneute Anmeldung erforderlich.",
}


def create_account(
    db_session: Session, *, password: str, password_change_required: bool
) -> Account:
    tenant = Tenant(name="Holzwerk", email="holzwerk@example.com")
    account = Account(
        tenant=tenant,
        account_id="EM-000001",
        name="Mitarbeiter",
        role=AccountRole.EMPLOYEE,
        password_hash=PasswordService().hash_password(password),
        password_change_required=password_change_required,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def authenticate_client(client: TestClient, db_session: Session, account: Account) -> str:
    client.base_url = "https://testserver"
    token = SessionService(db_session).create_session(account).token
    client.cookies.set(SESSION_COOKIE_NAME, token, domain="testserver.local", path="/")
    return token


def change_password(client: TestClient, *, current_password: str, new_password: str):
    return client.post(
        "/auth/change-password",
        json={"current_password": current_password, "new_password": new_password},
    )


def test_required_password_change_revokes_all_sessions_and_requires_new_login(
    client: TestClient, db_session: Session
):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=True
    )
    token = authenticate_client(client, db_session, account)
    service = SessionService(db_session)
    tokens = [token] + [service.create_session(account).token for _ in range(2)]
    other = Account(
        tenant_id=account.tenant_id, account_id="EM-000002", name="Other",
        role=AccountRole.EMPLOYEE,
        password_hash=PasswordService().hash_password("OtherSecure1!"),
    )
    db_session.add(other)
    db_session.commit()
    other_token = service.create_session(other).token

    response = change_password(
        client,
        current_password="InitialPass1!",
        new_password="NewSecurePass2!",
    )

    assert response.status_code == 200
    assert response.json() == SUCCESS_RESPONSE
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert "path=/" in response.headers["set-cookie"].lower()
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    db_session.refresh(account)
    assert PasswordService().verify_password("NewSecurePass2!", account.password_hash)
    assert not PasswordService().verify_password("InitialPass1!", account.password_hash)
    for old_token in tokens:
        with pytest.raises(InvalidSessionError):
            service.get_account_for_token(old_token)
        assert client.get("/accounts", headers={"Cookie": f"{SESSION_COOKIE_NAME}={old_token}"}).status_code == 401
    assert service.get_account_for_token(other_token).id == other.id
    assert client.get("/accounts").status_code == 401
    old_login = client.post(
        "/auth/login", json={"identifier": account.account_id, "password": "InitialPass1!"}
    )
    assert old_login.status_code == 401
    assert "set-cookie" not in old_login.headers
    new_login = client.post(
        "/auth/login", json={"identifier": account.account_id, "password": "NewSecurePass2!"}
    )
    assert new_login.status_code == 200
    assert new_login.json()["password_change_required"] is False
    new_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert new_token and new_token not in tokens
    assert service.get_account_for_token(new_token).id == account.id


def test_voluntary_password_change_is_allowed(client: TestClient, db_session: Session):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=False
    )
    authenticate_client(client, db_session, account)

    response = change_password(
        client,
        current_password="InitialPass1!",
        new_password="VoluntaryPass2!",
    )

    assert response.status_code == 200
    assert response.json() == SUCCESS_RESPONSE
    assert client.cookies.get(SESSION_COOKIE_NAME) is None


def test_change_password_requires_a_valid_session_cookie(client: TestClient):
    missing_cookie = change_password(
        client,
        current_password="InitialPass1!",
        new_password="NewSecurePass2!",
    )
    client.cookies.set(SESSION_COOKIE_NAME, "unknown-token")
    invalid_cookie = change_password(
        client,
        current_password="InitialPass1!",
        new_password="NewSecurePass2!",
    )

    for response in (missing_cookie, invalid_cookie):
        assert response.status_code == 401
        assert response.json() == {"detail": "Ungültige Sitzung."}


def test_invalid_current_password_leaves_account_unchanged(
    client: TestClient, db_session: Session
):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=True
    )
    original_hash = account.password_hash
    authenticate_client(client, db_session, account)

    response = change_password(
        client,
        current_password="WrongCurrentPass1!",
        new_password="NewSecurePass2!",
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Das aktuelle Passwort ist ungültig."}
    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True


@pytest.mark.parametrize(
    ("new_password", "expected_detail"),
    [
        (
            "Short1!",
            {
                "message": "Das neue Passwort erfüllt die Anforderungen nicht.",
                "is_too_short": True,
                "has_too_few_categories": False,
            },
        ),
        (
            "alllowercase1",
            {
                "message": "Das neue Passwort erfüllt die Anforderungen nicht.",
                "is_too_short": False,
                "has_too_few_categories": True,
            },
        ),
    ],
)
def test_invalid_new_password_returns_service_policy_details_without_persisting(
    client: TestClient,
    db_session: Session,
    new_password: str,
    expected_detail: dict[str, bool | str],
):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=True
    )
    original_hash = account.password_hash
    authenticate_client(client, db_session, account)

    response = change_password(
        client,
        current_password="InitialPass1!",
        new_password=new_password,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": expected_detail}
    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True


def test_rejects_reusing_current_password_without_changing_state(
    client: TestClient, db_session: Session
):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=True
    )
    original_hash = account.password_hash
    authenticate_client(client, db_session, account)

    response = change_password(
        client,
        current_password="InitialPass1!",
        new_password="InitialPass1!",
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Das neue Passwort muss sich vom aktuellen Passwort unterscheiden."
    }
    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True


def test_rejects_extra_request_fields(client: TestClient, db_session: Session):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=True
    )
    authenticate_client(client, db_session, account)

    response = client.post(
        "/auth/change-password",
        json={
            "current_password": "InitialPass1!",
            "new_password": "NewSecurePass2!",
            "account_id": "EM-000001",
            "tenant_id": "client-controlled",
            "role": "OWNER",
        },
    )

    assert response.status_code == 422


def test_password_whitespace_is_passed_to_the_service_unchanged(
    client: TestClient, db_session: Session
):
    account = create_account(
        db_session, password=" InitialPass1! ", password_change_required=True
    )
    authenticate_client(client, db_session, account)
    new_password = " NewSecurePass2! "

    response = change_password(
        client,
        current_password=" InitialPass1! ",
        new_password=new_password,
    )

    assert response.status_code == 200
    db_session.refresh(account)
    assert PasswordService().verify_password(new_password, account.password_hash)
    assert not PasswordService().verify_password(new_password.strip(), account.password_hash)


@pytest.mark.parametrize(
    ("current_password", "new_password", "status_code"),
    [
        ("WrongCurrent1!", "NewSecurePass2!", 400),
        ("InitialPass1!", "Short1!", 422),
        ("InitialPass1!", "InitialPass1!", 400),
    ],
)
def test_failed_password_change_preserves_sessions_cookie_and_credentials(
    client: TestClient, db_session: Session,
    current_password: str, new_password: str, status_code: int,
):
    account = create_account(db_session, password="InitialPass1!", password_change_required=True)
    original_hash = account.password_hash
    token = authenticate_client(client, db_session, account)
    service = SessionService(db_session)
    tokens = [token] + [service.create_session(account).token for _ in range(2)]
    response = change_password(client, current_password=current_password, new_password=new_password)
    assert response.status_code == status_code
    assert "set-cookie" not in response.headers
    assert client.cookies.get(SESSION_COOKIE_NAME) == token
    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True
    for active_token in tokens:
        assert service.get_account_for_token(active_token).id == account.id


@pytest.mark.parametrize("failure_method", ["execute", "commit"])
def test_password_change_database_failure_rolls_back_credentials_and_sessions(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
    failure_method: str,
):
    account = create_account(db_session, password="InitialPass1!", password_change_required=True)
    original_hash = account.password_hash
    token = authenticate_client(client, db_session, account)
    service = SessionService(db_session)
    sessions = [service.create_session(account) for _ in range(2)]

    # Patch at the revocation boundary, after authentication has completed.
    original_revoke = SessionService.revoke_all_sessions_for_account

    def fail(*args, **kwargs):
        raise SQLAlchemyError("simulated database failure")

    def failing_revoke(self, account_id, *, commit=True):
        with monkeypatch.context() as patch:
            patch.setattr(self._db, "execute", fail)
            original_revoke(self, account_id, commit=commit)

    with monkeypatch.context() as patch:
        if failure_method == "commit":
            patch.setattr(Session, "commit", fail)
        else:
            patch.setattr(SessionService, "revoke_all_sessions_for_account", failing_revoke)
        response = change_password(client, current_password="InitialPass1!", new_password="NewSecurePass2!")
    assert response.status_code == 500
    assert response.json() == {"detail": "Passwortänderung derzeit nicht möglich."}
    assert "set-cookie" not in response.headers
    assert client.cookies.get(SESSION_COOKIE_NAME) == token
    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True
    for active_token in [token] + [result.token for result in sessions]:
        assert service.get_account_for_token(active_token).id == account.id
