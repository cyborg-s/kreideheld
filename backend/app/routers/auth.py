from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import SESSION_COOKIE_NAME, session_cookie_settings
from app.schemas import LoginRequest, LoginResponse
from app.services.account_authentication_service import (
    AccountAuthenticationService,
    InvalidCredentialsError,
)
from app.services.session_service import SessionService

router = APIRouter()


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
