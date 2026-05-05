import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { verifyEmailApi } from '@/lib/auth';

type Status = 'verifying' | 'success' | 'error' | 'missing';

export default function VerifyPage() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<Status>('verifying');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('missing');
      return;
    }
    verifyEmailApi(token)
      .then(() => setStatus('success'))
      .catch(() => setStatus('error'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm text-center">
        <h1 className="mb-6 text-2xl font-semibold text-slate-800">fit-app</h1>

        {status === 'verifying' && (
          <p className="text-slate-500">Verificando tu correo…</p>
        )}

        {status === 'success' && (
          <>
            <div className="mb-4 text-5xl">✓</div>
            <p className="mb-2 font-medium text-slate-800">¡Correo verificado!</p>
            <p className="mb-6 text-sm text-slate-500">
              Tu cuenta está activa. Ya puedes iniciar sesión.
            </p>
            <Link
              to="/login"
              className="inline-block w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Ir al inicio de sesión
            </Link>
          </>
        )}

        {(status === 'error' || status === 'missing') && (
          <>
            <div className="mb-4 text-5xl">✗</div>
            <p className="mb-2 font-medium text-slate-800">Enlace no válido</p>
            <p className="mb-6 text-sm text-slate-500">
              El enlace ha caducado o ya fue utilizado. Inicia sesión y solicita uno nuevo.
            </p>
            <Link
              to="/login"
              className="inline-block w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Ir al inicio de sesión
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
