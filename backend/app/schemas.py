from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models import AccountRole


class LoginRequest(BaseModel):
    identifier: str
    password: str

    model_config = ConfigDict(extra="forbid")


class LoginResponse(BaseModel):
    account_id: str
    role: AccountRole
    password_change_required: bool


class PasswordChangeRequest(BaseModel):
    """Exact user-entered credentials for an authenticated password change."""

    current_password: str
    new_password: str

    model_config = ConfigDict(extra="forbid")


class PasswordChangeResponse(BaseModel):
    """Minimal confirmation without account, hash, or session data."""

    password_change_required: bool


class TenantCreate(BaseModel):
    name: str
    email: str
    unit_preference: str = "mm"
    is_active: bool = True


class TenantRead(TenantCreate):
    id: str
    model_config = ConfigDict(from_attributes=True)


class AccountCreate(BaseModel):
    """Client-controlled input for the authenticated account-onboarding flow."""

    name: str
    email: Optional[str] = None
    role: AccountRole

    model_config = ConfigDict(extra="forbid")


class AccountRead(BaseModel):
    """Normal account representation without credential material."""

    id: str
    tenant_id: str
    account_id: str
    name: str
    email: Optional[str] = None
    role: AccountRole
    password_change_required: bool
    model_config = ConfigDict(from_attributes=True)


class AccountOnboardingResponse(BaseModel):
    """One-time response containing the initial plaintext credential."""

    account_id: str
    name: str
    email: Optional[str] = None
    role: AccountRole
    password_change_required: bool
    temporary_password: str


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
