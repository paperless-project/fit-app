"""Schemas para el flujo de registro multi-paso."""
from __future__ import annotations

import datetime

from pydantic import BaseModel, EmailStr

from fitapp.models.user import Gender


class SendOTPRequest(BaseModel):
    email: EmailStr


class SendOTPResponse(BaseModel):
    message: str


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyOTPResponse(BaseModel):
    verified_token: str


class CompleteRegistrationRequest(BaseModel):
    verified_token: str
    first_name: str
    last_name: str
    birth_date: datetime.date
    gender: Gender
    password: str


class CompleteRegistrationResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    is_verified: bool


class CompleteGoogleRegistrationRequest(BaseModel):
    google_token: str


class CompleteGoogleRegistrationResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
