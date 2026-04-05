import { useState, useCallback, useEffect } from 'react';
import { authLogin, authRegister, api } from '../utils/api';

export function useAuth() {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('poorup_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Verify the server-side session is still valid on every page load.
  // localStorage can persist across browser restarts but the session cookie
  // (SESSION_PERMANENT=False) is cleared when the browser closes, causing
  // the "Authentication required" error even though the user appears logged in.
  useEffect(() => {
    if (!localStorage.getItem('poorup_user')) return;
    api.get('/auth/me').catch(() => {
      localStorage.removeItem('poorup_user');
      localStorage.removeItem('poorup_token');
      setUser(null);
    });
  }, []);

  const login = useCallback(async (username, password) => {
    setLoading(true);
    setError(null);
    try {
      const res = await authLogin({ username, password });
      const { user: userData } = res.data;
      localStorage.setItem('poorup_user', JSON.stringify(userData));
      setUser(userData);
      return userData;
    } catch (err) {
      const msg = err.response?.data?.error || err.response?.data?.message || 'Login failed';
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (username, password) => {
    setLoading(true);
    setError(null);
    try {
      const res = await authRegister({ username, password });
      const { user: userData } = res.data;
      localStorage.setItem('poorup_user', JSON.stringify(userData));
      setUser(userData);
      return userData;
    } catch (err) {
      const msg = err.response?.data?.error || err.response?.data?.message || 'Registration failed';
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('poorup_token');
    localStorage.removeItem('poorup_user');
    setUser(null);
  }, []);

  return { user, loading, error, login, register, logout };
}
