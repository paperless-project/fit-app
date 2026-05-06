import { api } from './api';

export async function changePasswordApi(
  current_password: string,
  new_password: string,
): Promise<void> {
  await api<{ detail: string }>('/users/me/password', {
    method: 'PATCH',
    body: JSON.stringify({ current_password, new_password }),
  });
}

export async function deleteAccountApi(): Promise<void> {
  await api<void>('/users/me', {
    method: 'DELETE',
    body: JSON.stringify({ confirm: true }),
  });
}
