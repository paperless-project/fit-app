import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getActivitiesApi,
  uploadActivityApi,
  downloadCsvApi,
  ApiError,
  type ActivityFilters,
} from '@/lib/activities';
import type { Activity } from '@/types/activity';

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  });
}

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`;
}

function fmtKm(meters: number | null): string {
  if (meters == null) return '—';
  return `${(meters / 1000).toFixed(2)} km`;
}

function fmtSpeed(mps: number | null): string {
  if (mps == null) return '—';
  return `${(mps * 3.6).toFixed(1)} km/h`;
}

function fmtInt(v: number | null, unit = ''): string {
  if (v == null) return '—';
  return unit ? `${v} ${unit}` : String(v);
}

function fmtSport(sport: string | null): string {
  if (!sport) return '—';
  return sport.charAt(0).toUpperCase() + sport.slice(1).toLowerCase();
}

// ── Filter bar ────────────────────────────────────────────────────────────────

function FilterBar({
  filters,
  sports,
  onChange,
  onExportCsv,
}: {
  filters: ActivityFilters;
  sports: string[];
  onChange: (f: ActivityFilters) => void;
  onExportCsv: () => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-500">Buscar</label>
        <input
          type="text"
          placeholder="Nombre de actividad"
          value={filters.q ?? ''}
          onChange={(e) => onChange({ ...filters, q: e.target.value || undefined })}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-500">Deporte</label>
        <select
          value={filters.sport ?? ''}
          onChange={(e) => onChange({ ...filters, sport: e.target.value || undefined })}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          <option value="">Todos</option>
          {sports.map((s) => (
            <option key={s} value={s}>{fmtSport(s)}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-500">Desde</label>
        <input
          type="date"
          value={filters.date_from ?? ''}
          onChange={(e) => onChange({ ...filters, date_from: e.target.value || undefined })}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-500">Hasta</label>
        <input
          type="date"
          value={filters.date_to ?? ''}
          onChange={(e) => onChange({ ...filters, date_to: e.target.value || undefined })}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </div>

      <button
        onClick={() => onChange({})}
        className="rounded-md px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100"
      >
        Limpiar
      </button>

      <div className="ml-auto">
        <button
          onClick={onExportCsv}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
        >
          Exportar CSV
        </button>
      </div>
    </div>
  );
}

// ── Upload modal ──────────────────────────────────────────────────────────────

function UploadModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (file: File) => uploadActivityApi(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activities'] });
      onSuccess();
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) {
        setErrorMsg('Esta actividad ya existe (duplicado).');
      } else if (err instanceof ApiError && err.status === 400) {
        setErrorMsg('Fichero FIT inválido o dañado.');
      } else {
        setErrorMsg('Error desconocido al subir el fichero.');
      }
    },
  });

  function handleFile(file: File) {
    setErrorMsg(null);
    setSelectedFile(file);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800">Subir actividad FIT</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Cerrar">✕</button>
        </div>

        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-slate-400'}`}
        >
          <input ref={inputRef} type="file" accept=".fit" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          {selectedFile
            ? <p className="text-sm font-medium text-slate-700">{selectedFile.name}</p>
            : <><p className="text-slate-500">Arrastra un fichero .fit aquí</p><p className="mt-1 text-xs text-slate-400">o haz clic para seleccionarlo</p></>
          }
        </div>

        {errorMsg && <p className="mt-3 text-sm text-red-600">{errorMsg}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">Cancelar</button>
          <button onClick={() => selectedFile && mutation.mutate(selectedFile)}
            disabled={!selectedFile || mutation.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {mutation.isPending ? 'Subiendo…' : 'Subir'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────────

function ActivityRow({ activity }: { activity: Activity }) {
  const navigate = useNavigate();
  return (
    <tr
      className="cursor-pointer border-b border-slate-100 hover:bg-blue-50"
      onClick={() => navigate(`/activities/${activity.id}`)}
    >
      <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-500">{fmtDate(activity.started_at)}</td>
      <td className="px-4 py-3">
        <p className="text-sm font-medium text-slate-800">{activity.name ?? fmtSport(activity.sport)}</p>
        {activity.name && <p className="text-xs text-slate-400">{fmtSport(activity.sport)}</p>}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtKm(activity.distance_m)}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtDuration(activity.moving_time_s ?? activity.duration_s)}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtInt(activity.ascent_m != null ? Math.round(activity.ascent_m) : null, 'm')}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtSpeed(activity.avg_speed_mps)}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtInt(activity.avg_hr, 'bpm')}</td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtInt(activity.calories, 'kcal')}</td>
    </tr>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ActivitiesPage() {
  const [showUpload, setShowUpload] = useState(false);
  const [filters, setFilters] = useState<ActivityFilters>({});

  const { data: activities, isLoading, isError } = useQuery({
    queryKey: ['activities', filters],
    queryFn: () => getActivitiesApi(filters),
  });

  const sports = [...new Set((activities ?? []).map((a) => a.sport).filter(Boolean) as string[])].sort();

  async function handleExportCsv() {
    await downloadCsvApi(filters);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-800">Actividades</h2>
        <button
          onClick={() => setShowUpload(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          + Subir actividad
        </button>
      </div>

      <FilterBar filters={filters} sports={sports} onChange={setFilters} onExportCsv={handleExportCsv} />

      {isLoading && <p className="text-sm text-slate-500">Cargando actividades…</p>}
      {isError && <p className="text-sm text-red-600">Error al cargar las actividades.</p>}

      {!isLoading && !isError && activities?.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 py-16 text-center">
          <p className="text-slate-500">No hay actividades con los filtros aplicados.</p>
        </div>
      )}

      {!isLoading && !isError && activities && activities.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">Actividad</th>
                <th className="px-4 py-3">Distancia</th>
                <th className="px-4 py-3">Duración</th>
                <th className="px-4 py-3">Desnivel</th>
                <th className="px-4 py-3">Vel. media</th>
                <th className="px-4 py-3">FC media</th>
                <th className="px-4 py-3">Calorías</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((a) => <ActivityRow key={a.id} activity={a} />)}
            </tbody>
          </table>
        </div>
      )}

      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onSuccess={() => setShowUpload(false)} />
      )}
    </div>
  );
}
