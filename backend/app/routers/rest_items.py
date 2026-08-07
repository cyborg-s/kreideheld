from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RestItem, Tenant
from app.schemas import RestItemCreate, RestItemRead

router = APIRouter()


@router.post("", response_model=RestItemRead, status_code=status.HTTP_201_CREATED)
def create_rest_item(payload: RestItemCreate, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="No tenant found")

    if payload.length_mm <= 0 or payload.width_mm <= 0 or payload.height_mm <= 0:
        raise HTTPException(status_code=400, detail="Dimensions must be positive")

    rest_item = RestItem(
        tenant_id=tenant.id,
        rest_type_id=payload.rest_type_id,
        chalk_number=payload.chalk_number,
        material_name=payload.material_name,
        length_mm=payload.length_mm,
        width_mm=payload.width_mm,
        height_mm=payload.height_mm,
        rest_meter_mm=payload.rest_meter_mm,
        notes=payload.notes,
    )
    db.add(rest_item)
    db.commit()
    db.refresh(rest_item)
    return rest_item


@router.get("", response_model=list[RestItemRead])
def list_rest_items(db: Session = Depends(get_db)):
    return db.query(RestItem).all()


@router.get("/{rest_item_id}", response_model=RestItemRead)
def get_rest_item(rest_item_id: str, db: Session = Depends(get_db)):
    rest_item = db.query(RestItem).filter(RestItem.id == rest_item_id).first()
    if not rest_item:
        raise HTTPException(status_code=404, detail="Rest item not found")
    return rest_item


@router.put("/{rest_item_id}", response_model=RestItemRead)
def update_rest_item(rest_item_id: str, payload: RestItemCreate, db: Session = Depends(get_db)):
    rest_item = db.query(RestItem).filter(RestItem.id == rest_item_id).first()
    if not rest_item:
        raise HTTPException(status_code=404, detail="Rest item not found")

    if payload.length_mm <= 0 or payload.width_mm <= 0 or payload.height_mm <= 0:
        raise HTTPException(status_code=400, detail="Dimensions must be positive")

    rest_item.rest_type_id = payload.rest_type_id
    rest_item.chalk_number = payload.chalk_number
    rest_item.material_name = payload.material_name
    rest_item.length_mm = payload.length_mm
    rest_item.width_mm = payload.width_mm
    rest_item.height_mm = payload.height_mm
    rest_item.rest_meter_mm = payload.rest_meter_mm
    rest_item.notes = payload.notes

    db.commit()
    db.refresh(rest_item)
    return rest_item


@router.delete("/{rest_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rest_item(rest_item_id: str, db: Session = Depends(get_db)):
    rest_item = db.query(RestItem).filter(RestItem.id == rest_item_id).first()
    if not rest_item:
        raise HTTPException(status_code=404, detail="Rest item not found")

    db.delete(rest_item)
    db.commit()
    return None
