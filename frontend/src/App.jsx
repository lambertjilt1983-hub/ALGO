import React, { useState, useEffect } from 'react';

import { Routes, Route, useNavigate } from 'react-router-dom';
import Dashboard from './Dashboard';
import AutoTradingDashboard from './components/AutoTradingDashboard';
import config from './config/api';
import './App.css';


export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [pendingOtpUser, setPendingOtpUser] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    console.log('[App] Checking auth token:', !!token);
    if (token) {
      setIsLoggedIn(true);
      console.log('[App] User is logged in');
    } else {
      console.log('[App] No token found, showing login');
    }
    setLoading(false);
  }, []);

  console.log('[App] Rendering - isLoggedIn:', isLoggedIn, 'loading:', loading);
  
  if (loading) {
    return <div style={{ textAlign: 'center', padding: '50px' }}>Loading...</div>;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      let payload;
      let endpoint;

      if (isLogin) {
        endpoint = config.endpoints.auth.login;
        payload = { username, password };
      } else {
        endpoint = config.endpoints.auth.register;
        payload = { username, email, mobile, password };
      }

      console.log('Sending login request:', { endpoint, payload });

      const response = await config.authFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      console.log('Response status:', response.status);

      const data = await response.json();

      if (response.ok) {
        if (isLogin) {
          localStorage.setItem('access_token', data.access_token);
          localStorage.setItem('refresh_token', data.refresh_token);
          console.log('Login successful, tokens saved');
          setUsername('');
          setPassword('');
          // Force immediate re-render
          setTimeout(() => {
            setIsLoggedIn(true);
            navigate('/');
          }, 100);
        } else {
          alert('✓ Registration successful! Enter the OTP sent to your email/mobile.');
          setPendingOtpUser(username);
          setOtp('');
          setIsLogin(false);
          setSubmitting(false);
          return;
        }
      } else if (response.status === 403 && data.detail && data.detail.toLowerCase().includes('otp')) {
        setPendingOtpUser(username);
        setOtp('');
        setError('Enter the OTP sent to your email/mobile to continue.');
        setSubmitting(false);
        return;
      } else {
        setError(data.detail || 'Operation failed. Please try again.');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleOtpSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const response = await config.authFetch(config.endpoints.auth.verifyOtp || '/auth/verify-otp', {
        method: 'POST',
        body: JSON.stringify({ username: pendingOtpUser || username, otp }),
      });

      const data = await response.json();
      if (response.ok) {
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        setIsLoggedIn(true);
      } else {
        setError(data.detail || 'Invalid OTP');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (!isLoggedIn) {
    // Show login/register form
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#f3f4f6' }}>
        {/* Navbar */}
        <nav style={{
          backgroundColor: '#1e40af',
          color: 'white',
          padding: '1rem 2rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}>
          <h1 style={{ margin: 0, fontSize: '1.5rem' }}>🚀 AlgoTrade Pro</h1>
        </nav>
        {/* Main Content */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 'calc(100vh - 60px)',
          padding: '2rem'
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: '0.5rem',
            boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
            padding: '2rem',
            width: '100%',
            maxWidth: '400px'
          }}>
            {/* Tabs */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
              <button
                onClick={() => {
                  setIsLogin(true);
                  setError('');
                }}
                style={{
                  flex: 1,
                  padding: '0.5rem',
                  border: 'none',
                  backgroundColor: isLogin ? '#1e40af' : '#e5e7eb',
                  color: isLogin ? 'white' : 'black',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  transition: 'all 0.3s'
                }}
              >
                Login
              </button>
              <button
                onClick={() => {
                  setIsLogin(false);
                  setError('');
                }}
                style={{
                  flex: 1,
                  padding: '0.5rem',
                  border: 'none',
                  backgroundColor: !isLogin ? '#1e40af' : '#e5e7eb',
                  color: !isLogin ? 'white' : 'black',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  transition: 'all 0.3s'
                }}
              >
                Register
              </button>
            </div>
            {/* Error Message */}
            {error && (
              <div style={{
                backgroundColor: '#fee2e2',
                color: '#991b1b',
                padding: '0.75rem',
                borderRadius: '0.375rem',
                marginBottom: '1rem',
                fontSize: '0.875rem'
              }}>
                ❌ {error}
              </div>
            )}
            {/* Form */}
            {pendingOtpUser ? (
              <form onSubmit={handleOtpSubmit}>
                <h2 style={{ textAlign: 'center', marginBottom: '1.5rem', color: '#1f2937' }}>
                  Verify OTP
                </h2>
                <p style={{ textAlign: 'center', marginBottom: '1rem', color: '#4b5563' }}>
                  Enter the 6-digit code sent to your email and mobile.
                </p>
                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>
                    OTP
                  </label>
                  <input
                    type="text"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    placeholder="Enter OTP"
                    required
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '0.375rem',
                      fontSize: '1rem',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    backgroundColor: submitting ? '#9ca3af' : '#1e40af',
                    color: 'white',
                    border: 'none',
                    borderRadius: '0.375rem',
                    fontSize: '1rem',
                    fontWeight: 'bold',
                    cursor: submitting ? 'not-allowed' : 'pointer',
                    transition: 'background-color 0.3s'
                  }}
                >
                  {submitting ? 'Verifying...' : 'Verify & Continue'}
                </button>
              </form>
            ) : (
              <form onSubmit={handleSubmit}>
                <h2 style={{ textAlign: 'center', marginBottom: '1.5rem', color: '#1f2937' }}>
                  {isLogin ? 'Welcome Back' : 'Create Account'}
                </h2>
                {!isLogin && (
                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>
                      Email
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter your email"
                      required={!isLogin}
                      style={{
                        width: '100%',
                        padding: '0.75rem',
                        border: '1px solid #d1d5db',
                        borderRadius: '0.375rem',
                        fontSize: '1rem',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                )}
                {!isLogin && (
                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>
                      Mobile
                    </label>
                    <input
                      type="tel"
                      value={mobile}
                      onChange={(e) => setMobile(e.target.value)}
                      placeholder="Enter mobile number"
                      required={!isLogin}
                      style={{
                        width: '100%',
                        padding: '0.75rem',
                        border: '1px solid #d1d5db',
                        borderRadius: '0.375rem',
                        fontSize: '1rem',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                )}
                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>
                    Username
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter username"
                    required
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '0.375rem',
                      fontSize: '1rem',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>
                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.5rem', color: '#374151', fontWeight: '500' }}>
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    required
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '0.375rem',
                      fontSize: '1rem',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    backgroundColor: submitting ? '#9ca3af' : '#1e40af',
                    color: 'white',
                    border: 'none',
                    borderRadius: '0.375rem',
                    fontSize: '1rem',
                    fontWeight: 'bold',
                    cursor: submitting ? 'not-allowed' : 'pointer',
                    transition: 'background-color 0.3s'
                  }}
                >
                  {submitting ? 'Loading...' : (isLogin ? 'Login' : 'Register')}
                </button>
              </form>
            )}
            {/* Footer Text */}
            <p style={{ textAlign: 'center', marginTop: '1.5rem', color: '#6b7280', fontSize: '0.875rem' }}>
              {isLogin ? "Don't have an account? " : 'Already have an account? '}
              <button
                type="button"
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#1e40af',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  textDecoration: 'underline'
                }}
              >
                {isLogin ? 'Register' : 'Login'}
              </button>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // If logged in, use routes
  console.log('[App] Rendering routes for logged in user');
  return (
    <Routes>
      <Route path="/autotrading" element={
        <div>
          <div style={{ 
            padding: '30px', 
            background: '#dc2626', 
            margin: '10px',
            textAlign: 'center',
            fontSize: '28px',
            fontWeight: 'bold',
            color: 'white',
            borderRadius: '8px'
          }}>
            🚀 AutoTradingDashboard !
          </div>
          <AutoTradingDashboard />
        </div>
      } />
      <Route path="/*" element={<Dashboard />} />
    </Routes>
  );
}

