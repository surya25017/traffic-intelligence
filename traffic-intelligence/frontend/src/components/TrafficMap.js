import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, useMap } from 'react-leaflet';

const CITY_CENTER  = [28.6139, 77.2090];
const DEFAULT_ZOOM = 13;

// Node lat/lon lookup
const NODE_COORDS = {
  A: [28.6139, 77.2090], B: [28.6250, 77.2090], C: [28.6139, 77.2200],
  D: [28.6020, 77.2090], E: [28.6139, 77.1980], F: [28.6270, 77.2200],
  G: [28.5970, 77.2200], H: [28.5970, 77.1980], I: [28.6270, 77.1980],
  J: [28.6200, 77.2145], K: [28.6080, 77.2200], L: [28.6020, 77.2145],
  M: [28.6080, 77.1980], N: [28.5580, 77.0900], O: [28.6420, 77.2190],
  P: [28.5900, 77.2400], Q: [28.6500, 77.1800], R: [28.6000, 77.1700],
};

// Road segment from→to mapping
const SEGMENT_COORDS = {
  'SEG-AB': ['A','B'], 'SEG-AC': ['A','C'], 'SEG-AD': ['A','D'],
  'SEG-AE': ['A','E'], 'SEG-BF': ['B','F'], 'SEG-CF': ['C','F'],
  'SEG-CG': ['C','G'], 'SEG-DG': ['D','G'], 'SEG-DH': ['D','H'],
  'SEG-EH': ['E','H'], 'SEG-EI': ['E','I'], 'SEG-NO': ['N','O'],
  'SEG-OB': ['O','B'], 'SEG-NR': ['N','R'], 'SEG-PG': ['P','G'],
  'SEG-QI': ['Q','I'], 'SEG-RE': ['R','E'], 'SEG-BA': ['B','A'],
  'SEG-CA': ['C','A'], 'SEG-DA': ['D','A'], 'SEG-EA': ['E','A'],
};

function FitBoundsOnRoute({ route }) {
  const map = useMap();
  useEffect(() => {
    if (!route) return;
    const coords = route.nodes
      .map(n => NODE_COORDS[n])
      .filter(Boolean);
    if (coords.length >= 2) {
      map.fitBounds(coords, { padding: [40, 40] });
    }
  }, [route, map]);
  return null;
}

export default function TrafficMap({ traffic, vehicles, recommendedRoute, alternativeRoutes }) {
  // Build a segment→color lookup from traffic data
  const segmentColors = {};
  (traffic || []).forEach(seg => {
    segmentColors[seg.segment_id] = seg.color || '#94a3b8';
  });
  const segmentScores = {};
  (traffic || []).forEach(seg => {
    segmentScores[seg.segment_id] = seg;
  });

  // Build route polylines
  const routeNodePath = (route) =>
    (route?.nodes || []).map(n => NODE_COORDS[n]).filter(Boolean);

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <MapContainer
        center={CITY_CENTER}
        zoom={DEFAULT_ZOOM}
        style={{ height: '100%', width: '100%' }}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* ── Road segments (congestion coloured) ── */}
        {Object.entries(SEGMENT_COORDS).map(([segId, [fromNode, toNode]]) => {
          const from = NODE_COORDS[fromNode];
          const to   = NODE_COORDS[toNode];
          if (!from || !to) return null;
          const color = segmentColors[segId] || '#475569';
          const seg   = segmentScores[segId];
          return (
            <Polyline
              key={segId}
              positions={[from, to]}
              pathOptions={{ color, weight: 5, opacity: 0.85 }}
            >
              {seg && (
                <Tooltip sticky>
                  <div style={{ fontSize: '12px', lineHeight: '1.6' }}>
                    <strong>{segId}</strong><br />
                    Score: {seg.congestion_score?.toFixed(1)}<br />
                    Level: {seg.congestion_level}<br />
                    Speed: {seg.avg_speed_kph?.toFixed(1)} km/h
                  </div>
                </Tooltip>
              )}
            </Polyline>
          );
        })}

        {/* ── Alternative routes ── */}
        {(alternativeRoutes || []).map((route, i) => {
          const path = routeNodePath(route);
          if (path.length < 2) return null;
          return (
            <Polyline
              key={`alt-${i}`}
              positions={path}
              pathOptions={{ color: '#a78bfa', weight: 4, opacity: 0.7, dashArray: '8 5' }}
            >
              <Tooltip>Alternative {i + 1}: {route.total_time_min?.toFixed(1)} min</Tooltip>
            </Polyline>
          );
        })}

        {/* ── Recommended route ── */}
        {recommendedRoute && (() => {
          const path = routeNodePath(recommendedRoute);
          if (path.length < 2) return null;
          return (
            <Polyline
              positions={path}
              pathOptions={{ color: '#06b6d4', weight: 6, opacity: 0.95 }}
            >
              <Tooltip>
                ✅ Recommended: {recommendedRoute.total_time_min?.toFixed(1)} min,
                {' '}{recommendedRoute.total_distance_km?.toFixed(1)} km
              </Tooltip>
            </Polyline>
          );
        })()}

        {/* ── City nodes ── */}
        {Object.entries(NODE_COORDS).map(([id, [lat, lon]]) => (
          <CircleMarker
            key={id}
            center={[lat, lon]}
            radius={5}
            pathOptions={{ fillColor: '#1e40af', color: '#60a5fa', weight: 2, fillOpacity: 0.9 }}
          >
            <Tooltip direction="top" offset={[0, -8]}>{id}</Tooltip>
          </CircleMarker>
        ))}

        {/* ── Simulated vehicles ── */}
        {(vehicles || []).slice(0, 25).map(v => (
          <CircleMarker
            key={v.vehicle_id}
            center={[v.latitude, v.longitude]}
            radius={4}
            pathOptions={{ fillColor: '#fbbf24', color: '#f59e0b', weight: 1, fillOpacity: 0.95 }}
          >
            <Tooltip>
              🚗 {v.vehicle_id}<br />
              {v.speed_kph} km/h — {v.road_segment_id}
            </Tooltip>
          </CircleMarker>
        ))}

        {recommendedRoute && <FitBoundsOnRoute route={recommendedRoute} />}
      </MapContainer>

      {/* ── Map legend ── */}
      <div className="map-legend">
        <div className="legend-title">Congestion Level</div>
        {[
          ['#22c55e', 'Low (0–24)'],
          ['#eab308', 'Moderate (25–49)'],
          ['#f97316', 'High (50–74)'],
          ['#ef4444', 'Severe (75–100)'],
          ['#fbbf24', 'Vehicles (simulated)'],
          ['#06b6d4', 'Recommended Route'],
          ['#a78bfa', 'Alternative Route'],
        ].map(([color, label]) => (
          <div key={label} className="legend-item">
            <div className="legend-dot" style={{ background: color }} />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
