from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant
from app.schemas import LoginRequest, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.email == payload.email).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if payload.password != "demo123":
        raise HTTPException(status_code=401, detail="Invalid password")

    return LoginResponse(
        tenant_id=tenant.id,
        email=tenant.email,
        name=tenant.name,
        unit_preference=tenant.unit_preference,
    )
