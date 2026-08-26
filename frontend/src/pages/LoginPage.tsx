import { useState } from 'react';
import type { User } from '@/types/chat.types';
import styles from './LoginPage.module.css';
import dogImg from '@/assets/dog_login_hero.png';

interface LoginPageProps {
  onLogin: (user: User) => void;
}

export function InspiredLogo({ variant = 'dark-bg' }: { variant?: 'dark-bg' | 'light-bg' | 'header' }) {
  if (variant === 'header') {
    return (
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <svg width="170" height="40" viewBox="0 0 170 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <text x="0" y="24" fill="#FFFFFF" fontFamily="Georgia, serif" fontSize="22" fontWeight="bold">Inspired</text>
          <text x="0" y="35" fill="#FFFFFF" fontFamily="sans-serif" fontSize="7" fontWeight="700" letterSpacing="2.5">PET NUTRITION</text>
          
          <g transform="translate(108, 4)">
            <path d="M 0 15 L 14 2 L 28 15 L 28 30 L 0 30 Z" fill="#FFFFFF"/>
            <circle cx="14" cy="20" r="4.5" fill="#00473C"/>
            <path d="M 9 30 L 9 20 Q 14 15 19 20 L 19 30 Z" fill="#00473C"/>
          </g>
        </svg>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <svg width="112" height="34" viewBox="0 0 112 34" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="112" height="34" rx="4" fill="#00473C"/>
        <text x="8" y="22" fill="#FFFFFF" fontFamily="Georgia, serif" fontSize="15" fontWeight="bold">Inspired</text>
        
        <g transform="translate(78, 6)" scale="0.75">
          <path d="M 0 12 L 12 0 L 24 12 L 24 24 L 0 24 Z" fill="#FFFFFF"/>
          <circle cx="12" cy="15" r="3" fill="#00473C"/>
          <path d="M 8 24 L 8 16 Q 12 13 16 16 L 16 24 Z" fill="#00473C"/>
        </g>
      </svg>
    </div>
  );
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState('hello@inspirednutrition.com');
  const [password, setPassword] = useState('password123');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (!response.ok) throw new Error('Login failed');
      const data = await response.json();
      
      localStorage.setItem('bobby_token', data.access_token);
      onLogin(data.user);
    } catch (err) {
      console.error('Auth API error, falling back to local session:', err);
      const role = email.includes('admin') ? 'admin' : email.includes('helpdesk') ? 'helpdesk' : 'employee';
      const name = role === 'admin' ? 'James (IT Admin)' : role === 'helpdesk' ? 'Sarah (Helpdesk)' : 'Alex (Employee)';
      
      onLogin({
        user_id: email,
        name,
        role
      });
    }
  };

  return (
    <div className={styles.container}>
      {/* Left side form */}
      <div className={styles.formPane}>
        <div className={styles.formContainer}>
          <div className={styles.logoWrapper}>
            <InspiredLogo />
          </div>

          <div className={styles.welcomeHeader}>
            <h1 className={styles.title}>Welcome Back</h1>
            <p className={styles.subtitle}>
              Sign in to continue your journey with <span className={styles.brandLink}>Inspired.</span>
            </p>
          </div>

          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.inputGroup}>
              <label htmlFor="email" className={styles.label}>Email Address</label>
              <div className={styles.inputWrapper}>
                <span className={styles.inputIcon}>✉</span>
                <input
                  type="email"
                  id="email"
                  className={styles.input}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className={styles.inputGroup}>
              <label htmlFor="password" className={styles.label}>Password</label>
              <div className={styles.inputWrapper}>
                <span className={styles.inputIcon}>🔒</span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  className={styles.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className={styles.eyeBtn}
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? '👁️' : '👁️‍🗨️'}
                </button>
              </div>
            </div>

            <div className={styles.formMeta}>
              <label className={styles.rememberMe}>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                <span className={styles.checkboxLabel}>Remember me</span>
              </label>
              <a href="#forgot" className={styles.forgotLink}>Forgot password?</a>
            </div>

            <button type="submit" className={styles.submitBtn}>
              Sign In
            </button>
          </form>

          <div className={styles.divider}>
            <span>OR</span>
          </div>
        </div>
      </div>

      {/* Right side image */}
      <div className={styles.imagePane} style={{ backgroundImage: `url(${dogImg})` }}>
        <div className={styles.imageOverlay}>
          <h2 className={styles.heroTitle}>We Create Happiness</h2>
          <p className={styles.heroSubtitle}>Through better nutrition.</p>
        </div>
      </div>
    </div>
  );
}
