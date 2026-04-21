// src/App.jsx
import React, { useState } from 'react';
import './App.css';
import { Icons, AppProvider } from './store';

import DashboardPage from './pages/DashboardPage';
import DocumentsPage from './pages/DocumentsPage';
import QueryLogsPage from './pages/QueryLogsPage';
import VectorDBPage from './pages/VectorDBPage';
import SettingsPage from './pages/SettingsPage';

// Pull the app title from the environment, with a fallback.
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
          <button className={`nav-item ${activePage === 'settings' ? 'active' : ''}`} style={{marginTop: 'auto'}} onClick={() => setActivePage('settings')}>
            <Icons.Settings /> Settings
          </button>
        </aside>
        
        <main className={`content-scroll ${activePage === 'chat' ? 'no-padding' : ''}`}>
          {activePage === "dashboard" && <DashboardPage />}
          {activePage === "documents" && <DocumentsPage />}
          {activePage === "chat" && <QueryLogsPage />}
          {activePage === "vectordb" && <VectorDBPage />}
          {activePage === "settings" && <SettingsPage />}
        </main>
      </div>
    </div>
  );
}