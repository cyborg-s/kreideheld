from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_password_change_completed
from app.models import Account, AccountRole
from app.schemas import AccountCreate, AccountOnboardingResponse, AccountRead
from app.services.account_onboarding_service import (
    AccountIdGenerationError,
    AccountOnboardingService,
    AccountPersistenceError,
    EmailAlreadyInUseError,
    InvalidAccountDataError,
    TenantNotFoundError,
    UnsupportedTargetRoleError,
)

router = APIRouter()


def can_create_account(actor_role: AccountRole, target_role: AccountRole) -> bool:
    """Return whether an authenticated actor may onboard the requested role."""

    allowed_roles = {
        AccountRole.OWNER: {AccountRole.ADMIN, AccountRole.EMPLOYEE},
        AccountRole.ADMIN: {AccountRole.EMPLOYEE},
        AccountRole.EMPLOYEE: set(),
    }
    return target_role in allowed_roles[actor_role]


@router.post(
    "", response_model=AccountOnboardingResponse, status_code=status.HTTP_201_CREATED
)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    current_account: Account = Depends(require_password_change_completed),
):
    """Onboard an ADMIN or EMPLOYEE within the authenticated actor's tenant."""

    if not can_create_account(current_account.role, payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nicht berechtigt, diese Account-Rolle zu erstellen.",
        )

    try:
        result = AccountOnboardingService(db).onboard(
            tenant_id=current_account.tenant_id,
            name=payload.name,
            email=payload.email,
            role=payload.role,
        )
    except EmailAlreadyInUseError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-Mail-Adresse wird bereits verwendet.",
        ) from error
    except InvalidAccountDataError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ungültige Account-Daten.",
        ) from error
    except UnsupportedTargetRoleError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nicht berechtigt, diese Account-Rolle zu erstellen.",
        ) from error
    except (TenantNotFoundError, AccountPersistenceError, AccountIdGenerationError) as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account-Erstellung derzeit nicht möglich.",
        ) from error

    return AccountOnboardingResponse(
        account_id=result.account.account_id,
        name=result.account.name,
        email=result.account.email,
        role=result.account.role,
        password_change_required=result.account.password_change_required,
        temporary_password=result.temporary_password,
    )


@router.get("", response_model=list[AccountRead])
def list_accounts(
    db: Session = Depends(get_db),
    current_account: Account = Depends(require_password_change_completed),
):
    """List account administration data only within the actor's tenant."""

    if current_account.role not in {AccountRole.OWNER, AccountRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nicht berechtigt, die Account-Liste zu lesen.",
        )
    return db.query(Account).filter(Account.tenant_id == current_account.tenant_id).all()
