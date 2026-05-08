import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { logoutApi } from '@/lib/auth';
import { changePasswordApi, deleteAccountApi, deleteAllActivitiesApi, updateTrainingProfileApi } from '@/lib/account';
import { ApiError } from '@/lib/api';
import { connectStrava, disconnectStrava, getStravaStatus, startStravaImport } from '@/lib/strava';

// ── Cambio de contraseña ──────────────────────────────────────────────────────

function ChangePasswordSection() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (next !== confirm) {
      setError('Las contraseñas nuevas no coinciden.');
      return;
    }
    if (next.length < 8) {
      setError('La nueva contraseña debe tener al menos 8 caracteres.');
      return;
    }

    setLoading(true);
    try {
      await changePasswordApi(current, next);
      setSuccess(true);
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setError('La contraseña actual es incorrecta.');
      } else {
        setError('Error al cambiar la contraseña. Inténtalo de nuevo.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-base font-semibold text-slate-800">Cambiar contraseña</h2>
      <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-600">
            Contraseña actual
          </label>
          <input
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-600">
            Nueva contraseña
          </label>
          <input
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
            minLength={8}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-600">
            Confirmar nueva contraseña
          </label>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {success && <p className="text-sm text-green-600">Contraseña actualizada correctamente.</p>}

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Guardando…' : 'Cambiar contraseña'}
        </button>
      </form>
    </section>
  );
}

// ── Modal de borrado de todas las actividades ─────────────────────────────────

function DeleteAllActivitiesModal({ onClose }: { onClose: () => void }) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();

  async function handleDelete() {
    if (input !== 'BORRAR') return;
    setLoading(true);
    setError(null);
    try {
      await deleteAllActivitiesApi();
      await qc.invalidateQueries({ queryKey: ['activities'] });
      onClose();
    } catch {
      setError('Error al borrar las actividades. Inténtalo de nuevo.');
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-red-700">Borrar todas las actividades</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Cerrar">
            ✕
          </button>
        </div>

        <p className="mb-4 text-sm text-slate-600">
          Esta acción es <strong>irreversible</strong>. Se eliminarán todas tus actividades,
          incluyendo los datos GPS, potencia y estadísticas. Para confirmar, escribe{' '}
          <strong>BORRAR</strong> en el campo de abajo.
        </p>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="BORRAR"
          className="mb-4 w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
        />

        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            Cancelar
          </button>
          <button
            onClick={handleDelete}
            disabled={input !== 'BORRAR' || loading}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? 'Borrando…' : 'Borrar todas las actividades'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Modal de confirmación de borrado ──────────────────────────────────────────

function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { token, logout } = useAuthStore();
  const navigate = useNavigate();

  async function handleDelete() {
    if (input !== 'BORRAR') return;
    setLoading(true);
    setError(null);
    try {
      if (token) await logoutApi(token).catch(() => {});
      await deleteAccountApi();
      logout();
      navigate('/login', { replace: true });
    } catch {
      setError('Error al borrar la cuenta. Inténtalo de nuevo.');
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-red-700">Borrar cuenta</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Cerrar">
            ✕
          </button>
        </div>

        <p className="mb-4 text-sm text-slate-600">
          Esta acción es <strong>irreversible</strong>. Se eliminarán tu cuenta y todas tus
          actividades. Para confirmar, escribe <strong>BORRAR</strong> en el campo de abajo.
        </p>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="BORRAR"
          className="mb-4 w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
        />

        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            Cancelar
          </button>
          <button
            onClick={handleDelete}
            disabled={input !== 'BORRAR' || loading}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? 'Borrando…' : 'Borrar cuenta definitivamente'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Perfil de entrenamiento ───────────────────────────────────────────────────

function TrainingProfileSection() {
  const { user, setUser } = useAuthStore();
  const [ftp, setFtp] = useState<string>(user?.ftp != null ? String(user.ftp) : '');
  const [weight, setWeight] = useState<string>(user?.weight_kg != null ? String(user.weight_kg) : '');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    const ftpVal = ftp ? parseInt(ftp, 10) : null;
    const weightVal = weight ? parseFloat(weight) : null;

    if (ftpVal !== null && (ftpVal < 50 || ftpVal > 600)) {
      setError('El FTP debe estar entre 50 y 600 W.');
      return;
    }
    if (weightVal !== null && (weightVal < 30 || weightVal > 250)) {
      setError('El peso debe estar entre 30 y 250 kg.');
      return;
    }

    setLoading(true);
    try {
      const updated = await updateTrainingProfileApi(ftpVal, weightVal);
      setUser(updated);
      setSuccess(true);
    } catch {
      setError('Error al guardar el perfil de entrenamiento.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-1 text-base font-semibold text-slate-800">Perfil de entrenamiento</h2>
      <p className="mb-4 text-xs text-slate-400">
        Usado para calcular TSS e IF en el calendario y para estimar potencia en actividades
        sin medidor.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-600">
            FTP — Potencia Umbral Funcional (W)
          </label>
          <input
            type="number"
            min={50}
            max={600}
            placeholder="200"
            value={ftp}
            onChange={e => setFtp(e.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <p className="mt-1 text-xs text-slate-400">
            Si no lo conoces, deja en blanco (se usarán 200 W por defecto).
          </p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-600">
            Peso corporal (kg)
          </label>
          <input
            type="number"
            min={30}
            max={250}
            step={0.1}
            placeholder="75"
            value={weight}
            onChange={e => setWeight(e.target.value)}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <p className="mt-1 text-xs text-slate-400">
            Se suma 10 kg de bicicleta para la estimación de potencia. Cambia el peso y
            pulsa «Recalcular» en el Calendario para actualizar NP en actividades anteriores.
          </p>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {success && <p className="text-sm text-green-600">Perfil guardado correctamente.</p>}

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Guardando…' : 'Guardar perfil'}
        </button>
      </form>
    </section>
  );
}

// ── Sección Strava ────────────────────────────────────────────────────────────

function StravaSection() {
  const qc = useQueryClient();
  const [connectError, setConnectError] = useState('');
  const prevStatusRef = useRef<string | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ['strava-status'],
    queryFn: getStravaStatus,
    refetchInterval: (query) => {
      const s = query.state.data?.import_status;
      return s === 'running' || s === 'rate_limited' || s === 'fetching_streams' ? 10_000 : false;
    },
  });

  // Invalidar lista de actividades en transiciones relevantes
  useEffect(() => {
    const prev = prevStatusRef.current;
    const curr = status?.import_status ?? null;
    const inProgress = (s: string | null) =>
      s === 'running' || s === 'rate_limited' || s === 'fetching_streams';
    // Al terminar fase 1 (running → fetching_streams): las actividades ya están visibles
    if (prev === 'running' && curr === 'fetching_streams') {
      qc.invalidateQueries({ queryKey: ['activities'] });
    }
    // Al completar todo: invalidar de nuevo por si llegaron streams nuevos
    if (inProgress(prev) && curr === 'completed') {
      qc.invalidateQueries({ queryKey: ['activities'] });
    }
    prevStatusRef.current = curr;
  }, [status?.import_status]);

  const syncMutation = useMutation({
    mutationFn: startStravaImport,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strava-status'] }),
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectStrava,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strava-status'] }),
  });

  async function handleConnect() {
    setConnectError('');
    try {
      await connectStrava();
    } catch {
      setConnectError('No se pudo iniciar la conexión con Strava. Inténtalo de nuevo.');
    }
  }

  if (isLoading) return null;

  const isRunning = status?.import_status === 'running';
  const isRateLimited = status?.import_status === 'rate_limited';
  const isFetchingStreams = status?.import_status === 'fetching_streams';
  const isBlocked = isRunning || isRateLimited || isFetchingStreams;

  function StatusBanner() {
    if (!status?.import_status) return null;
    switch (status.import_status) {
      case 'running':
        return (
          <div className="flex items-center gap-2 rounded-md bg-orange-50 border border-orange-200 px-3 py-2 text-sm text-orange-700">
            <svg className="h-4 w-4 shrink-0 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            Descargando lista de actividades de Strava…
          </div>
        );
      case 'fetching_streams':
        return (
          <div className="flex items-center gap-2 rounded-md bg-blue-50 border border-blue-200 px-3 py-2 text-sm text-blue-700">
            <svg className="h-4 w-4 shrink-0 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            {status.import_status_message ?? 'Descargando datos GPS en segundo plano…'}
          </div>
        );
      case 'rate_limited':
        return (
          <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-800">
            <span className="font-medium">Pausa por límite de Strava</span>
            <br />
            {status.import_status_message}
          </div>
        );
      case 'daily_limit':
        return (
          <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            <span className="font-medium">Límite diario alcanzado</span>
            <br />
            {status.import_status_message}
          </div>
        );
      case 'error':
        return (
          <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            <span className="font-medium">Error en la importación</span>
            <br />
            {status.import_status_message}
          </div>
        );
      case 'completed':
        return (
          <p className="text-xs text-green-700">
            Última sincronización: {status.last_import_at
              ? new Date(status.last_import_at).toLocaleString('es-ES')
              : '—'
            }
            {status.import_status_message && ` · ${status.import_status_message}`}
          </p>
        );
      default:
        return null;
    }
  }

  return (
    <section className="rounded-xl border border-orange-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center gap-3">
        <svg viewBox="0 0 24 24" className="h-6 w-6 fill-orange-500" xmlns="http://www.w3.org/2000/svg">
          <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169" />
        </svg>
        <h2 className="text-base font-semibold text-slate-800">Strava</h2>
      </div>

      {status?.connected ? (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Conectado
            {status.athlete_id && (
              <span className="ml-1 text-slate-400">(ID atleta: {status.athlete_id})</span>
            )}
          </p>

          <div className="space-y-3">
            <StatusBanner />
            {!status.import_status && status.last_import_at && (
              <p className="text-xs text-slate-400">
                Última sincronización: {new Date(status.last_import_at).toLocaleString('es-ES')}
              </p>
            )}
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending || isBlocked}
              className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white hover:bg-orange-600 disabled:opacity-50"
            >
              {syncMutation.isPending ? 'Iniciando…' : 'Actualizar desde Strava'}
            </button>
            {syncMutation.isError && (
              <p className="text-sm text-red-600">Error al iniciar la sincronización.</p>
            )}
          </div>

          <div className="border-t border-slate-100 pt-4">
            <button
              onClick={() => disconnectMutation.mutate()}
              disabled={disconnectMutation.isPending}
              className="text-sm text-slate-500 hover:text-red-600 disabled:opacity-50"
            >
              {disconnectMutation.isPending ? 'Desconectando…' : 'Desconectar Strava'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-slate-500">
            Conecta tu cuenta de Strava para importar actividades directamente.
          </p>
          <button
            onClick={handleConnect}
            className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white hover:bg-orange-600"
          >
            Conectar con Strava
          </button>
          {connectError && <p className="text-sm text-red-600">{connectError}</p>}
        </div>
      )}
    </section>
  );
}

// ── Zona de peligro ───────────────────────────────────────────────────────────

function DangerZone() {
  const [showDeleteActivities, setShowDeleteActivities] = useState(false);
  const [showDeleteAccount, setShowDeleteAccount] = useState(false);

  return (
    <section className="rounded-xl border border-red-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-base font-semibold text-red-700">Zona de peligro</h2>

      <div className="flex items-center justify-between border-b border-red-100 pb-4 mb-4">
        <div>
          <p className="text-sm font-medium text-slate-700">Borrar todas las actividades</p>
          <p className="text-xs text-slate-500">Elimina todos los registros GPS, potencia y estadísticas. La cuenta se conserva.</p>
        </div>
        <button
          onClick={() => setShowDeleteActivities(true)}
          className="ml-4 shrink-0 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
        >
          Borrar actividades
        </button>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-700">Borrar cuenta</p>
          <p className="text-xs text-slate-500">Elimina permanentemente tu cuenta y todas tus actividades.</p>
        </div>
        <button
          onClick={() => setShowDeleteAccount(true)}
          className="ml-4 shrink-0 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
        >
          Borrar cuenta
        </button>
      </div>

      {showDeleteActivities && <DeleteAllActivitiesModal onClose={() => setShowDeleteActivities(false)} />}
      {showDeleteAccount && <DeleteAccountModal onClose={() => setShowDeleteAccount(false)} />}
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AccountPage() {
  const { user } = useAuthStore();
  const [searchParams, setSearchParams] = useSearchParams();
  const [stravaNotice, setStravaNotice] = useState<{ type: 'ok' | 'error'; msg: string } | null>(null);

  useEffect(() => {
    if (searchParams.get('strava_connected')) {
      setStravaNotice({ type: 'ok', msg: 'Strava conectado correctamente.' });
      setSearchParams((p) => { p.delete('strava_connected'); return p; }, { replace: true });
    } else if (searchParams.get('strava_error')) {
      const err = searchParams.get('strava_error');
      setStravaNotice({ type: 'error', msg: `Error al conectar con Strava: ${err}.` });
      setSearchParams((p) => { p.delete('strava_error'); return p; }, { replace: true });
    }
  }, []);

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Mi cuenta</h1>
        {user && <p className="text-sm text-slate-400">{user.email}</p>}
      </div>
      {stravaNotice && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            stravaNotice.type === 'ok'
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {stravaNotice.msg}
        </div>
      )}
      <ChangePasswordSection />
      <TrainingProfileSection />
      <StravaSection />
      <DangerZone />
    </div>
  );
}
