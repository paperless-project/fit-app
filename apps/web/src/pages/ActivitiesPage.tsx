import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getActivitiesApi, uploadActivityApi, ApiError } from '@/lib/activities';
import type { Activity } from '@/types/activity';

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es-ES', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
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

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleSubmit() {
    if (!selectedFile) return;
    mutation.mutate(selectedFile);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800">Subir actividad FIT</h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        {/* Drop zone */}
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
            dragging
              ? 'border-blue-500 bg-blue-50'
              : 'border-slate-300 hover:border-slate-400'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".fit"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
          {selectedFile ? (
            <p className="text-sm font-medium text-slate-700">{selectedFile.name}</p>
          ) : (
            <>
              <p className="text-slate-500">Arrastra un fichero .fit aquí</p>
              <p className="mt-1 text-xs text-slate-400">o haz clic para seleccionarlo</p>
            </>
          )}
        </div>

        {errorMsg && (
          <p className="mt-3 text-sm text-red-600">{errorMsg}</p>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={!selectedFile || mutation.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
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
      <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-500">
        {fmtDate(activity.started_at)}
      </td>
      <td className="px-4 py-3">
        <p className="text-sm font-medium text-slate-800">
          {activity.name ?? fmtSport(activity.sport)}
        </p>
        {activity.name && (
          <p className="text-xs text-slate-400">{fmtSport(activity.sport)}</p>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtKm(activity.distance_m)}</td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {fmtDuration(activity.moving_time_s ?? activity.duration_s)}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {fmtInt(activity.ascent_m != null ? Math.round(activity.ascent_m) : null, 'm')}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">{fmtSpeed(activity.avg_speed_mps)}</td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {fmtInt(activity.avg_hr, 'bpm')}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {fmtInt(activity.calories, 'kcal')}
      </td>
    </tr>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ActivitiesPage() {
  const [showUpload, setShowUpload] = useState(false);

  const { data: activities, isLoading, isError } = useQuery({
    queryKey: ['activities'],
    queryFn: getActivitiesApi,
  });

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

      {isLoading && (
        <p className="text-sm text-slate-500">Cargando actividades…</p>
      )}

      {isError && (
        <p className="text-sm text-red-600">Error al cargar las actividades.</p>
      )}

      {!isLoading && !isError && activities?.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 py-16 text-center">
          <p className="text-slate-500">Aún no tienes actividades.</p>
          <p className="mt-1 text-sm text-slate-400">
            Sube tu primer fichero .fit con el botón de arriba.
          </p>
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
              {activities.map((a) => (
                <ActivityRow key={a.id} activity={a} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onSuccess={() => setShowUpload(false)}
        />
      )}
    </div>
  );
}
