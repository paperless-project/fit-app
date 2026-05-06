import { api, downloadFile, ApiError } from './api';
import type { Activity, ActivityDetail } from '@/types/activity';

export interface ActivityFilters {
  q?: string;
  sport?: string;
  date_from?: string;
  date_to?: string;
}

export interface ActivityPatch {
  name?: string | null;
  sport?: string | null;
  notes?: string | null;
}

function buildQuery(filters: ActivityFilters): string {
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  if (filters.sport) params.set('sport', filters.sport);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function getActivitiesApi(filters: ActivityFilters = {}): Promise<Activity[]> {
  return api<Activity[]>(`/activities/${buildQuery(filters)}`);
}

export async function getActivityDetailApi(id: string): Promise<ActivityDetail> {
  return api<ActivityDetail>(`/activities/${id}`);
}

export async function uploadActivityApi(file: File): Promise<Activity> {
  const form = new FormData();
  form.append('file', file);
  return api<Activity>('/activities/upload', { method: 'POST', body: form });
}

export async function patchActivityApi(id: string, patch: ActivityPatch): Promise<Activity> {
  return api<Activity>(`/activities/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function downloadGpxApi(id: string, filename: string): Promise<void> {
  return downloadFile(`/activities/${id}/export/gpx`, filename);
}

export async function downloadCsvApi(filters: ActivityFilters = {}): Promise<void> {
  return downloadFile(`/activities/export/csv${buildQuery(filters)}`, 'actividades.csv');
}

export { ApiError };
