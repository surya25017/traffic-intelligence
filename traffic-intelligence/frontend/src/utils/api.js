// Axios API client configured to call the FastAPI backend.
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
});

export const fetchCurrentTraffic  = ()         => api.get('/api/traffic/current');
export const fetchSegments         = ()         => api.get('/api/traffic/segments');
export const fetchStatistics       = ()         => api.get('/api/traffic/statistics');
export const fetchLiveVehicles     = (count=20) => api.get(`/api/traffic/vehicles/live?count=${count}`);
export const fetchNodes            = ()         => api.get('/api/routes/nodes');
export const recommendRoute        = (src, dst) => api.post('/api/routes/recommend', { source: src, destination: dst });
export const fetchHealth           = ()         => api.get('/api/health');

export default api;
