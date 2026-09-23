from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Tenant, generate_account_id
from app.schemas import AccountCreate, AccountRead

router = APIRouter()


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="No tenant found")

    if payload.email and db.query(Account).filter(Account.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    for _ in range(5):
        account = Account(
            tenant_id=tenant.id,
            account_id=generate_account_id(),
            name=payload.name,
            email=payload.email,
            role=payload.role,
            password_change_required=payload.password_change_required,
        )
        db.add(account)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            db.refresh(account)
            return account

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not generate a unique account ID")


@router.get("", response_model=list[AccountRead])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(Account).all()
