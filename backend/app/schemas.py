"""Request/response schemas for Phase 2 (authentication + multi-tenancy).

Request models declare explicit fields only (no mass assignment — unknown
fields are ignored). Response models never include password hashes or
session material.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    status: str
    created_at: datetime


class TokenResponse(BaseModel):
    token: str
    token_type: str
    expires_at: datetime
    user: UserResponse


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    created_at: datetime
    role: str | None = None


class ConnectionResponse(BaseModel):
    """Connection status. Never includes credential material or raw Meta
    payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    platform: str
    status: str
    waba_id: str | None = None
    phone_number_id: str | None = None
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None


class ConnectionInitiateResponse(BaseModel):
    """Response for the connection-initiation action."""

    platform: str
    status: str
    detail: str | None = None
