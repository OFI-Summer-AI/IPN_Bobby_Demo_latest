import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useChatStore } from '@/store/chatStore';
import HomePage from '@/pages/HomePage';
import DashboardPage from '@/pages/DashboardPage';
import LoginPage from '@/pages/LoginPage';
import Layout from '@/components/layout/Layout';
import type { User } from '@/types/chat.types';

export default function App() {
  const { setUser } = useChatStore();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    // Demo: restore user from localStorage
    const saved = localStorage.getItem('bobby_user');
    if (saved) {
      const user: User = JSON.parse(saved);
      setUser(user);
      setAuthed(true);
    }
  }, [setUser]);

  const handleLogin = (user: User) => {
    localStorage.setItem('bobby_user', JSON.stringify(user));
    setUser(user);
    setAuthed(true);
  };

  if (!authed) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
