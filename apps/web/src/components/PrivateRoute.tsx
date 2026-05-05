import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

export default function PrivateRoute() {
  const { token, isInitialized } = useAuthStore();

  if (!isInitialized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="text-slate-500">Cargando…</span>
      </div>
    );
  }

  return token ? <Outlet /> : <Navigate to="/login" replace />;
}
