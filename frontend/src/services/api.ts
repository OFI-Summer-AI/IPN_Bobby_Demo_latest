import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

// ── Auth interceptor ──────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('bobby_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Error interceptor ─────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('bobby_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
