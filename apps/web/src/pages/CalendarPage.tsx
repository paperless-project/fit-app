import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  getCalendarDetailApi,
  recalculateNpApi,
  type CalendarDetailResponse,
} from '@/lib/stats';

// ── Tipos ─────────────────────────────────────────────────────────────────────
type View = 'month' | 'year';

// ── Constantes ────────────────────────────────────────────────────────────────
const MONTHS = [
  'Enero','Febrero','Marzo','Abril','Mayo','Junio',
  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre',
];
const MONTHS_S = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
const DAYS_S = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'];

// ── Helpers de fecha ──────────────────────────────────────────────────────────
function toDS(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function isToday(d: Date): boolean { return toDS(d) === toDS(new Date()); }

function monthWeeks(year: number, month: number): Date[][] {
  const first = new Date(year, month, 1);
  const last  = new Date(year, month + 1, 0);
  const back  = first.getDay() === 0 ? 6 : first.getDay() - 1;
  const cur   = new Date(year, month, 1 - back);
  const weeks: Date[][] = [];
  while (cur <= last) {
    const wk: Date[] = [];
    for (let i = 0; i < 7; i++) { wk.push(new Date(cur)); cur.setDate(cur.getDate() + 1); }
    weeks.push(wk);
  }
  return weeks;
}

// ── Helpers de formato ────────────────────────────────────────────────────────
function fmtKm(m: number): string { return (m / 1000).toFixed(1); }
function fmtDur(s: number): string {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h > 0 ? `${h}h ${String(m).padStart(2,'0')}m` : `${m}min`;
}
function fmtDurShort(s: number): string {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return `${h}:${String(m).padStart(2,'0')}`;
}

// ── Colores ───────────────────────────────────────────────────────────────────
const SPORT_COLOR: [string, string][] = [
  ['cycling','bg-blue-500'], ['running','bg-emerald-500'],
  ['swimming','bg-cyan-500'], ['hiking','bg-amber-500'], ['walking','bg-lime-500'],
];
function sBg(s: string | null): string {
  if (!s) return 'bg-slate-400';
  const m = SPORT_COLOR.find(([k]) => s.toLowerCase().includes(k));
  return m ? m[1] : 'bg-violet-500';
}

function heatBg(durS: number): string {
  if (durS === 0)    return 'bg-slate-100';
  if (durS < 1800)   return 'bg-blue-100';
  if (durS < 3600)   return 'bg-blue-300';
  if (durS < 7200)   return 'bg-blue-500';
  return 'bg-blue-700';
}

// ── Estadísticas de periodo ───────────────────────────────────────────────────
interface PS { activities: number; distM: number; durS: number; cal: number; tss: number; IF: number | null; }

function computePS(data: CalendarDetailResponse, days: Date[]): PS {
  let activities = 0, distM = 0, durS = 0, cal = 0, tss = 0, np2d = 0, nd = 0;
  for (const d of days) {
    for (const a of (data.days[toDS(d)] ?? [])) {
      activities++;
      distM += a.distance_m ?? 0;
      durS  += a.duration_s ?? 0;
      cal   += a.calories ?? 0;
      tss   += a.tss ?? 0;
      if (a.normalized_power != null && a.duration_s) {
        np2d += a.normalized_power * a.normalized_power * a.duration_s;
        nd   += a.duration_s;
      }
    }
  }
  const IF = nd > 0 && np2d > 0 && data.ftp > 0 ? Math.sqrt(np2d / nd) / data.ftp : null;
  return { activities, distM, durS, cal, tss, IF };
}

// ── SummaryBar ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex min-w-[6.5rem] flex-col items-center rounded-xl border border-slate-200 bg-white px-4 py-2 shadow-sm">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      <span className="mt-0.5 text-xl font-bold text-slate-800">{value}</span>
      {sub && <span className="text-xs text-slate-400">{sub}</span>}
    </div>
  );
}

function SummaryBar({ ps, ftp }: { ps: PS; ftp: number }) {
  return (
    <div className="flex flex-wrap gap-3">
      <StatCard label="Actividades" value={String(ps.activities)} />
      <StatCard label="Distancia"   value={`${fmtKm(ps.distM)} km`} />
      <StatCard label="Tiempo"      value={fmtDur(ps.durS)} />
      <StatCard label="Calorías"    value={ps.cal > 0 ? ps.cal.toLocaleString() : '—'} />
      {ps.tss > 0 && (
        <StatCard
          label="TSS"
          value={ps.tss.toFixed(0)}
          sub={ps.IF != null ? `IF ${ps.IF.toFixed(2)}` : `FTP ${ftp}W`}
        />
      )}
    </div>
  );
}

// ── VISTA MES ─────────────────────────────────────────────────────────────────
function WeekSummaryCell({ ps }: { ps: PS }) {
  if (ps.activities === 0) {
    return <td className="w-44 border-l border-slate-100 bg-slate-50/50 px-2 py-1 align-middle text-center"><span className="text-xs text-slate-200">—</span></td>;
  }
  return (
    <td className="w-44 border-l border-slate-100 bg-blue-50/40 px-2 py-1 align-top">
      <div className="space-y-0.5 text-xs">
        <div className="flex justify-between"><span className="text-slate-400">Dist</span><span className="font-medium text-slate-700">{fmtKm(ps.distM)} km</span></div>
        <div className="flex justify-between"><span className="text-slate-400">Tiempo</span><span className="font-medium text-slate-700">{fmtDurShort(ps.durS)}</span></div>
        <div className="flex justify-between"><span className="text-slate-400">Cal</span><span className="font-medium text-slate-700">{ps.cal > 0 ? ps.cal.toLocaleString() : '—'}</span></div>
        {ps.tss > 0 && (
          <>
            <div className="my-0.5 border-t border-slate-200" />
            <div className="flex justify-between"><span className="text-slate-400">TSS</span><span className="font-semibold text-blue-700">{ps.tss.toFixed(0)}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">IF</span><span className="font-semibold text-blue-700">{ps.IF ? ps.IF.toFixed(2) : '—'}</span></div>
          </>
        )}
      </div>
    </td>
  );
}

function MonthView({ anchor, data }: { anchor: Date; data: CalendarDetailResponse }) {
  const year  = anchor.getFullYear();
  const month = anchor.getMonth();
  const weeks = monthWeeks(year, month);
  const ps    = computePS(data, weeks.flat().filter(d => d.getMonth() === month));

  return (
    <div className="space-y-4">
      <SummaryBar ps={ps} ftp={data.ftp} />
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {DAYS_S.map(d => (
                <th key={d} className="w-[12%] py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-400">{d}</th>
              ))}
              <th className="w-44 border-l border-slate-200 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-400">Semana</th>
            </tr>
          </thead>
          <tbody>
            {weeks.map((wk, wi) => {
              const wkPS = computePS(data, wk);
              return (
                <tr key={wi} className="border-b border-slate-100 last:border-0">
                  {wk.map((day, di) => {
                    const inMonth = day.getMonth() === month;
                    const acts    = data.days[toDS(day)] ?? [];
                    return (
                      <td key={di} className={`min-h-[80px] align-top p-1.5 ${inMonth ? '' : 'bg-slate-50/60'}`}>
                        <div className="flex flex-col gap-0.5">
                          <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-medium ${
                            isToday(day) ? 'bg-blue-600 text-white'
                            : inMonth    ? 'text-slate-600'
                            : 'text-slate-300'
                          }`}>
                            {day.getDate()}
                          </span>
                          {acts.map(act => (
                            <Link
                              key={act.id}
                              to={`/activities/${act.id}`}
                              title={`${act.name ?? act.sport ?? 'Actividad'}${act.distance_m ? ` · ${fmtKm(act.distance_m)} km` : ''}${act.tss ? ` · TSS ${act.tss.toFixed(0)}` : ''}`}
                              className="flex items-center gap-1 rounded px-0.5 py-px hover:bg-slate-100"
                            >
                              <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${sBg(act.sport)}`} />
                              <span className="truncate text-xs text-slate-500">
                                {act.distance_m != null ? `${fmtKm(act.distance_m)} km` : '—'}
                              </span>
                            </Link>
                          ))}
                        </div>
                      </td>
                    );
                  })}
                  <WeekSummaryCell ps={wkPS} />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── VISTA AÑO ─────────────────────────────────────────────────────────────────
function MiniMonth({
  year, month, data, onDayClick,
}: {
  year: number; month: number;
  data: CalendarDetailResponse;
  onDayClick: (d: Date) => void;
}) {
  const weeks = monthWeeks(year, month);
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">{MONTHS[month]}</p>
      <div className="mb-0.5 grid grid-cols-7 gap-px">
        {DAYS_S.map(d => (
          <span key={d} className="text-center text-[9px] font-medium text-slate-300">{d[0]}</span>
        ))}
      </div>
      <div className="space-y-px">
        {weeks.map((wk, wi) => (
          <div key={wi} className="grid grid-cols-7 gap-px">
            {wk.map((day, di) => {
              if (day.getMonth() !== month) return <span key={di} />;
              const acts = data.days[toDS(day)] ?? [];
              const durS = acts.reduce((s, a) => s + (a.duration_s ?? 0), 0);
              const nActs = acts.length;
              return (
                <button
                  key={di}
                  title={
                    nActs > 0
                      ? `${day.getDate()} ${MONTHS_S[month]}: ${nActs} actividad${nActs > 1 ? 'es' : ''} · ${fmtKm(acts.reduce((s,a)=>s+(a.distance_m??0),0))} km`
                      : `${day.getDate()} ${MONTHS_S[month]}`
                  }
                  onClick={() => onDayClick(day)}
                  className={`h-[18px] w-full rounded-[3px] transition-opacity hover:opacity-75 ${
                    isToday(day) ? 'ring-1 ring-offset-[1px] ring-blue-500' : ''
                  } ${heatBg(durS)}`}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function YearView({
  year, data, onDayClick,
}: {
  year: number; data: CalendarDetailResponse; onDayClick: (d: Date) => void;
}) {
  const allDays: Date[] = [];
  for (let m = 0; m < 12; m++) {
    const daysInMonth = new Date(year, m + 1, 0).getDate();
    for (let d = 1; d <= daysInMonth; d++) allDays.push(new Date(year, m, d));
  }
  const ps = computePS(data, allDays);

  return (
    <div className="space-y-4">
      <SummaryBar ps={ps} ftp={data.ftp} />
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 12 }, (_, m) => (
            <MiniMonth key={m} year={year} month={m} data={data} onDayClick={onDayClick} />
          ))}
        </div>
        {/* Leyenda */}
        <div className="mt-5 flex items-center gap-1.5 text-xs text-slate-400">
          <span>Menos</span>
          {[0, 1800, 3600, 7200, 10800].map((dur, i) => (
            <span key={i} className={`h-3 w-3 rounded-[2px] ${heatBg(dur)}`} />
          ))}
          <span>Más</span>
          <span className="ml-3 text-slate-300">· Haz clic en un día para ver su semana</span>
        </div>
      </div>
    </div>
  );
}

// ── PÁGINA PRINCIPAL ──────────────────────────────────────────────────────────
export default function CalendarPage() {
  const [view, setView]     = useState<View>('month');
  const [anchor, setAnchor] = useState(new Date());
  const [msg, setMsg]       = useState<string | null>(null);

  const year = anchor.getFullYear();

  const { data, isLoading, error } = useQuery({
    queryKey: ['calendar-detail', year],
    queryFn: () => getCalendarDetailApi(year),
  });

  function navigate(delta: number) {
    const d = new Date(anchor);
    if (view === 'month') d.setMonth(d.getMonth() + delta);
    else d.setFullYear(d.getFullYear() + delta);
    setAnchor(d);
  }

  function navTitle(): string {
    if (view === 'month') return `${MONTHS[anchor.getMonth()]} ${anchor.getFullYear()}`;
    return String(anchor.getFullYear());
  }

  function handleDayClick(d: Date) {
    setAnchor(d);
    setView('month');
  }

  async function handleRecalc() {
    try {
      const r = await recalculateNpApi();
      setMsg(r.message);
      setTimeout(() => setMsg(null), 5000);
    } catch {
      setMsg('Error al lanzar el recálculo.');
    }
  }

  return (
    <div className="space-y-4">
      {/* ── Cabecera ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-800">Calendario</h1>
        {/* Selector de vista */}
        <div className="flex items-center gap-0.5 rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm">
          {(['month','year'] as View[]).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === v ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {v === 'month' ? 'Mes' : 'Año'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Navegación ── */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          aria-label="Anterior"
        >
          ‹
        </button>
        <span className="text-base font-semibold text-slate-700">{navTitle()}</span>
        <button
          onClick={() => navigate(1)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          aria-label="Siguiente"
        >
          ›
        </button>
      </div>

      {isLoading && <p className="py-8 text-center text-sm text-slate-400">Cargando…</p>}
      {error    && <p className="text-sm text-red-500">Error al cargar los datos.</p>}

      {/* ── Vistas ── */}
      {data && view === 'month' && <MonthView anchor={anchor} data={data} />}
      {data && view === 'year'  && <YearView  year={year}    data={data} onDayClick={handleDayClick} />}

      {/* ── Recalcular NP ── */}
      <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
        <div>
          <p className="font-medium text-slate-700">Normalized Power · TSS · IF</p>
          <p className="text-xs text-slate-400">
            Recalcula las métricas de entrenamiento para todas tus actividades con tu peso y FTP actuales.
          </p>
        </div>
        <button
          onClick={handleRecalc}
          className="ml-auto flex-shrink-0 rounded-md border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
        >
          Recalcular
        </button>
        {msg && <span className="text-xs text-green-600">{msg}</span>}
      </div>
    </div>
  );
}
