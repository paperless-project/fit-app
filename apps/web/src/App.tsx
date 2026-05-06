import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { getMeApi } from '@/lib/auth';
import Layout from '@/components/Layout';
import PrivateRoute from '@/components/PrivateRoute';
import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import VerifyPage from '@/pages/VerifyPage';
import ActivitiesPage from '@/pages/ActivitiesPage'
import ActivityDetailPage from '@/pages/ActivityDetailPage';
import StatsPage from '@/pages/StatsPage';

export default function App() {
  const { token, setUser, setInitialized, logout } = useAuthStore();

  // Al arrancar: si hay token en localStorage, verificarlo contra /users/me
  useEffect(() => {
    if (!token) {
      setInitialized();
      return;
    }
    getMeApi(token)
      .then(setUser)
      .catch(() => logout())
      .finally(setInitialized);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Routes>
      {/* Rutas públicas */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify" element={<VerifyPage />} />

      {/* Rutas privadas */}
      <Route element={<PrivateRoute />}>
        <Route element={<Layout />}>
          <Route path="/activities" element={<ActivitiesPage />} />
          <Route path="/activities/:id" element={<ActivityDetailPage />} />
          <Route path="/stats" element={<StatsPage />} />
          <Route path="/" element={<Navigate to="/activities" replace />} />
        </Route>
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
