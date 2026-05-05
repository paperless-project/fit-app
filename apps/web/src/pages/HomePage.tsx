import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export default function HomePage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['health'],
    queryFn: () => api<{ status: string; version: string }>('/health'),
  });

  return (
    <div className="space-y-4">
      <p className="text-slate-600">
        Aplicación para visualizar actividades ciclistas almacenadas en formato FIT.
      </p>
      <div className="rounded-md border border-slate-200 bg-white p-4">
        <h2 className="mb-2 font-medium">Estado del backend</h2>
        {isLoading && <p className="text-slate-500">Comprobando…</p>}
        {error && <p className="text-red-600">Error: {(error as Error).message}</p>}
        {data && (
          <p className="text-slate-700">
            <span className="font-mono">{data.status}</span> · v{data.version}
          </p>
        )}
      </div>
    </div>
  );
}
