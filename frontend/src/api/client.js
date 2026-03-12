import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 3000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('ndic_access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Track refresh state to avoid multiple concurrent refresh attempts
let isRefreshing = false;
let pendingRequests = [];

function processQueue(error, token = null) {
  pendingRequests.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
  });
  pendingRequests = [];
}

// Response interceptor — handle 401, 403, 500
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (!error.response) {
      // Network error
      console.error('[NDIC API] Network error:', error.message);
      return Promise.reject(error);
    }

    const { status } = error.response;

    if (status === 401 && !originalRequest._retried) {
      originalRequest._retried = true;

      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve, reject) => {
          pendingRequests.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      isRefreshing = true;

      const refreshToken = localStorage.getItem('ndic_refresh_token');
      if (!refreshToken) {
        isRefreshing = false;
        processQueue(error);
        return Promise.reject(error);
      }

      try {
        const res = await axios.post(`${BASE_URL}/auth/refresh-token`, {
          refresh_token: refreshToken,
        });
        const newToken = res.data.access_token;
        const newRefresh = res.data.refresh_token;

        localStorage.setItem('ndic_access_token', newToken);
        if (newRefresh) localStorage.setItem('ndic_refresh_token', newRefresh);

        apiClient.defaults.headers.common.Authorization = `Bearer ${newToken}`;
        originalRequest.headers.Authorization = `Bearer ${newToken}`;

        processQueue(null, newToken);
        isRefreshing = false;

        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        isRefreshing = false;
        return Promise.reject(refreshError);
      }
    }

    if (status === 403) {
      console.warn('[NDIC API] Access denied:', originalRequest.url);
    }

    if (status === 500) {
      console.error('[NDIC API] Server error on:', originalRequest.url, error.response.data);
    }

    return Promise.reject(error);
  }
);

export default apiClient;
