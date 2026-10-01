import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies.auth import SESSION_COOKIE_NAME
from app.models import Account, AccountRole, Tenant
from app.services.password_service import PasswordService
from app.services.session_service import SessionService


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
    token = SessionService(db_session).create_session(account).token
    client.cookies.set(SESSION_COOKIE_NAME, token)
    return token


def change_password(client: TestClient, *, current_password: str, new_password: str):
    return client.post(
        "/auth/change-password",
        json={"current_password": current_password, "new_password": new_password},
    )


def test_required_password_change_updates_credentials_and_keeps_session_valid(
    client: TestClient, db_session: Session
):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=True
    )
    token = authenticate_client(client, db_session, account)

    response = change_password(
        client,
        current_password="InitialPass1!",
        new_password="NewSecurePass2!",
    )

    assert response.status_code == 200
    assert response.json() == {"password_change_required": False}
    assert "set-cookie" not in response.headers
    db_session.refresh(account)
    assert PasswordService().verify_password("NewSecurePass2!", account.password_hash)
    assert not PasswordService().verify_password("InitialPass1!", account.password_hash)
    assert SessionService(db_session).get_account_for_token(token).id == account.id


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
    assert response.json() == {"password_change_required": False}


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
