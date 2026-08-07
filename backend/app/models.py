from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    unit_preference = Column(String(10), nullable=False, default="mm")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    accounts = relationship("Account", back_populates="tenant", cascade="all, delete-orphan")
    rest_types = relationship("RestTypeDefinition", back_populates="tenant", cascade="all, delete-orphan")
    rest_items = relationship("RestItem", back_populates="tenant", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="accounts")


class RestTypeDefinition(Base):
    __tablename__ = "rest_type_definitions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    measure_fields = Column(JSON, nullable=False, default=list)
    accepted_rotated_input = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="rest_types")
    rest_items = relationship("RestItem", back_populates="rest_type", cascade="all, delete-orphan")


class RestItem(Base):
    __tablename__ = "rest_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    rest_type_id = Column(String(36), ForeignKey("rest_type_definitions.id"), nullable=False, index=True)
    chalk_number = Column(String(50), nullable=False, index=True)
    material_name = Column(String(255), nullable=False)
    length_mm = Column(Integer, nullable=False)
    width_mm = Column(Integer, nullable=False)
    height_mm = Column(Integer, nullable=False)
    rest_meter_mm = Column(Integer, nullable=False, default=0)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="rest_items")
    rest_type = relationship("RestTypeDefinition", back_populates="rest_items")
