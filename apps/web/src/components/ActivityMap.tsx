import { useEffect, useRef } from 'react';
import { MapContainer, Polyline, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import type { RecordPoint } from '@/types/activity';

// Fix default icon paths broken by Vite bundling
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)['_getIconUrl'];
L.Icon.Default.mergeOptions({
  iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
  iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
  shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
});

interface Props {
  records: RecordPoint[];
  hoverIdx: number | null;
}

type LatLng = [number, number];

function FitBounds({ bounds }: { bounds: L.LatLngBoundsExpression }) {
  const map = useMap();
  useEffect(() => {
    map.fitBounds(bounds, { padding: [24, 24] });
  }, [map, bounds]);
  return null;
}

function HoverMarker({ position }: { position: LatLng | null }) {
  const markerRef = useRef<L.CircleMarker | null>(null);
  const map = useMap();

  useEffect(() => {
    if (!position) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    if (!markerRef.current) {
      markerRef.current = L.circleMarker(position, {
        radius: 7,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.9,
        weight: 2,
      }).addTo(map);
    } else {
      markerRef.current.setLatLng(position);
    }
    return () => {
      markerRef.current?.remove();
      markerRef.current = null;
    };
  }, [position, map]);

  return null;
}

export default function ActivityMap({ records, hoverIdx }: Props) {
  const gps: LatLng[] = records
    .filter((r) => r.lat != null && r.lon != null)
    .map((r) => [r.lat!, r.lon!]);

  if (gps.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-400 text-sm">
        Sin datos GPS
      </div>
    );
  }

  const bounds = L.latLngBounds(gps);

  const hoverPos: LatLng | null =
    hoverIdx != null && records[hoverIdx]?.lat != null
      ? [records[hoverIdx].lat!, records[hoverIdx].lon!]
      : null;

  return (
    <div className="h-80 overflow-hidden rounded-xl border border-slate-200 shadow-sm">
      <MapContainer
        center={gps[0]}
        zoom={13}
        scrollWheelZoom={true}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds bounds={bounds} />
        <Polyline positions={gps} color="#3b82f6" weight={3} opacity={0.85} />
        {/* Marcador de inicio (verde) */}
        <Polyline positions={[gps[0]]} color="#22c55e" weight={10} opacity={0.9} />
        {/* Marcador de fin (rojo) */}
        <Polyline positions={[gps[gps.length - 1]]} color="#ef4444" weight={10} opacity={0.9} />
        <HoverMarker position={hoverPos} />
      </MapContainer>
    </div>
  );
}
