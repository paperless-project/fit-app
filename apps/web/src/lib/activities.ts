import { api, ApiError } from './api';
import type { Activity, ActivityDetail } from '@/types/activity';

export async function getActivitiesApi(): Promise<Activity[]> {
  return api<Activity[]>('/activities/');
}

export async function getActivityDetailApi(id: string): Promise<ActivityDetail> {
  return api<ActivityDetail>(`/activities/${id}`);
}

export async function uploadActivityApi(file: File): Promise<Activity> {
  const form = new FormData();
  form.append('file', file);
  return api<Activity>('/activities/upload', { method: 'POST', body: form });
}

export { ApiError };
