from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RestTypeDefinition, Tenant
from app.schemas import RestTypeCreate, RestTypeRead

router = APIRouter()


@router.post("", response_model=RestTypeRead, status_code=status.HTTP_201_CREATED)
def create_rest_type(payload: RestTypeCreate, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).first()
    if not tenant:
        raise Exception("No tenant found")

    rest_type = RestTypeDefinition(
        tenant_id=tenant.id,
        name=payload.name,
        measure_fields=payload.measure_fields,
        accepted_rotated_input=payload.accepted_rotated_input,
    )
    db.add(rest_type)
    db.commit()
    db.refresh(rest_type)
    return rest_type


@router.get("", response_model=list[RestTypeRead])
def list_rest_types(db: Session = Depends(get_db)):
    return db.query(RestTypeDefinition).all()
