// src/pages/LoginPage.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { api, Icons } from '../store';
import '../styles/LoginPage.css';

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const role = localStorage.getItem('user_role');
    if (token) {
      if (role === 'admin') navigate('/');
      else navigate('/chat');
    }
  }, [navigate]);

// --- Normal User Login ---
  const handleGoogleSuccess = async (credentialResponse) => {
    try {
      const data = await api.login(credentialResponse.credential);
      localStorage.setItem('auth_token', credentialResponse.credential);
      localStorage.setItem('user_role', data.user?.role || 'user');
      
      // ADD THIS LINE:
      localStorage.setItem('user_id', data.user?.id || 'unknown_user'); 
      
      window.location.href = '/chat'; 
    } catch (error) {
      console.error("Backend verification failed:", error);
      setError("Failed to verify Google login with the server.");
    }
  };

  // --- Admin Login ---
  const handleAdminLogin = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    
    try {
      const data = await api.adminLogin(username, password);
      localStorage.setItem('auth_token', data.token);
      localStorage.setItem('user_role', 'admin'); 
      
      // ADD THIS LINE:
      localStorage.setItem('user_id', data.user?.id || 'admin_sys_001'); 
      
      window.location.href = '/'; 
    } catch (err) {
      setError(err.message || "Invalid Admin Credentials");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>System Access</h2>
        <p>Sign in to access your RAG Knowledge Base</p>
        
        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleAdminLogin} className="admin-login-form">
          <div className="form-group">
            <input 
              type="text" 
              placeholder="Admin Username" 
              className="login-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <input 
              type="password" 
              placeholder="Password" 
              className="login-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary login-submit-btn" disabled={isLoading}>
            {isLoading ? "Authenticating..." : <><Icons.Lock /> Admin Login</>}
          </button>
        </form>

        <div className="login-divider">
          <span>OR</span>
        </div>

        <div className="google-btn-wrapper">
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={() => setError("Google Login Prompt Failed")}
            useOneTap
            shape="rectangular"
            theme="filled_blue"
            size="large"
            text="continue_with"
          />
        </div>
        <p style={{fontSize: '0.8rem', marginTop: '12px'}}>Standard users: Login with Google to access Ask AI.</p>
      </div>
    </div>
  );
}