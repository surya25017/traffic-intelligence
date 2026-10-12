import React from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1e293b', border: '1px solid #334155',
      borderRadius: 8, padding: '8px 12px', fontSize: '0.75rem'
    }}>
      <p style={{ color: '#94a3b8', marginBottom: 4 }}>{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color || '#f1f5f9' }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</strong>
        </p>
      ))}
    </div>
  );
};

export function CongestionTrendChart({ data }) {
  if (!data?.length) return <div className="empty-state">No trend data</div>;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
        <defs>
          <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.4} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#64748b' }} interval={3} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="avg_score"
          name="Congestion Score"
          stroke="#3b82f6"
          fill="url(#scoreGrad)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function SegmentSpeedChart({ data }) {
  if (!data?.length) return <div className="empty-state">No segment data</div>;
  const topSegments = data
    .filter(d => d.avg_speed_kph != null)
    .slice(0, 10)
    .map(d => ({
      name: d.segment_id?.replace('SEG-', ''),
      speed: parseFloat(d.avg_speed_kph?.toFixed(1)),
      fill: d.color || '#3b82f6',
    }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={topSegments} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} />
        <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="speed" name="Avg Speed (km/h)" radius={[3, 3, 0, 0]}>
          {topSegments.map((entry, i) => (
            <rect key={i} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
