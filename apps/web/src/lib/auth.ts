import type { LoginResponse, UserRead } from '@/types/user';
import { ApiError } from './api';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// fastapi-users login uses OAuth2 form data (username + password)
export async function loginApi(
  email: string,
  password: string,
  remember = false,
): Promise<LoginResponse> {
  const endpoint = remember ? '/auth/jwt-remember/login' : '/auth/jwt/login';
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(text || res.statusText, res.status);
  }
  return res.json() as Promise<LoginResponse>;
}

export async function registerApi(email: string, password: string): Promise<UserRead> {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(text || res.statusText, res.status);
  }
  return res.json() as Promise<UserRead>;
}

export async function getMeApi(token: string): Promise<UserRead> {
  const res = await fetch(`${BASE_URL}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiError(res.statusText, res.status);
  return res.json() as Promise<UserRead>;
}

export async function verifyEmailApi(token: string): Promise<UserRead> {
  const res = await fetch(`${BASE_URL}/auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(text || res.statusText, res.status);
  }
  return res.json() as Promise<UserRead>;
}

export async function logoutApi(token: string): Promise<void> {
  await fetch(`${BASE_URL}/auth/jwt/logout`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function sendOTPApi(email: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/auth/register/send-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? 'Error al enviar el código', res.status);
  }
}

export async function verifyOTPApi(email: string, code: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/auth/register/verify-otp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? 'Código incorrecto o expirado', res.status);
  }
  const data = await res.json();
  return data.verified_token as string;
}

export async function completeRegistrationApi(payload: {
  verified_token: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  password: string;
}): Promise<void> {
  const res = await fetch(`${BASE_URL}/auth/register/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? 'Error al crear la cuenta', res.status);
  }
}

export async function completeGoogleRegistrationApi(
  google_token: string,
): Promise<{ access_token: string; token_type: string }> {
  const res = await fetch(`${BASE_URL}/auth/register/complete-google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ google_token }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail ?? 'Error al crear la cuenta con Google', res.status);
  }
  return res.json();
}
