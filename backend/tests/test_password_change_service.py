import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Account, AccountRole, Tenant
from app.services.password_change_service import (
    InvalidCurrentPasswordError,
    InvalidNewPasswordError,
    PasswordChangePersistenceError,
    PasswordChangeService,
    PasswordUnchangedError,
)
from app.services.password_service import PasswordService


def create_account(
    db_session: Session, *, password: str, password_change_required: bool = True
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


def test_successful_required_password_change_persists_a_new_hash(db_session: Session):
    account = create_account(db_session, password="InitialPass1!")
    original_hash = account.password_hash

    changed_account = PasswordChangeService(db_session).change_password(
        account=account,
        current_password="InitialPass1!",
        new_password="NewSecurePass2!",
    )

    assert changed_account is account
    assert account.password_hash != original_hash
    assert account.password_change_required is False
    assert PasswordService().verify_password("NewSecurePass2!", account.password_hash)
    assert not PasswordService().verify_password("InitialPass1!", account.password_hash)


def test_voluntary_password_change_keeps_requirement_disabled(db_session: Session):
    account = create_account(
        db_session, password="InitialPass1!", password_change_required=False
    )

    PasswordChangeService(db_session).change_password(
        account=account,
        current_password="InitialPass1!",
        new_password="VoluntaryPass2!",
    )

    assert account.password_change_required is False
    assert PasswordService().verify_password("VoluntaryPass2!", account.password_hash)


def test_invalid_current_password_changes_nothing(db_session: Session):
    account = create_account(db_session, password="InitialPass1!")
    original_hash = account.password_hash

    with pytest.raises(InvalidCurrentPasswordError):
        PasswordChangeService(db_session).change_password(
            account=account,
            current_password="WrongCurrentPass1!",
            new_password="NewSecurePass2!",
        )

    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True


@pytest.mark.parametrize(
    ("new_password", "expected_attribute"),
    [
        ("Short1!", "is_too_short"),
        ("alllowercase1", "has_too_few_categories"),
    ],
)
def test_invalid_new_password_reports_existing_policy_result_and_changes_nothing(
    db_session: Session, new_password: str, expected_attribute: str
):
    account = create_account(db_session, password="InitialPass1!")
    original_hash = account.password_hash

    with pytest.raises(InvalidNewPasswordError) as error:
        PasswordChangeService(db_session).change_password(
            account=account,
            current_password="InitialPass1!",
            new_password=new_password,
        )

    assert getattr(error.value.validation_result, expected_attribute) is True
    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True


def test_rejects_reusing_the_current_password_without_changing_state(db_session: Session):
    account = create_account(db_session, password="InitialPass1!")
    original_hash = account.password_hash

    with pytest.raises(PasswordUnchangedError):
        PasswordChangeService(db_session).change_password(
            account=account,
            current_password="InitialPass1!",
            new_password="InitialPass1!",
        )

    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True


def test_valid_password_with_sql_syntax_characters_is_stored_as_password_data(
    db_session: Session,
):
    account = create_account(db_session, password="InitialPass1!")

    PasswordChangeService(db_session).change_password(
        account=account,
        current_password="InitialPass1!",
        new_password="Abcdef1234'!",
    )

    assert PasswordService().verify_password("Abcdef1234'!", account.password_hash)


def test_password_whitespace_is_not_normalized(db_session: Session):
    account = create_account(db_session, password="InitialPass1!")
    new_password = " LeadingPass1! "

    PasswordChangeService(db_session).change_password(
        account=account,
        current_password="InitialPass1!",
        new_password=new_password,
    )

    assert PasswordService().verify_password(new_password, account.password_hash)
    assert not PasswordService().verify_password(new_password.strip(), account.password_hash)


def test_commit_failure_rolls_back_and_raises_controlled_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    account = create_account(db_session, password="InitialPass1!")
    original_hash = account.password_hash

    def failing_commit() -> None:
        raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(PasswordChangePersistenceError):
        PasswordChangeService(db_session).change_password(
            account=account,
            current_password="InitialPass1!",
            new_password="NewSecurePass2!",
        )

    db_session.refresh(account)
    assert account.password_hash == original_hash
    assert account.password_change_required is True
