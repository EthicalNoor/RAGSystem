// src/App.jsx
import React, { useState, useEffect } from 'react';
import './App.css';
import { Icons, AppProvider, useApp } from './store';

import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import QueryLogsPage from './pages/QueryLogsPage';
import VectorDBPage from './pages/VectorDBPage';
import SettingsPage from './pages/SettingsPage';
import GraphDBPage from './pages/GraphDBPage'; // NEW IMPORT

const APP_TITLE = import.meta.env.VITE_APP_TITLE || "RAG Control Center";

export default function App() {
  return (
    <AppProvider>
      <MainLayout />
    </AppProvider>
  );
}

function MainLayout() {
  const [activePage, setActivePage] = useState("dashboard");
  const { settings } = useApp();
  const [showSettingsPopup, setShowSettingsPopup] = useState(false);

  useEffect(() => {
    if (settings) {
      const hasKeys = settings.openai_api_key || settings.gemini_api_key;
      if (!hasKeys || !settings.api_provider) {
        setShowSettingsPopup(true);
      } else {
        setShowSettingsPopup(false);
      }
    }
  }, [settings]);

  return (
    <div className="app-layout">
      <header className="global-topbar">
        <div className="brand-logo">
          <Icons.Database /> {APP_TITLE}
        </div>
      </header>

      <div className="main-wrapper">
        <aside className="sidebar">
          <button className={`nav-item ${activePage === 'dashboard' ? 'active' : ''}`} onClick={() => setActivePage('dashboard')}>
            <Icons.Dashboard /> Dashboard
          </button>
          <button className={`nav-item ${activePage === 'documents' ? 'active' : ''}`} onClick={() => setActivePage('documents')}>
            <Icons.Folder /> Documents
          </button>
          <button className={`nav-item ${activePage === 'chat' ? 'active' : ''}`} onClick={() => setActivePage('chat')}>
            <Icons.MessageSquare /> Ask AI
          </button>
          <button className={`nav-item ${activePage === 'vectordb' ? 'active' : ''}`} onClick={() => setActivePage('vectordb')}>
            <Icons.Database /> Vector DB
          </button>
          
          {/* NEW GRAPH KNOWLEDGE BASE BUTTON */}
          <button className={`nav-item ${activePage === 'graphdb' ? 'active' : ''}`} onClick={() => setActivePage('graphdb')}>
            <Icons.Network /> Knowledge Graph
          </button>

          <button className={`nav-item ${activePage === 'settings' ? 'active' : ''}`} style={{marginTop: 'auto'}} onClick={() => setActivePage('settings')}>
            <Icons.Settings /> Settings
          </button>
        </aside>
        
        <main className={`content-scroll ${activePage === 'chat' ? 'no-padding' : ''}`}>
          {activePage === "dashboard" && <DashboardPage />}
          {activePage === "documents" && <DocumentsPage />}
          {activePage === "chat" && <QueryLogsPage />}
          {activePage === "vectordb" && <VectorDBPage />}
          {activePage === "graphdb" && <GraphDBPage />} {/* NEW ROUTE */}
          {activePage === "settings" && <SettingsPage />}
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
                borderRadius: '12px', textAlign: 'center', maxWidth: '400px',
                boxShadow: 'var(--shadow-lg)'
            }}>
                <div style={{color: 'var(--error)', marginBottom: '16px', display: 'flex', justifyContent: 'center'}}>
                  <Icons.AlertCircle />
                </div>
                <h2 style={{color: 'var(--text-main)', fontSize: '1.4rem'}}>Please check settings.</h2>
                <p style={{margin: '16px 0', color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: '1.5'}}>
                  You must configure your API Provider and provide valid API keys in the Settings panel before using the application.
                </p>
                <button 
                    className="btn btn-primary" 
                    style={{width: '100%', marginTop: '8px'}}
                    onClick={() => { setShowSettingsPopup(false); setActivePage('settings'); }}
                >
                    Go to Settings
                </button>
            </div>
        </div>
      )}
    </div>
  );
}