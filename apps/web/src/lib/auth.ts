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
