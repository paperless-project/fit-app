import { api } from './api';

export interface StatsSummary {
  total_activities: number;
  total_km: number;
  total_hours: number;
  total_ascent_m: number;
}

export interface CalendarDay {
  count: number;
  km: number;
}

export interface CalendarResponse {
  year: number;
  days: Record<string, CalendarDay>;
}

export interface TimelineEntry {
  period: string;
  count: number;
  km: number;
  hours: number;
  ascent_m: number;
}

export function getStatsSummaryApi(): Promise<StatsSummary> {
  return api<StatsSummary>('/stats/summary');
}

export function getStatsCalendarApi(year: number): Promise<CalendarResponse> {
  return api<CalendarResponse>(`/stats/calendar?year=${year}`);
}

export function getStatsTimelineApi(bucket: 'month' | 'year' = 'month'): Promise<TimelineEntry[]> {
  return api<TimelineEntry[]>(`/stats/timeline?bucket=${bucket}`);
}
