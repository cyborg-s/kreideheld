from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    tenant_id: str
    email: str
    name: str
    unit_preference: str

    model_config = ConfigDict(from_attributes=True)


class TenantCreate(BaseModel):
    name: str
    email: str
    unit_preference: str = "mm"
    is_active: bool = True


class TenantRead(TenantCreate):
    id: str
    model_config = ConfigDict(from_attributes=True)


class AccountCreate(BaseModel):
    code: str
    display_name: str


class AccountRead(AccountCreate):
    id: str
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)


class RestTypeCreate(BaseModel):
    name: str
    measure_fields: List[str]
    accepted_rotated_input: bool = False


class RestTypeRead(RestTypeCreate):
    id: str
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)


class RestItemCreate(BaseModel):
    rest_type_id: str
    chalk_number: str
    material_name: str
    length_mm: int
    width_mm: int
    height_mm: int
    rest_meter_mm: int = 0
    notes: Optional[str] = None


class RestItemRead(RestItemCreate):
    id: str
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)
