import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { logoutApi } from '@/lib/auth';

export default function Layout() {
  const { user, token, logout } = useAuthStore();
  const navigate = useNavigate();

  async function handleLogout() {
    if (token) await logoutApi(token).catch(() => {});
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/activities" className="text-lg font-semibold text-slate-800 hover:text-slate-600">
            fit-app
          </Link>
          <nav className="flex gap-4">
            <Link to="/activities" className="text-sm text-slate-600 hover:text-slate-900">
              Actividades
            </Link>
            <Link to="/stats" className="text-sm text-slate-600 hover:text-slate-900">
              Estadísticas
            </Link>
          </nav>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-500">{user?.email}</span>
            <button
              onClick={handleLogout}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
