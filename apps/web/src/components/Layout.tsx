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
            <Link to="/calendar" className="text-sm text-slate-600 hover:text-slate-900">
              Calendario
            </Link>
          </nav>
          <div className="flex items-center gap-4">
            {user && (!user.birth_date || !user.gender) && (
              <Link
                to="/account"
                title="Faltan datos de perfil"
                className="relative flex items-center text-amber-500 hover:text-amber-600"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                <span className="ml-1 text-xs font-medium">Faltan datos</span>
              </Link>
            )}
            <Link to="/account" className="text-sm text-slate-500 hover:text-slate-800">
              {user?.email}
            </Link>
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
