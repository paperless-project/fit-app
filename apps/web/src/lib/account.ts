import { api } from './api';
import type { UserRead } from '@/types/user';

export async function changePasswordApi(
  current_password: string,
  new_password: string,
): Promise<void> {
  await api<{ detail: string }>('/users/me/password', {
    method: 'PATCH',
    body: JSON.stringify({ current_password, new_password }),
  });
}

export async function deleteAllActivitiesApi(): Promise<void> {
  await api<void>('/activities', { method: 'DELETE' });
}

export async function deleteAccountApi(): Promise<void> {
  await api<void>('/users/me', {
    method: 'DELETE',
    body: JSON.stringify({ confirm: true }),
  });
}

export async function updateTrainingProfileApi(
  ftp: number | null,
  weight_kg: number | null,
): Promise<UserRead> {
  return api<UserRead>('/users/me/training', {
    method: 'PATCH',
    body: JSON.stringify({ ftp, weight_kg }),
  });
}
