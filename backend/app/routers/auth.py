from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import (
    SESSION_COOKIE_NAME,
    get_current_account,
    session_cookie_settings,
)
from app.models import Account
from app.schemas import (
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
)
from app.services.account_authentication_service import (
    AccountAuthenticationService,
    InvalidCredentialsError,
)
from app.services.password_change_service import (
    InvalidCurrentPasswordError,
    InvalidNewPasswordError,
    PasswordChangePersistenceError,
    PasswordChangeService,
    PasswordUnchangedError,
)
from app.services.session_service import SessionPersistenceError, SessionService

router = APIRouter()


def _delete_session_cookie(response: Response) -> None:
    cookie_settings = session_cookie_settings()
    cookie_settings.pop("max_age")
    response.delete_cookie(key=SESSION_COOKIE_NAME, **cookie_settings)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        account = AccountAuthenticationService(db).authenticate(
            identifier=payload.identifier,
            password=payload.password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültige Anmeldedaten.",
        ) from error

    session_result = SessionService(db).create_session(account)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_result.token,
        **session_cookie_settings(),
    )

    return LoginResponse(
        account_id=account.account_id,
        role=account.role,
        password_change_required=account.password_change_required,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """Idempotently revoke only the presented session, even during password-change duty."""

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is not None:
        try:
            SessionService(db).revoke_session(token)
        except SessionPersistenceError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Abmeldung derzeit nicht möglich.",
            ) from error
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_session_cookie(response)
    return response


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
):
    """Change only the authenticated account's password without changing its session."""

    try:
        account = PasswordChangeService(db).change_password(
            account=current_account,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidCurrentPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das aktuelle Passwort ist ungültig.",
        ) from error
    except InvalidNewPasswordError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Das neue Passwort erfüllt die Anforderungen nicht.",
                "is_too_short": error.validation_result.is_too_short,
                "has_too_few_categories": error.validation_result.has_too_few_categories,
            },
        ) from error
    except PasswordUnchangedError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das neue Passwort muss sich vom aktuellen Passwort unterscheiden.",
        ) from error
    except PasswordChangePersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Passwortänderung derzeit nicht möglich.",
        ) from error

    return PasswordChangeResponse(
        password_change_required=account.password_change_required
    )
