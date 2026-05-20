// src/store.jsx
import React, { useState, useEffect, createContext, useContext, useCallback, useMemo, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const authFetch = (endpoint, options = {}) => {
  const token = localStorage.getItem('auth_token');
  const headers = {
    ...options.headers,
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
  return fetch(`${API_BASE}${endpoint}`, { ...options, headers }).then(handleResponse);
};

const handleResponse = async (response) => {
  if (!response.ok) {
    if (response.status === 401) {
      console.warn("Session expired or invalid token. Logging out...");
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_role');
      localStorage.removeItem('user_id');
      window.location.href = '/login'; 
      return; 
    }

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
  login: (token) => fetch(`${API_BASE}/auth/google`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ token }) }).then(handleResponse),
  adminLogin: (username, password) => fetch(`${API_BASE}/auth/admin`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ username, password }) }).then(handleResponse),
  getDocs: () => authFetch(`/documents`),
  uploadDocs: (formData, isFolder) => authFetch(`/documents/${isFolder ? 'upload-folder' : 'upload'}`, { method: 'POST', body: formData }),
  deleteDoc: (id) => authFetch(`/documents/${id}`, { method: 'DELETE' }),
  rerunDoc: (id) => authFetch(`/documents/${id}/rerun`, { method: 'POST' }),
  getDashboard: () => authFetch(`/system/dashboard/metrics`),
  getLogs: () => authFetch(`/system/logs/queries`),
  clearLogs: () => authFetch(`/system/logs/queries`, { method: 'DELETE' }),
  getVDBHealth: () => authFetch(`/system/vectordb/health`),
  getSettings: () => authFetch(`/system/settings`),
  updateSettings: (data) => authFetch(`/system/settings`, { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) }),
  chat: (query, session_id) => authFetch(`/chat`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ query, session_id }) }),
  getGraphData: () => authFetch(`/system/graphdb/data`),
  getModels: () => authFetch(`/system/settings/models`)
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
  Network: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>,
  Volume2: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>,
  VolumeX: () => <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>,
  Lock: () => <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
};

export const AppContext = createContext();
export const useApp = () => useContext(AppContext);

export const AppProvider = ({ children }) => {
  const [documents, setDocuments] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [logs, setLogs] = useState([]);
  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState(null);
  
  const hasInitialized = useRef(false);
  const prevPendingCount = useRef(0);

  const [conversations, setConversations] = useState(() => {
    try { 
      const userId = localStorage.getItem('user_id') || 'default';
      const parsed = JSON.parse(localStorage.getItem(`rag_conversations_${userId}`));
    } catch { return []; }
  });
  const [activeChatId, setActiveChatId] = useState(null);

  const fetchDocuments = useCallback(() => api.getDocs().then(res => setDocuments(Array.isArray(res) ? res : [])).catch(console.error), []);
  const fetchMetrics = useCallback(() => api.getDashboard().then(setMetrics).catch(console.error), []);
  const fetchLogs = useCallback(() => api.getLogs().then(res => setLogs(Array.isArray(res) ? res : [])).catch(console.error), []);
  const fetchHealth = useCallback(() => api.getVDBHealth().then(setHealth).catch(console.error), []);
  const fetchSettings = useCallback(() => api.getSettings().then(setSettings).catch(console.error), []);

  useEffect(() => {
    if (!hasInitialized.current) {
      // Only fetch settings if Admin
      const role = localStorage.getItem('user_role');
      if (role === 'admin') fetchSettings();
      
      fetchDocuments();
      hasInitialized.current = true;
    }
  }, [fetchSettings, fetchDocuments]);

useEffect(() => {
    const userId = localStorage.getItem('user_id') || 'default';
    localStorage.setItem(`rag_conversations_${userId}`, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    const pendingDocs = documents.filter(doc => doc.status === 'Pending' || doc.status === 'Processing');
    const currentPendingCount = pendingDocs.length;
    
    if (currentPendingCount > 0) {
      let totalPendingMB = 0;
      pendingDocs.forEach(doc => {
        const sizeVal = parseFloat(doc.size);
        if (!isNaN(sizeVal)) totalPendingMB += sizeVal;
      });

      let dynamicIntervalMs = Math.floor(5000 + (totalPendingMB * 1500));
      if (dynamicIntervalMs > 45000) dynamicIntervalMs = 45000;
      if (dynamicIntervalMs < 5000) dynamicIntervalMs = 5000;

      const timeoutId = setTimeout(() => {
        fetchDocuments(); 
      }, dynamicIntervalMs); 
      
      prevPendingCount.current = currentPendingCount;
      return () => clearTimeout(timeoutId); 
      
    } else if (prevPendingCount.current > 0 && currentPendingCount === 0) {
      fetchMetrics();
      fetchHealth();
      prevPendingCount.current = 0;
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