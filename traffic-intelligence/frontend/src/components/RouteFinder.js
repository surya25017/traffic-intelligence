import React, { useState } from 'react';
import { recommendRoute, fetchNodes } from '../utils/api';

const NODES = [
  { id:'A', name:'City Center'       },
  { id:'B', name:'North Junction'    },
  { id:'C', name:'East Gate'         },
  { id:'D', name:'South Plaza'       },
  { id:'E', name:'West End'          },
  { id:'F', name:'NE Corner'         },
  { id:'G', name:'SE Corner'         },
  { id:'H', name:'SW Corner'         },
  { id:'I', name:'NW Corner'         },
  { id:'N', name:'Airport Terminal'  },
  { id:'O', name:'Railway Station'   },
  { id:'P', name:'Tech Park'         },
  { id:'Q', name:'University'        },
  { id:'R', name:'Hospital Hub'      },
];

const levelColor = {
  LOW:'#22c55e', MODERATE:'#eab308', HIGH:'#f97316', SEVERE:'#ef4444', UNKNOWN:'#94a3b8'
};

function RouteCard({ route, highlight }) {
  if (!route) return null;
  return (
    <div className={`route-card ${highlight ? 'recommended' : ''}`}>
      <div className="route-card-header">
        <span className="route-label">{route.label}</span>
        <span className={`badge badge-${route.dominant_level}`}>{route.dominant_level}</span>
      </div>
      <div className="route-meta">
        <div className="route-meta-item">
          <div className="route-meta-value">{route.total_time_min?.toFixed(1)}</div>
          <div className="route-meta-label">minutes</div>
        </div>
        <div className="route-meta-item">
          <div className="route-meta-value">{route.total_distance_km?.toFixed(1)}</div>
          <div className="route-meta-label">km</div>
        </div>
        <div className="route-meta-item">
          <div className="route-meta-value">{route.avg_congestion_score?.toFixed(0)}</div>
          <div className="route-meta-label">score</div>
        </div>
      </div>
      <div className="route-nodes">
        {route.nodes?.join(' → ')}
      </div>
    </div>
  );
}

export default function RouteFinder({ onRouteResult }) {
  const [source, setSource]     = useState('A');
  const [dest,   setDest]       = useState('G');
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState(null);
  const [result,  setResult]    = useState(null);

  const handleFind = async () => {
    if (source === dest) { setError('Source and destination must differ.'); return; }
    setLoading(true); setError(null);
    try {
      const res = await recommendRoute(source, dest);
      setResult(res.data);
      onRouteResult && onRouteResult(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Route calculation failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="route-form">
        <div className="form-group">
          <label className="form-label">📍 From</label>
          <select className="form-select" value={source} onChange={e => setSource(e.target.value)}>
            {NODES.map(n => <option key={n.id} value={n.id}>{n.id} — {n.name}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">🏁 To</label>
          <select className="form-select" value={dest} onChange={e => setDest(e.target.value)}>
            {NODES.map(n => <option key={n.id} value={n.id}>{n.id} — {n.name}</option>)}
          </select>
        </div>
        <button className="btn-primary" onClick={handleFind} disabled={loading || source === dest}>
          {loading ? <><span className="spinner" style={{borderWidth:2,width:14,height:14}} /> Finding…</> : '🗺 Find Best Route'}
        </button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {result && (
        <div className="route-result">
          {result.error && <div className="error-msg">{result.error}</div>}
          <RouteCard route={result.recommended} highlight />
          {(result.alternatives || []).map((r, i) => (
            <RouteCard key={i} route={r} />
          ))}
        </div>
      )}
    </div>
  );
}
