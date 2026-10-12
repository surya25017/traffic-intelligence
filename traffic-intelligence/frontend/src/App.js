import React, { useState } from 'react';
import './index.css';
import { useTrafficData } from './hooks/useTrafficData';
import TrafficMap   from './components/TrafficMap';
import RouteFinder  from './components/RouteFinder';
import { CongestionTrendChart, SegmentSpeedChart } from './components/Charts';

function StatCard({ value, label, color }) {
  return (
    <div className="stat-item">
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function CongestionBadge({ level, count }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'6px 0', borderBottom:'1px solid #1e293b' }}>
      <span className={`badge badge-${level}`}>{level}</span>
      <span style={{ fontWeight:700, fontSize:'0.9rem' }}>{count}</span>
    </div>
  );
}

export default function App() {
  const { traffic, vehicles, statistics, loading, error, lastUpdate } = useTrafficData();
  const [routeResult, setRouteResult] = useState(null);

  const summary = statistics?.summary;
  const trend   = statistics?.congestion_trend || [];

  // Sort segments by congestion score descending for the list
  const sortedSegments = [...traffic].sort((a,b) => (b.congestion_score||0) - (a.congestion_score||0));

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-logo">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 11l19-9-9 19-2-8-8-2z"/>
          </svg>
          <div>
            <div className="header-title">Traffic Intelligence</div>
            <div className="header-sub">Real-Time Congestion Monitor · Simulated Data</div>
          </div>
        </div>
        <div className="header-status">
          <div className="status-dot" />
          {loading ? 'Connecting…' : error ? 'API Offline' : `Live · Updated ${lastUpdate || '—'}`}
        </div>
      </header>

      <div className="main-content">
        {/* ── Sidebar ── */}
        <aside className="sidebar">

          {/* Stats */}
          <div className="card">
            <div className="card-title">📊 Network Overview</div>
            {loading && !summary ? (
              <div className="loading"><div className="spinner" /> Loading…</div>
            ) : (
              <div className="stats-grid">
                <StatCard value={summary?.total_segments ?? traffic.length} label="Segments" color="#60a5fa" />
                <StatCard value={summary?.total_vehicles ?? vehicles.length} label="Vehicles" color="#fbbf24" />
                <StatCard value={`${summary?.avg_congestion_score?.toFixed(0) ?? '—'}`} label="Avg Score" color="#f97316" />
                <StatCard value={`${summary?.avg_speed_kph?.toFixed(0) ?? '—'} km/h`} label="Avg Speed" color="#22c55e" />
              </div>
            )}
          </div>

          {/* Congestion breakdown */}
          <div className="card">
            <div className="card-title">🚦 Congestion Breakdown</div>
            {summary ? (
              <>
                <CongestionBadge level="LOW"      count={summary.low_count}      />
                <CongestionBadge level="MODERATE" count={summary.moderate_count} />
                <CongestionBadge level="HIGH"     count={summary.high_count}     />
                <CongestionBadge level="SEVERE"   count={summary.severe_count}   />
              </>
            ) : <div className="empty-state">No data yet</div>}
          </div>

          {/* Segment list */}
          <div className="card">
            <div className="card-title">🛣 Road Segments</div>
            {sortedSegments.length === 0 ? (
              <div className="empty-state">No segment data</div>
            ) : (
              <div className="segment-list">
                {sortedSegments.map(seg => (
                  <div key={seg.segment_id} className="segment-item">
                    <div>
                      <div className="segment-name">{seg.segment_id}</div>
                      <div className="segment-speed">
                        {seg.avg_speed_kph != null ? `${seg.avg_speed_kph.toFixed(1)} km/h` : 'N/A'}
                      </div>
                    </div>
                    <div className="segment-bar-wrap">
                      <div className="segment-bar">
                        <div className="segment-bar-fill"
                          style={{ width:`${seg.congestion_score||0}%`, background: seg.color || '#94a3b8' }} />
                      </div>
                      <span className={`badge badge-${seg.congestion_level}`} style={{fontSize:'0.65rem'}}>
                        {seg.congestion_level}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Route finder */}
          <div className="card">
            <div className="card-title">🗺 Route Recommender</div>
            <RouteFinder onRouteResult={setRouteResult} />
          </div>

          {error && (
            <div className="error-msg">
              ⚠ {error} — showing simulated data.
            </div>
          )}
        </aside>

        {/* ── Map + Charts ── */}
        <div style={{ display:'flex', flexDirection:'column', overflow:'hidden' }}>
          <div className="map-panel" style={{ flex:1, minHeight:0 }}>
            <div className="map-container" style={{ height:'100%' }}>
              <TrafficMap
                traffic={traffic}
                vehicles={vehicles}
                recommendedRoute={routeResult?.recommended}
                alternativeRoutes={routeResult?.alternatives}
              />
            </div>
          </div>

          {/* Charts */}
          <div className="charts-row">
            <div className="chart-card">
              <div className="chart-title">24-Hour Congestion Trend</div>
              <div style={{ flex:1 }}>
                <CongestionTrendChart data={trend} />
              </div>
            </div>
            <div className="chart-card">
              <div className="chart-title">Segment Speeds (km/h)</div>
              <div style={{ flex:1 }}>
                <SegmentSpeedChart data={sortedSegments} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
