import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  sendOTPApi,
  verifyOTPApi,
  completeRegistrationApi,
  completeGoogleRegistrationApi,
  getMeApi,
} from '@/lib/auth';
import { useAuthStore } from '@/store/authStore';
import { ApiError } from '@/lib/api';
import type { Gender } from '@/types/user';

type Step = 'email' | 'otp' | 'profile';

const GENDER_OPTIONS: { value: Gender; label: string }[] = [
  { value: 'hombre', label: 'Hombre' },
  { value: 'mujer', label: 'Mujer' },
  { value: 'no_binario', label: 'No binario' },
  { value: 'prefiero_no_decirlo', label: 'Prefiero no decirlo' },
  { value: 'otro', label: 'Otro' },
];

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

const INPUT_CLS =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500';
const LABEL_CLS = 'mb-1 block text-sm font-medium text-slate-700';
const BTN_PRIMARY =
  'w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50';

export default function RegisterPage() {
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();

  const googleToken = searchParams.get('google_token') ?? '';
  const isGoogleFlow = !!googleToken;

  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [verifiedToken, setVerifiedToken] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [gender, setGender] = useState<Gender | ''>('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Flujo Google: auto-completar cuenta al montar el componente
  useEffect(() => {
    if (!isGoogleFlow) return;
    setLoading(true);
    completeGoogleRegistrationApi(googleToken)
      .then(({ access_token }) => getMeApi(access_token).then((user) => {
        setAuth(access_token, user);
        navigate('/activities', { replace: true });
      }))
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : 'Error al crear la cuenta con Google.');
        setLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Paso 1: enviar OTP ────────────────────────────────────────────────────

  async function handleSendOTP(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await sendOTPApi(email);
      setStep('otp');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error al enviar el código.');
    } finally {
      setLoading(false);
    }
  }

  async function handleResendOTP() {
    setError('');
    setLoading(true);
    try {
      await sendOTPApi(email);
      setOtpCode('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error al reenviar el código.');
    } finally {
      setLoading(false);
    }
  }

  // ── Paso 2: verificar OTP ─────────────────────────────────────────────────

  async function handleVerifyOTP(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const token = await verifyOTPApi(email, otpCode);
      setVerifiedToken(token);
      setStep('profile');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Código incorrecto o expirado.');
    } finally {
      setLoading(false);
    }
  }

  // ── Paso 3: completar perfil ──────────────────────────────────────────────

  async function handleCompleteProfile(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!gender) { setError('Selecciona tu género.'); return; }
    if (password !== confirm) { setError('Las contraseñas no coinciden.'); return; }
    if (password.length < 8) { setError('La contraseña debe tener al menos 8 caracteres.'); return; }
    setLoading(true);
    try {
      await completeRegistrationApi({
        verified_token: verifiedToken,
        first_name: firstName,
        last_name: lastName,
        birth_date: birthDate,
        gender,
        password,
      });
      navigate('/login', { replace: true, state: { registered: true } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error al crear la cuenta.');
    } finally {
      setLoading(false);
    }
  }

  // ── Botón Google ──────────────────────────────────────────────────────────

  async function handleGoogleRegister() {
    try {
      const params = new URLSearchParams({ flow: 'register' });
      ['openid', 'email', 'profile'].forEach((s) => params.append('scopes', s));
      const res = await fetch(`${BASE_URL}/auth/google/authorize?${params}`, { credentials: 'include' });
      if (!res.ok) throw new Error(await res.text());
      const { authorization_url } = await res.json();
      window.location.href = authorization_url;
    } catch {
      setError('No se pudo iniciar el registro con Google.');
    }
  }

  // ── Pantalla de carga para flujo Google ───────────────────────────────────

  if (isGoogleFlow) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm text-center">
          {loading ? (
            <>
              <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
              <p className="text-sm text-slate-500">Creando tu cuenta…</p>
            </>
          ) : (
            <>
              <p className="mb-4 text-sm text-red-600">{error}</p>
              <Link to="/login" className="text-sm text-blue-600 hover:underline">Volver al inicio</Link>
            </>
          )}
        </div>
      </div>
    );
  }

  // ── Render flujo email ────────────────────────────────────────────────────

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-center text-2xl font-semibold text-slate-800">Crear cuenta</h1>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        {/* ── Paso 1: email ── */}
        {step === 'email' && (
          <>
            <form onSubmit={handleSendOTP} className="space-y-4">
              <div>
                <label className={LABEL_CLS}>Email</label>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={INPUT_CLS}
                />
              </div>
              <button type="submit" disabled={loading} className={BTN_PRIMARY}>
                {loading ? 'Enviando…' : 'Enviar código'}
              </button>
            </form>

            <div className="relative my-5">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200" />
              </div>
              <div className="relative flex justify-center text-xs text-slate-400">
                <span className="bg-white px-2">o regístrate con</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleGoogleRegister}
              className="flex w-full items-center justify-center gap-3 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Registrarse con Google
            </button>
          </>
        )}

        {/* ── Paso 2: OTP ── */}
        {step === 'otp' && (
          <form onSubmit={handleVerifyOTP} className="space-y-4">
            <p className="text-sm text-slate-600">
              Hemos enviado un código de 6 dígitos a <strong>{email}</strong>.
            </p>
            <div>
              <label className={LABEL_CLS}>Código de verificación</label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                required
                autoFocus
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className={`${INPUT_CLS} text-center tracking-widest text-lg`}
                placeholder="000000"
              />
            </div>
            <button type="submit" disabled={loading || otpCode.length < 6} className={BTN_PRIMARY}>
              {loading ? 'Verificando…' : 'Verificar código'}
            </button>
            <p className="text-center text-sm text-slate-500">
              ¿No has recibido el código?{' '}
              <button
                type="button"
                onClick={handleResendOTP}
                disabled={loading}
                className="text-blue-600 hover:underline disabled:opacity-50"
              >
                Reenviar
              </button>
            </p>
            <button
              type="button"
              onClick={() => { setStep('email'); setOtpCode(''); setError(''); }}
              className="w-full text-center text-sm text-slate-400 hover:text-slate-600"
            >
              ← Cambiar email
            </button>
          </form>
        )}

        {/* ── Paso 3: perfil ── */}
        {step === 'profile' && (
          <form onSubmit={handleCompleteProfile} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={LABEL_CLS}>Nombre</label>
                <input type="text" required value={firstName} onChange={(e) => setFirstName(e.target.value)} className={INPUT_CLS} />
              </div>
              <div>
                <label className={LABEL_CLS}>Apellidos</label>
                <input type="text" required value={lastName} onChange={(e) => setLastName(e.target.value)} className={INPUT_CLS} />
              </div>
            </div>
            <div>
              <label className={LABEL_CLS}>Fecha de nacimiento</label>
              <input type="date" required value={birthDate} onChange={(e) => setBirthDate(e.target.value)} className={INPUT_CLS} />
            </div>
            <div>
              <label className={LABEL_CLS}>Género</label>
              <select required value={gender} onChange={(e) => setGender(e.target.value as Gender)} className={INPUT_CLS}>
                <option value="" disabled>Selecciona…</option>
                {GENDER_OPTIONS.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Contraseña</label>
              <input type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className={INPUT_CLS} />
            </div>
            <div>
              <label className={LABEL_CLS}>Confirmar contraseña</label>
              <input type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} className={INPUT_CLS} />
            </div>
            <button type="submit" disabled={loading} className={BTN_PRIMARY}>
              {loading ? 'Creando cuenta…' : 'Crear cuenta'}
            </button>
          </form>
        )}

        <p className="mt-4 text-center text-sm text-slate-500">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="text-blue-600 hover:underline">Entra aquí</Link>
        </p>
      </div>
    </div>
  );
}
