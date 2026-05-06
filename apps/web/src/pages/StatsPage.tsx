import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import {
  getStatsSummaryApi,
  getStatsCalendarApi,
  getStatsTimelineApi,
  type CalendarDay,
} from '@/lib/stats';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtKm(km: number): string {
  return km >= 1000
    ? `${(km / 1000).toFixed(1)}k km`
    : `${km.toFixed(0)} km`;
}

function fmtHours(h: number): string {
  if (h < 1) return `${Math.round(h * 60)} min`;
  return `${h.toFixed(1)} h`;
}

function fmtAscent(m: number): string {
  return m >= 1000
    ? `${(m / 1000).toFixed(1)}k m`
    : `${Math.round(m)} m`;
}

// ── Summary cards ─────────────────────────────────────────────────────────────

function SummaryCards() {
  const { data, isLoading } = useQuery({
    queryKey: ['stats', 'summary'],
    queryFn: getStatsSummaryApi,
  });

  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="animate-pulse rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 h-3 w-20 rounded bg-slate-200" />
            <div className="h-6 w-16 rounded bg-slate-200" />
          </div>
        ))}
      </div>
    );
  }

  const cards = [
    { label: 'Actividades', value: String(data.total_activities) },
    { label: 'Distancia', value: fmtKm(data.total_km) },
    { label: 'Tiempo en bici', value: fmtHours(data.total_hours) },
    { label: 'Desnivel +', value: fmtAscent(data.total_ascent_m) },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {cards.map(({ label, value }) => (
        <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">{value}</p>
        </div>
      ))}
    </div>
  );
}

// ── Calendar heatmap ──────────────────────────────────────────────────────────

const DAYS_SHORT = ['L', 'M', 'X', 'J', 'V', 'S', 'D'];
const MONTHS_SHORT = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

function heatColor(count: number): string {
  if (count === 0) return 'bg-slate-100';
  if (count === 1) return 'bg-green-200';
  if (count === 2) return 'bg-green-400';
  if (count <= 4) return 'bg-green-500';
  return 'bg-green-700';
}

interface GridCell {
  date: string | null;
  data: CalendarDay | null;
}

function buildGrid(year: number, days: Record<string, CalendarDay>): GridCell[][] {
  // cells[i]: column = floor(i/7), row = i%7, row 0 = Monday
  const jan1 = new Date(year, 0, 1);
  const startDow = (jan1.getDay() + 6) % 7; // Mon=0 … Sun=6

  const cells: GridCell[] = [];
  for (let i = 0; i < startDow; i++) cells.push({ date: null, data: null });

  const cur = new Date(year, 0, 1);
  while (cur.getFullYear() === year) {
    const iso = cur.toISOString().slice(0, 10);
    cells.push({ date: iso, data: days[iso] ?? null });
    cur.setDate(cur.getDate() + 1);
  }
  while (cells.length % 7 !== 0) cells.push({ date: null, data: null });

  const numWeeks = cells.length / 7;
  const grid: GridCell[][] = [];
  for (let w = 0; w < numWeeks; w++) {
    grid.push(cells.slice(w * 7, (w + 1) * 7));
  }
  return grid;
}

function monthLabels(year: number, numWeeks: number): string[] {
  // For each week column, determine its month (use the first non-null day)
  const labels: string[] = Array(numWeeks).fill('');
  const jan1 = new Date(year, 0, 1);
  const startDow = (jan1.getDay() + 6) % 7;

  let seen = -1;
  for (let w = 0; w < numWeeks; w++) {
    // Day index of Monday (first row) of this week
    const cellIdx = w * 7;
    const dayOffset = cellIdx - startDow;
    if (dayOffset < 0) continue;
    const d = new Date(year, 0, 1 + dayOffset);
    if (d.getFullYear() !== year) continue;
    const m = d.getMonth();
    if (m !== seen) {
      labels[w] = MONTHS_SHORT[m];
      seen = m;
    }
  }
  return labels;
}

function CalendarHeatmap({ year }: { year: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['stats', 'calendar', year],
    queryFn: () => getStatsCalendarApi(year),
  });

  if (isLoading || !data) {
    return <div className="h-28 animate-pulse rounded-lg bg-slate-100" />;
  }

  const grid = buildGrid(year, data.days);
  const mLabels = monthLabels(year, grid.length);

  return (
    <div className="overflow-x-auto">
      {/* Month labels */}
      <div className="mb-1 flex" style={{ paddingLeft: '1.5rem' }}>
        {mLabels.map((label, i) => (
          <div key={i} className="w-3.5 shrink-0 text-center text-[10px] text-slate-400">
            {label}
          </div>
        ))}
      </div>

      <div className="flex">
        {/* Day-of-week labels */}
        <div className="mr-1 flex flex-col gap-0.5">
          {DAYS_SHORT.map((d) => (
            <div key={d} className="flex h-3 w-4 items-center justify-end text-[10px] text-slate-400">
              {d}
            </div>
          ))}
        </div>

        {/* Cells */}
        <div className="flex gap-0.5">
          {grid.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-0.5">
              {week.map((cell, di) => {
                const count = cell.data?.count ?? 0;
                const title = cell.date
                  ? count > 0
                    ? `${cell.date}: ${count} actividad${count > 1 ? 'es' : ''} (${cell.data!.km.toFixed(1)} km)`
                    : cell.date
                  : '';
                return (
                  <div
                    key={di}
                    title={title}
                    className={`h-3 w-3 rounded-sm ${cell.date ? heatColor(count) : 'bg-transparent'}`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Timeline chart ────────────────────────────────────────────────────────────

function TimelineChart() {
  const [metric, setMetric] = useState<'km' | 'hours'>('km');

  const { data, isLoading } = useQuery({
    queryKey: ['stats', 'timeline'],
    queryFn: () => getStatsTimelineApi('month'),
  });

  if (isLoading || !data) {
    return <div className="h-48 animate-pulse rounded-lg bg-slate-100" />;
  }

  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">Sin datos de actividad.</p>
    );
  }

  const labels = data.map((e) => {
    const [y, m] = e.period.split('-');
    return `${MONTHS_SHORT[parseInt(m) - 1]} ${y}`;
  });

  const values = data.map((e) => (metric === 'km' ? +e.km.toFixed(1) : +e.hours.toFixed(1)));

  const chartData = {
    labels,
    datasets: [
      {
        label: metric === 'km' ? 'Km' : 'Horas',
        data: values,
        backgroundColor: '#3b82f6',
        borderRadius: 4,
        borderSkipped: false,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { raw: unknown }) =>
            metric === 'km' ? `${ctx.raw} km` : `${ctx.raw} h`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          callback: (v: unknown) => (metric === 'km' ? `${v} km` : `${v} h`),
        },
      },
    },
  };

  return (
    <div>
      <div className="mb-3 flex gap-2">
        <button
          onClick={() => setMetric('km')}
          className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
            metric === 'km'
              ? 'bg-blue-600 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          Distancia
        </button>
        <button
          onClick={() => setMetric('hours')}
          className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
            metric === 'hours'
              ? 'bg-blue-600 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          Tiempo
        </button>
      </div>
      <Bar data={chartData} options={options as Parameters<typeof Bar>[0]['options']} />
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function StatsPage() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);

  const years = Array.from({ length: 6 }, (_, i) => currentYear - i);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-800">Estadísticas</h2>

      <SummaryCards />

      {/* Calendar */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Actividad por día</h3>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-600"
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <CalendarHeatmap year={year} />
        <div className="mt-3 flex items-center gap-1.5 text-[10px] text-slate-400">
          <span>Menos</span>
          {['bg-slate-100', 'bg-green-200', 'bg-green-400', 'bg-green-500', 'bg-green-700'].map((c) => (
            <div key={c} className={`h-3 w-3 rounded-sm ${c}`} />
          ))}
          <span>Más</span>
        </div>
      </div>

      {/* Timeline */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-slate-700">Evolución mensual</h3>
        <TimelineChart />
      </div>
    </div>
  );
}
