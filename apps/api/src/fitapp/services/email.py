"""Servicio de envio de emails via SMTP."""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fitapp.config import settings


def _send_sync(to: str, subject: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, to, msg.as_string())


async def send_verification_email(email: str, token: str) -> None:
    if not settings.smtp_host:
        return
    verify_url = f"{settings.frontend_url}/verify?token={token}"
    body = f"""
    <p>Bienvenido a fit-app.</p>
    <p>Para confirmar tu dirección de correo, haz clic en el siguiente enlace:</p>
    <p><a href="{verify_url}">{verify_url}</a></p>
    <p>Este enlace caduca en 1 hora.</p>
    """
    await asyncio.to_thread(_send_sync, email, "Confirma tu correo — fit-app", body)


async def send_welcome_email(email: str, first_name: str) -> None:
    if not settings.smtp_host:
        return
    body = f"""
    <p>Hola <strong>{first_name}</strong>,</p>
    <p>Te damos la bienvenida a <strong>fit-app</strong>. 🎉</p>
    <p>Ya puedes acceder a tu cuenta y empezar a explorar tus actividades.</p>
    <p><a href="{settings.frontend_url}/login">Entrar a fit-app</a></p>
    """
    await asyncio.to_thread(_send_sync, email, "Te damos la bienvenida a fit-app", body)


async def send_otp_email(email: str, code: str) -> None:
    if not settings.smtp_host:
        return
    body = f"""
    <p>Tu código de verificación para <strong>fit-app</strong> es:</p>
    <h2 style="letter-spacing: 8px; font-size: 36px; font-family: monospace;">{code}</h2>
    <p>Este código caduca en <strong>10 minutos</strong>.</p>
    <p>Si no has solicitado este código, ignora este mensaje.</p>
    """
    await asyncio.to_thread(_send_sync, email, "Código de verificación — fit-app", body)
