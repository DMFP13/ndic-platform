import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

function decodeJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

function isTokenExpired(token) {
  const payload = decodeJwt(token);
  if (!payload || !payload.exp) return true;
  return payload.exp * 1000 < Date.now();
}

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('ndic_access_token');
    if (storedToken && !isTokenExpired(storedToken)) {
      const payload = decodeJwt(storedToken);
      if (payload) {
        setToken(storedToken);
        setUser({
          user_id: payload.sub,
          org_id: payload.org,
          role: payload.role,
          email: payload.email || '',
        });
        setIsAuthenticated(true);
      }
    } else if (storedToken) {
      // Token expired — attempt refresh
      const refresh = localStorage.getItem('ndic_refresh_token');
      if (refresh) {
        axios.post(`${API_BASE}/auth/refresh-token`, { refresh_token: refresh })
          .then((res) => {
            const newToken = res.data.access_token;
            const newRefresh = res.data.refresh_token;
            localStorage.setItem('ndic_access_token', newToken);
            if (newRefresh) localStorage.setItem('ndic_refresh_token', newRefresh);
            const payload = decodeJwt(newToken);
            if (payload) {
              setToken(newToken);
              setUser({
                user_id: payload.sub,
                org_id: payload.org,
                role: payload.role,
                email: payload.email || '',
              });
              setIsAuthenticated(true);
            }
          })
          .catch(() => {
            localStorage.removeItem('ndic_access_token');
            localStorage.removeItem('ndic_refresh_token');
          })
          .finally(() => setLoading(false));
        return;
      } else {
        localStorage.removeItem('ndic_access_token');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (email, password, role) => {
    const response = await axios.post(`${API_BASE}/auth/login`, {
      email,
      password,
      role,
    }, { timeout: 3000 });

    const { access_token, refresh_token } = response.data;

    localStorage.setItem('ndic_access_token', access_token);
    if (refresh_token) {
      localStorage.setItem('ndic_refresh_token', refresh_token);
    }

    const payload = decodeJwt(access_token);
    const userData = {
      user_id: payload?.sub || email,
      org_id: payload?.org || '',
      role: payload?.role || role,
      email,
    };

    setToken(access_token);
    setUser(userData);
    setIsAuthenticated(true);

    // Audit log entry
    const auditLog = JSON.parse(localStorage.getItem('ndic_audit_log') || '[]');
    auditLog.unshift({ event: 'login', user: email, role, timestamp: new Date().toISOString() });
    localStorage.setItem('ndic_audit_log', JSON.stringify(auditLog.slice(0, 50)));

    return userData;
  }, []);

  const logout = useCallback(() => {
    const auditLog = JSON.parse(localStorage.getItem('ndic_audit_log') || '[]');
    auditLog.unshift({ event: 'logout', user: user?.email || '', role: user?.role || '', timestamp: new Date().toISOString() });
    localStorage.setItem('ndic_audit_log', JSON.stringify(auditLog.slice(0, 50)));

    localStorage.removeItem('ndic_access_token');
    localStorage.removeItem('ndic_refresh_token');
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  }, [user]);

  const refreshToken = useCallback(async () => {
    const refresh = localStorage.getItem('ndic_refresh_token');
    if (!refresh) throw new Error('No refresh token');

    const response = await axios.post(`${API_BASE}/auth/refresh-token`, {
      refresh_token: refresh,
    });

    const newToken = response.data.access_token;
    const newRefresh = response.data.refresh_token;

    localStorage.setItem('ndic_access_token', newToken);
    if (newRefresh) localStorage.setItem('ndic_refresh_token', newRefresh);

    const payload = decodeJwt(newToken);
    setToken(newToken);
    if (payload) {
      setUser((prev) => ({
        ...prev,
        user_id: payload.sub,
        org_id: payload.org,
        role: payload.role,
      }));
    }

    return newToken;
  }, []);

  const demoLogin = useCallback((role, email) => {
    const mockPayload = {
      sub: 'demo-user', org: 'demo-org', role,
      email: email || 'demo@ndic.ng',
      exp: Math.floor(Date.now() / 1000) + 3600,
    };
    const mockToken = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${btoa(JSON.stringify(mockPayload)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')}.demo`;
    localStorage.setItem('ndic_access_token', mockToken);
    const userData = { user_id: 'demo-user', org_id: 'demo-org', role, email: email || 'demo@ndic.ng' };
    setToken(mockToken);
    setUser(userData);
    setIsAuthenticated(true);
    return userData;
  }, []);

  const value = {
    user,
    token,
    isAuthenticated,
    loading,
    login,
    logout,
    refreshToken,
    demoLogin,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
