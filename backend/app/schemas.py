from typing import List, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.models import AccountRole


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
    name: str
    email: Optional[str] = None
    role: AccountRole
    password_change_required: bool = True

    @model_validator(mode="after")
    def privileged_accounts_require_email(self):
        if self.role in {AccountRole.OWNER, AccountRole.ADMIN} and self.email is None:
            raise ValueError("OWNER and ADMIN accounts require an email address")
        return self


class AccountRead(AccountCreate):
    id: str
    tenant_id: str
    account_id: str
    password_change_required: bool
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
