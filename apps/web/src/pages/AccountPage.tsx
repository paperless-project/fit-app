import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { logoutApi } from '@/lib/auth';
import { changePasswordApi, deleteAccountApi } from '@/lib/account';
import { ApiError } from '@/lib/api';

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

// ── Zona de peligro ───────────────────────────────────────────────────────────

function DangerZone() {
  const [showModal, setShowModal] = useState(false);

  return (
    <section className="rounded-xl border border-red-200 bg-white p-6 shadow-sm">
      <h2 className="mb-1 text-base font-semibold text-red-700">Zona de peligro</h2>
      <p className="mb-4 text-sm text-slate-500">
        Borrar la cuenta elimina permanentemente todos tus datos y actividades.
      </p>
      <button
        onClick={() => setShowModal(true)}
        className="rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
      >
        Borrar cuenta
      </button>
      {showModal && <DeleteAccountModal onClose={() => setShowModal(false)} />}
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AccountPage() {
  const { user } = useAuthStore();

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Mi cuenta</h1>
        {user && <p className="text-sm text-slate-400">{user.email}</p>}
      </div>
      <ChangePasswordSection />
      <DangerZone />
    </div>
  );
}
