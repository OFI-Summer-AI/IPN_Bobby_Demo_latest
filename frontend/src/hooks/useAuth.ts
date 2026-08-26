import { useState, useCallback } from 'react';
import type { User } from '@/types/chat.types';

/**
 * useAuth hook
 * Manages demo authentication state.
 * Production: replace localStorage with Entra ID MSAL token.
 */
export function useAuth() {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('bobby_user');
    return saved ? JSON.parse(saved) : null;
  });

  const login = useCallback((selectedUser: User) => {
    localStorage.setItem('bobby_user', JSON.stringify(selectedUser));
    setUser(selectedUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('bobby_user');
    localStorage.removeItem('bobby_token');
    setUser(null);
  }, []);

  const isEmployee  = user?.role === 'employee';
  const isHelpdesk  = user?.role === 'helpdesk';
  const isAdmin     = user?.role === 'admin';
  const canViewDashboard = isHelpdesk || isAdmin;

  return { user, login, logout, isEmployee, isHelpdesk, isAdmin, canViewDashboard };
}
