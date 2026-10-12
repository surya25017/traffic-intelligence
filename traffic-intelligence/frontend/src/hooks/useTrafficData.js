// useTrafficData — polling hook for live traffic and vehicle data.
// Polls every INTERVAL_MS for fresh data without requiring WebSockets.
import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchCurrentTraffic, fetchLiveVehicles, fetchStatistics } from '../utils/api';

const INTERVAL_MS = 8000;   // refresh every 8 seconds

export function useTrafficData() {
  const [traffic,    setTraffic]    = useState([]);
  const [vehicles,   setVehicles]   = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [tRes, vRes, sRes] = await Promise.all([
        fetchCurrentTraffic(),
        fetchLiveVehicles(25),
        fetchStatistics(),
      ]);
      setTraffic(tRes.data   || []);
      setVehicles(vRes.data  || []);
      setStatistics(sRes.data || null);
      setLastUpdate(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'API unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchAll]);

  return { traffic, vehicles, statistics, loading, error, lastUpdate, refresh: fetchAll };
}
