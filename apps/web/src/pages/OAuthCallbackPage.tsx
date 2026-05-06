import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getMeApi } from '@/lib/auth';
import { useAuthStore } from '@/store/authStore';

export default function OAuthCallbackPage() {
  const [params] = useSearchParams();
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    const token = params.get('access_token');
    if (!token) {
      navigate('/login', { replace: true });
      return;
    }
    getMeApi(token)
      .then((user) => {
        setAuth(token, user);
        navigate('/activities', { replace: true });
      })
      .catch(() => navigate('/login', { replace: true }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <p className="text-sm text-slate-500">Autenticando con Google…</p>
    </div>
  );
}
