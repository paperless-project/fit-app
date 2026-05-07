import { api } from './api';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface StravaStatus {
  connected: boolean;
  athlete_id?: number;
  last_import_at?: string;
}

export async function getStravaStatus(): Promise<StravaStatus> {
  return api<StravaStatus>('/strava/status');
}

export async function disconnectStrava(): Promise<void> {
  await api<void>('/strava/disconnect', { method: 'DELETE' });
}

export async function startStravaImport(after?: number, before?: number): Promise<{ status: string }> {
  const params = new URLSearchParams();
  if (after) params.set('after', String(after));
  if (before) params.set('before', String(before));
  const qs = params.toString();
  return api<{ status: string }>(`/strava/import${qs ? `?${qs}` : ''}`, { method: 'POST' });
}

export async function connectStrava(): Promise<void> {
  const token = localStorage.getItem('access_token');
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}/strava/authorize`, { headers });
  if (!res.ok) throw new Error('No se pudo iniciar la conexión con Strava.');
  const { authorization_url } = await res.json();
  window.location.href = authorization_url;
}
