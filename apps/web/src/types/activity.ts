export interface Activity {
  id: string;
  file_name: string;
  name: string | null;
  sport: string | null;
  notes: string | null;
  started_at: string;
  duration_s: number | null;
  moving_time_s: number | null;
  distance_m: number | null;
  ascent_m: number | null;
  descent_m: number | null;
  avg_speed_mps: number | null;
  max_speed_mps: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_cadence: number | null;
  avg_power: number | null;
  calories: number | null;
  created_at: string;
}

export interface RecordPoint {
  ts: string;
  lat: number | null;
  lon: number | null;
  altitude_m: number | null;
  distance_m: number | null;
  speed_mps: number | null;
  heart_rate: number | null;
  cadence: number | null;
  power: number | null;
}

export interface LapPoint {
  lap_index: number;
  start_time: string;
  duration_s: number | null;
  distance_m: number | null;
  avg_speed_mps: number | null;
  avg_hr: number | null;
  ascent_m: number | null;
}

export interface ActivityDetail extends Activity {
  records: RecordPoint[];
  laps: LapPoint[];
}

export interface ActivityPage {
  items: Activity[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
