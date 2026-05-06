import { useEffect, useMemo, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  type ChartOptions,
  type Plugin,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import type { RecordPoint } from '@/types/activity';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface Props {
  records: RecordPoint[];
  hoverIdx: number | null;
  onHover: (idx: number | null) => void;
}

// ── Crosshair plugin ──────────────────────────────────────────────────────────

function makeCrosshair(getIdx: () => number | null): Plugin<'line'> {
  return {
    id: 'crosshair',
    afterDraw(chart) {
      const idx = getIdx();
      if (idx == null) return;
      const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
      const xPos = x.getPixelForValue(idx);
      ctx.save();
      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(xPos, top);
      ctx.lineTo(xPos, bottom);
      ctx.stroke();
      ctx.restore();
    },
  };
}

// ── Single chart component ────────────────────────────────────────────────────

interface ChartProps {
  label: string;
  color: string;
  fill: boolean;
  xLabels: number[];
  values: (number | null)[];
  unit: string;
  hoverIdx: number | null;
  onHover: (idx: number | null) => void;
}

function SingleChart({ label, color, fill, xLabels, values, unit, hoverIdx, onHover }: ChartProps) {
  const chartRef = useRef<ChartJS<'line'>>(null);
  const hoverRef = useRef<number | null>(hoverIdx);
  hoverRef.current = hoverIdx;

  // Trigger chart redraw when hoverIdx changes (crosshair)
  useEffect(() => {
    chartRef.current?.update('none');
  }, [hoverIdx]);

  const crosshair = useMemo(() => makeCrosshair(() => hoverRef.current), []);

  const data = {
    labels: xLabels,
    datasets: [
      {
        label,
        data: values,
        borderColor: color,
        backgroundColor: fill ? color + '22' : 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        fill,
        spanGaps: true,
        tension: 0.2,
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    onHover(_evt, elements) {
      onHover(elements.length > 0 ? elements[0].index : null);
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => items[0] ? `${(items[0].parsed.x as number).toFixed(2)} km` : '',
          label: (item) =>
            item.parsed.y != null ? `${label}: ${item.parsed.y.toFixed(1)} ${unit}` : '',
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        title: { display: false },
        ticks: { maxTicksLimit: 8, callback: (v) => `${Number(v).toFixed(1)}` },
        grid: { color: '#f1f5f9' },
      },
      y: {
        title: { display: true, text: unit, font: { size: 11 } },
        grid: { color: '#f1f5f9' },
        ticks: { maxTicksLimit: 5 },
      },
    },
  };

  return (
    <div className="h-28">
      <Line ref={chartRef} data={data} options={options} plugins={[crosshair]} />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ActivityCharts({ records, hoverIdx, onHover }: Props) {
  if (records.length === 0) return null;

  // X-axis: distance in km (use index if distance missing)
  const xKm = records.map((r, i) =>
    r.distance_m != null ? r.distance_m / 1000 : i / 60,
  );

  const altitudes = records.map((r) =>
    r.altitude_m != null ? Math.round(r.altitude_m) : null,
  );
  const speeds = records.map((r) =>
    r.speed_mps != null ? parseFloat((r.speed_mps * 3.6).toFixed(1)) : null,
  );
  const hrs = records.map((r) => r.heart_rate ?? null);
  const cadences = records.map((r) => r.cadence ?? null);
  const powers = records.map((r) => r.power ?? null);

  const hasHr = hrs.some((v) => v != null);
  const hasCadence = cadences.some((v) => v != null);
  const hasPower = powers.some((v) => v != null);

  const common = { xLabels: xKm, hoverIdx, onHover };

  return (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <SingleChart
        label="Altitud"
        color="#64748b"
        fill={true}
        values={altitudes}
        unit="m"
        {...common}
      />
      <SingleChart
        label="Velocidad"
        color="#3b82f6"
        fill={false}
        values={speeds}
        unit="km/h"
        {...common}
      />
      {hasHr && (
        <SingleChart
          label="FC"
          color="#ef4444"
          fill={false}
          values={hrs}
          unit="bpm"
          {...common}
        />
      )}
      {hasCadence && (
        <SingleChart
          label="Cadencia"
          color="#a855f7"
          fill={false}
          values={cadences}
          unit="rpm"
          {...common}
        />
      )}
      {hasPower && (
        <SingleChart
          label="Potencia"
          color="#f59e0b"
          fill={false}
          values={powers}
          unit="W"
          {...common}
        />
      )}
    </div>
  );
}
