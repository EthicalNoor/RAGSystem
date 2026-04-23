// src/store.jsx
import React, { useState, useEffect, createContext, useContext, useCallback, useMemo } from 'react';

// --- API Service Configuration ---
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const handleResponse = async (response) => {
  if (!response.ok) {
    let errorMessage = `Error: ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.error?.message || errorData.message || errorMessage;
      if (typeof errorMessage !== 'string') errorMessage = JSON.stringify(errorMessage);
    } catch (e) {}
    throw new Error(errorMessage);
  }
  return response.json();
};

export const api = {
  getDocs: () => fetch(`${API_BASE}/documents`).then(handleResponse),
  uploadDocs: (formData, isFolder) => fetch(`${API_BASE}/documents/${isFolder ? 'upload-folder' : 'upload'}`, { method: 'POST', body: formData }).then(handleResponse),
  deleteDoc: (id) => fetch(`${API_BASE}/documents/${id}`, { method: 'DELETE' }).then(handleResponse),
  rerunDoc: (id) => fetch(`${API_BASE}/documents/${id}/rerun`, { method: 'POST' }).then(handleResponse),
  getDashboard: () => fetch(`${API_BASE}/system/dashboard/metrics`).then(handleResponse),
  getLogs: () => fetch(`${API_BASE}/system/logs/queries`).then(handleResponse),
  clearLogs: () => fetch(`${API_BASE}/system/logs/queries`, { method: 'DELETE' }).then(handleResponse),
  getVDBHealth: () => fetch(`${API_BASE}/system/vectordb/health`).then(handleResponse),
  getSettings: () => fetch(`${API_BASE}/system/settings`).then(handleResponse),
  updateSettings: (data) => fetch(`${API_BASE}/system/settings`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }).then(handleResponse),
  chat: (query, session_id) => fetch(`${API_BASE}/chat`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ query, session_id }) }).then(handleResponse),
  getGraphData: () => fetch(`${API_BASE}/system/graphdb/data`).then(handleResponse),
  getModels: () => fetch(`${API_BASE}/system/settings/models`).then(handleResponse) // NEW ENDPOINT
};

export const Icons = {
  Dashboard: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>,
  Folder: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>,
  Upload: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>,
  Activity: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>,
  Database: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>,
  Settings: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>,
  Trash: () => <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>,
  Send: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>,
  MessageSquare: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>,
  Bot: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line></svg>,
  User: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>,
  Archive: () => <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>,
  AlertCircle: () => <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>,
  CheckCircle: () => <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>,
  Plus: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>,
  Network: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
};

export const AppContext = createContext();
export const useApp = () => useContext(AppContext);

export const AppProvider = ({ children }) => {
  const [documents, setDocuments] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [logs, setLogs] = useState([]);
  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState(null);

  const [conversations, setConversations] = useState(() => {
    try { 
      const parsed = JSON.parse(localStorage.getItem('rag_conversations'));
      return Array.isArray(parsed) ? parsed : [];
    } catch { return []; }
  });
  const [activeChatId, setActiveChatId] = useState(null);

  const fetchDocuments = useCallback(() => api.getDocs().then(res => setDocuments(Array.isArray(res) ? res : [])).catch(console.error), []);
  const fetchMetrics = useCallback(() => api.getDashboard().then(setMetrics).catch(console.error), []);
  const fetchLogs = useCallback(() => api.getLogs().then(res => setLogs(Array.isArray(res) ? res : [])).catch(console.error), []);
  const fetchHealth = useCallback(() => api.getVDBHealth().then(setHealth).catch(console.error), []);
  const fetchSettings = useCallback(() => api.getSettings().then(setSettings).catch(console.error), []);

  useEffect(() => {
    fetchSettings();
    fetchDocuments();
  }, [fetchSettings, fetchDocuments]);

  useEffect(() => {
    localStorage.setItem('rag_conversations', JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    const hasPending = documents.some(doc => doc.status === 'Pending' || doc.status === 'Processing');
    if (hasPending) {
      const intervalId = setInterval(() => {
        fetchDocuments(); 
      }, 3000); 
      return () => clearInterval(intervalId); 
    } else if (documents.length > 0) {
      fetchMetrics();
      fetchHealth();
    }
  }, [documents, fetchDocuments, fetchMetrics, fetchHealth]);

  const contextValue = useMemo(() => ({
    documents, fetchDocuments,
    metrics, fetchMetrics,
    logs, fetchLogs,
    health, fetchHealth,
    settings, fetchSettings,
    conversations, setConversations,
    activeChatId, setActiveChatId
  }), [
    documents, fetchDocuments,
    metrics, fetchMetrics,
    logs, fetchLogs,
    health, fetchHealth,
    settings, fetchSettings,
    conversations, activeChatId
  ]);

  return (
    <AppContext.Provider value={contextValue}>
      {children}
    </AppContext.Provider>
  );
};