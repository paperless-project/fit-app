import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getActivityDetailApi, patchActivityApi, downloadGpxApi } from '@/lib/activities';
import ActivityMap from '@/components/ActivityMap';
import ActivityCharts from '@/components/ActivityCharts';
import type { ActivityDetail, LapPoint } from '@/types/activity';

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('es-ES', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });
}

function fmtDuration(s: number | null) {
  if (s == null) return '—';
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`;
}

function fmtKm(m: number | null) { return m != null ? `${(m / 1000).toFixed(2)} km` : '—'; }
function fmtSpeed(mps: number | null) { return mps != null ? `${(mps * 3.6).toFixed(1)} km/h` : '—'; }
function fmtInt(v: number | null, unit = '') { return v != null ? `${Math.round(v)} ${unit}`.trim() : '—'; }

// ── Stat card ─────────────────────────────────────────────────────────────────

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-4 py-3 text-center">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-lg font-semibold text-slate-800">{value}</p>
    </div>
  );
}

// ── Edit modal ────────────────────────────────────────────────────────────────

function EditModal({
  activity,
  onClose,
}: {
  activity: ActivityDetail;
  onClose: () => void;
}) {
  const [name, setName] = useState(activity.name ?? '');
  const [sport, setSport] = useState(activity.sport ?? '');
  const [notes, setNotes] = useState(activity.notes ?? '');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => patchActivityApi(activity.id, {
      name: name || null,
      sport: sport || null,
      notes: notes || null,
    }),
    onSuccess: (updated) => {
      queryClient.setQueryData(['activity', activity.id], (old: ActivityDetail) => ({
        ...old,
        name: updated.name,
        sport: updated.sport,
        notes: updated.notes,
      }));
      queryClient.invalidateQueries({ queryKey: ['activities'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800">Editar actividad</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Cerrar">✕</button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">Nombre</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nombre de la actividad"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">Deporte</label>
            <input
              type="text"
              value={sport}
              onChange={(e) => setSport(e.target.value)}
              placeholder="cycling, running, gravel…"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600">Notas</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Sensaciones, condiciones, equipo…"
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
        </div>

        {mutation.isError && (
          <p className="mt-3 text-sm text-red-600">Error al guardar los cambios.</p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">
            Cancelar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Laps table ────────────────────────────────────────────────────────────────

function LapsTable({ laps }: { laps: LapPoint[] }) {
  if (laps.length === 0) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <p className="border-b border-slate-100 px-4 py-2 text-sm font-medium text-slate-600">
        Vueltas ({laps.length})
      </p>
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2">Vuelta</th>
            <th className="px-4 py-2">Distancia</th>
            <th className="px-4 py-2">Duración</th>
            <th className="px-4 py-2">Vel. media</th>
            <th className="px-4 py-2">FC media</th>
            <th className="px-4 py-2">Desnivel</th>
          </tr>
        </thead>
        <tbody>
          {laps.map((lap) => (
            <tr key={lap.lap_index} className="border-t border-slate-100 hover:bg-slate-50">
              <td className="px-4 py-2 font-medium text-slate-700">{lap.lap_index + 1}</td>
              <td className="px-4 py-2 text-slate-600">{fmtKm(lap.distance_m)}</td>
              <td className="px-4 py-2 text-slate-600">{fmtDuration(lap.duration_s)}</td>
              <td className="px-4 py-2 text-slate-600">{fmtSpeed(lap.avg_speed_mps)}</td>
              <td className="px-4 py-2 text-slate-600">{fmtInt(lap.avg_hr, 'bpm')}</td>
              <td className="px-4 py-2 text-slate-600">{fmtInt(lap.ascent_m, 'm')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [showEdit, setShowEdit] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['activity', id],
    queryFn: () => getActivityDetailApi(id!),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-sm text-slate-500">Cargando actividad…</p>;
  if (isError || !data) return <p className="text-sm text-red-600">No se encontró la actividad.</p>;

  const title = data.name ?? (data.sport
    ? data.sport.charAt(0).toUpperCase() + data.sport.slice(1).toLowerCase()
    : data.file_name);

  async function handleDownloadGpx() {
    const filename = `${(data!.name || data!.file_name).replace(/ /g, '_')}.gpx`;
    await downloadGpxApi(data!.id, filename);
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button onClick={() => navigate('/activities')} className="mb-1 text-xs text-slate-400 hover:text-slate-600">
            ← Actividades
          </button>
          <h2 className="text-xl font-semibold text-slate-800">{title}</h2>
          <p className="text-sm text-slate-400">{fmtDate(data.started_at)}</p>
          {data.notes && (
            <p className="mt-1 text-sm italic text-slate-500">{data.notes}</p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={handleDownloadGpx}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Descargar GPX
          </button>
          <button
            onClick={() => setShowEdit(true)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Editar
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <Stat label="Distancia" value={fmtKm(data.distance_m)} />
        <Stat label="Duración" value={fmtDuration(data.moving_time_s ?? data.duration_s)} />
        <Stat label="Desnivel ↑" value={fmtInt(data.ascent_m != null ? Math.round(data.ascent_m) : null, 'm')} />
        <Stat label="Vel. media" value={fmtSpeed(data.avg_speed_mps)} />
        {data.avg_hr && <Stat label="FC media" value={fmtInt(data.avg_hr, 'bpm')} />}
        {data.avg_cadence && <Stat label="Cadencia" value={fmtInt(data.avg_cadence, 'rpm')} />}
        {data.calories && <Stat label="Calorías" value={fmtInt(data.calories, 'kcal')} />}
      </div>

      <ActivityMap records={data.records} hoverIdx={hoverIdx} />
      <ActivityCharts records={data.records} hoverIdx={hoverIdx} onHover={setHoverIdx} />
      <LapsTable laps={data.laps} />

      {showEdit && <EditModal activity={data} onClose={() => setShowEdit(false)} />}
    </div>
  );
}
