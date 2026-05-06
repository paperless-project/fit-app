"""Registro central de modelos para Alembic autogenerate."""
from fitapp.models.activity import Activity, Lap, Record
from fitapp.models.email_otp import EmailOTP
from fitapp.models.user import User

__all__ = ["Activity", "EmailOTP", "Lap", "Record", "User"]
