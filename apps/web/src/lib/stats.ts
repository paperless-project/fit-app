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

export interface CalendarActivity {
  id: string;
  name: string | null;
  sport: string | null;
  distance_m: number | null;
  duration_s: number | null;
  calories: number | null;
  avg_power: number | null;
  normalized_power: number | null;
  tss: number | null;
  intensity_factor: number | null;
}

export interface WeekSummary {
  week_number: number;
  week_start: string;
  distance_m: number;
  duration_s: number;
  calories: number;
  tss: number;
  intensity_factor: number | null;
}

export interface YearSummary {
  total_activities: number;
  total_km: number;
  total_hours: number;
  total_calories: number;
}

export interface CalendarDetailResponse {
  year: number;
  ftp: number;
  summary: YearSummary;
  weeks: WeekSummary[];
  days: Record<string, CalendarActivity[]>;
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

export function getCalendarDetailApi(year: number): Promise<CalendarDetailResponse> {
  return api<CalendarDetailResponse>(`/stats/calendar-detail?year=${year}`);
}

export function recalculateNpApi(): Promise<{ message: string }> {
  return api<{ message: string }>('/stats/recalculate-np', { method: 'POST' });
}
