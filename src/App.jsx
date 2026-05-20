// src/App.jsx
import React, { useState, useEffect } from 'react';
import './App.css';
import { Routes, Route, NavLink, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Icons, AppProvider, useApp } from './store';

import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import QueryLogsPage from './pages/QueryLogsPage';
import VectorDBPage from './pages/VectorDBPage';
import SettingsPage from './pages/SettingsPage';
import GraphDBPage from './pages/GraphDBPage'; 
import LoginPage from './pages/LoginPage';

const APP_TITLE = import.meta.env.VITE_APP_TITLE || "RAG Control Center";

export default function App() {
  const token = localStorage.getItem('auth_token');

  if (!token) {
    return (
      <AppProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </AppProvider>
    );
  }

  return (
    <AppProvider>
      <MainLayout />
    </AppProvider>
  );
}

function MainLayout() {
  const { settings } = useApp();
  const [showSettingsPopup, setShowSettingsPopup] = useState(false);
  const role = localStorage.getItem('user_role') || 'user'; // Extract Role
  
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_id');
    window.location.href = '/login';
  };

  // Only validate global settings if the user is an Admin
  useEffect(() => {
    if (settings && role === 'admin') {
      const hasApiKeys = settings.openai_api_key || settings.gemini_api_key;
      const hasProvider = !!settings.api_provider;
      const hasDbUrl = !!settings.database_url;
      
      if (!hasApiKeys || !hasProvider || !hasDbUrl) {
        setShowSettingsPopup(true);
      } else {
        setShowSettingsPopup(false);
      }
    }
  }, [settings, role]);

  return (
    <div className="app-layout">
      <header className="global-topbar">
        <div className="brand-logo">
          <Icons.Database /> {APP_TITLE} {role === 'admin' && <span style={{fontSize: '0.7rem', background: 'var(--accent-primary)', color: 'white', padding: '2px 6px', borderRadius: '4px'}}>ADMIN</span>}
        </div>
      </header>

      <div className="main-wrapper">
        <aside className="sidebar">
          
          {/* Admin sees these top items */}
          {role === 'admin' && (
            <>
              <NavLink to="/" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} end>
                <Icons.Dashboard /> Dashboard
              </NavLink>
              <NavLink to="/documents" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                <Icons.Folder /> Documents
              </NavLink>
            </>
          )}

          {/* Everyone sees Ask AI */}
          <NavLink to="/chat" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Icons.MessageSquare /> Ask AI
          </NavLink>

          {/* Admin sees these bottom items */}
          {role === 'admin' && (
            <>
              <NavLink to="/vectordb" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                <Icons.Database /> Vector DB
              </NavLink>
              <NavLink to="/graphdb" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                <Icons.Network /> Knowledge Graph
              </NavLink>
              <NavLink to="/settings" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} style={{marginTop: 'auto'}}>
                <Icons.Settings /> Settings
              </NavLink>
            </>
          )}

          <button onClick={handleLogout} className="nav-item" style={{ color: 'var(--error)', marginTop: role !== 'admin' ? 'auto' : '0' }}>
            <Icons.AlertCircle /> Logout
          </button>
        </aside>
        
        <main className={`content-scroll ${location.pathname === '/chat' ? 'no-padding' : ''}`}>
          <Routes>
            {role === 'admin' ? (
              // ADMIN ROUTES
              <>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/chat" element={<QueryLogsPage />} />
                <Route path="/vectordb" element={<VectorDBPage />} />
                <Route path="/graphdb" element={<GraphDBPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </>
            ) : (
              // NORMAL USER ROUTES
              <>
                <Route path="/chat" element={<QueryLogsPage />} />
                <Route path="*" element={<Navigate to="/chat" replace />} />
              </>
            )}
          </Routes>
        </main>
      </div>

      {showSettingsPopup && (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
            background: 'rgba(0,0,0,0.85)', zIndex: 9999, display: 'flex', 
            justifyContent: 'center', alignItems: 'center'
        }}>
            <div style={{
                background: 'var(--bg-panel)', padding: '40px', 
                borderRadius: '12px', textAlign: 'center', maxWidth: '450px',
                boxShadow: 'var(--shadow-lg)'
            }}>
                <div style={{color: 'var(--error)', margin: '0 auto 16px', display: 'flex', justifyContent: 'center'}}>
                  <Icons.AlertCircle />
                </div>
                <h2 style={{color: 'var(--text-main)', fontSize: '1.4rem'}}>Initialization Required</h2>
                <p style={{margin: '16px 0', color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: '1.5'}}>
                  You must configure your API Provider, provide valid API keys, and confirm your Database Connection in the Settings panel before utilizing the system.
                </p>
                <button 
                    className="btn btn-primary" 
                    style={{width: '100%', marginTop: '8px'}}
                    onClick={() => { setShowSettingsPopup(false); navigate('/settings'); }}
                >
                    Configure System Settings
                </button>
            </div>
        </div>
      )}
    </div>
  );
}