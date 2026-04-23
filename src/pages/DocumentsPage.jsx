// src/pages/DocumentsPage.jsx
import React, { useState, useRef } from 'react';
import { api, Icons, useApp } from '../store';
import '../styles/DocumentsPage.css';

export default function DocumentsPage() {
  const { 
    documents, fetchDocuments, fetchMetrics, fetchHealth, fetchLogs,
    setConversations, setActiveChatId 
  } = useApp();
  
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]); 
  const [uiMessage, setUiMessage] = useState(null);

  // NOTE: REMOVED on-mount fetchDocuments() effect! It is handled by store.jsx now.

  const handleFiles = async (filesList, isFolder = false) => {
    if (!filesList.length) return;
    setIsUploading(true);
    setUiMessage(null);
    
    const formData = new FormData();
    Array.from(filesList).forEach(file => formData.append('files', file));

    try {
      await api.uploadDocs(formData, isFolder);
      await fetchDocuments(); 
      setUiMessage({ type: 'success', text: `Successfully uploaded ${filesList.length} document(s). Background indexing started.` });
    } catch (err) {
      setUiMessage({ type: 'error', text: `Upload failed: ${err.message}` });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (folderInputRef.current) folderInputRef.current.value = '';
    }
  };

  const deleteDoc = async (id) => {
    try {
      await api.deleteDoc(id);
      
      const remainingDocs = await api.getDocs();
      if (remainingDocs.length === 0) {
        await api.clearLogs();
        setConversations([]);
        setActiveChatId(null);
        setUiMessage({ type: 'success', text: 'All documents deleted. Chat history automatically cleared.' });
        // Only fetch logs if we actually cleared them
        fetchLogs(); 
      } else {
        setUiMessage({ type: 'success', text: 'Document deleted successfully.' });
      }

      await fetchDocuments();
      
      // Update stats in the background without blocking the UI
      fetchMetrics();
      fetchHealth();
      setSelectedIds(prev => prev.filter(selectedId => selectedId !== id));
    } catch (err) {
      setUiMessage({ type: 'error', text: `Delete failed: ${err.message}` });
    }
  };

  const toggleSelectAll = (checked) => setSelectedIds(checked ? documents.map(d => d.id) : []);
  const toggleSelect = (id) => setSelectedIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);

  const handleBulkDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete ${selectedIds.length} documents?`)) return;
    try {
      await Promise.all(selectedIds.map(id => api.deleteDoc(id)));
      
      const remainingDocs = await api.getDocs();
      if (remainingDocs.length === 0) {
        await api.clearLogs();
        setConversations([]);
        setActiveChatId(null);
        setUiMessage({ type: 'success', text: `Successfully deleted ${selectedIds.length} document(s). All chat history automatically cleared.` });
        // Only fetch logs if we actually cleared them
        fetchLogs(); 
      } else {
        setUiMessage({ type: 'success', text: `Successfully deleted ${selectedIds.length} document(s).` });
      }

      await fetchDocuments();
      
      // Update stats in the background without blocking the UI
      fetchMetrics();
      fetchHealth();
      setSelectedIds([]);
    } catch (err) {
      setUiMessage({ type: 'error', text: `Bulk delete failed: ${err.message}` });
    }
  };

  const handleBulkRerun = async () => {
    try {
      await Promise.all(selectedIds.map(id => api.rerunDoc(id)));
      await fetchDocuments();
      setUiMessage({ type: 'success', text: `Successfully queued ${selectedIds.length} document(s) for reprocessing.` });
      setSelectedIds([]);
    } catch (err) {
      setUiMessage({ type: 'error', text: `Bulk rerun failed: ${err.message}` });
    }
  };

  return (
    <div className="page-container">
      <h2 style={{ fontSize: '1.5rem' }}>Document Management</h2>

      {uiMessage && (
        <div className={`ui-alert ${uiMessage.type}`}>
          {uiMessage.type === 'success' ? <Icons.CheckCircle /> : <Icons.AlertCircle />}
          {uiMessage.text}
        </div>
      )}

      <div className="dashboard-card">
        <div className="upload-zone">
          <Icons.Upload />
          <h3 style={{ margin: 0 }}>Drag & drop files or folders here</h3>
          <p style={{ fontSize: '0.85rem' }}>Supported: PDF, DOCX, TXT, CSV, Images (OCR)</p>
          
          <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
            <button className="btn btn-primary" disabled={isUploading} onClick={() => fileInputRef.current.click()}>
              {isUploading ? 'Uploading...' : 'Upload Files'}
            </button>
            <button className="btn btn-secondary" disabled={isUploading} onClick={() => folderInputRef.current.click()}>
              Upload Folder
            </button>
          </div>

          <input type="file" multiple className="hidden-input" ref={fileInputRef} onChange={(e) => handleFiles(e.target.files, false)} />
          <input type="file" webkitdirectory="true" className="hidden-input" ref={folderInputRef} onChange={(e) => handleFiles(e.target.files, true)} />
        </div>
      </div>

      <div className="dashboard-card">
        <h3 className="card-title">Knowledge Base</h3>

        {selectedIds.length > 0 && (
          <div style={{ padding: '12px 16px', background: '#f8f9fa', border: '1px solid #e2e8f0', borderRadius: '8px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.9rem', marginRight: 'auto' }}>
              {selectedIds.length} item(s) selected
            </span>
            <button className="btn btn-secondary" onClick={handleBulkRerun} style={{ fontSize: '0.8rem', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Icons.Activity /> Rerun Selected
            </button>
            <button className="btn btn-secondary" onClick={handleBulkDelete} style={{ fontSize: '0.8rem', padding: '6px 12px', color: 'var(--error)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Icons.Trash /> Delete
            </button>
          </div>
        )}

        {documents.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Icons.Folder />
            <p style={{ marginTop: '8px' }}>No documents uploaded yet.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '40px', textAlign: 'center' }}>
                    <input type="checkbox" checked={documents.length > 0 && selectedIds.length === documents.length} onChange={(e) => toggleSelectAll(e.target.checked)} style={{ cursor: 'pointer' }} />
                  </th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map(doc => (
                  <tr key={doc.id} style={selectedIds.includes(doc.id) ? { backgroundColor: '#f1f5f9' } : {}}>
                    <td style={{ textAlign: 'center' }}>
                      <input type="checkbox" checked={selectedIds.includes(doc.id)} onChange={() => toggleSelect(doc.id)} style={{ cursor: 'pointer' }} />
                    </td>
                    <td style={{ fontWeight: 500 }}>{doc.name}</td>
                    <td>{doc.type}</td>
                    <td>{doc.size}</td>
                    <td>
                      <span className={`badge ${doc.status === 'Indexed' ? 'badge-success' : (doc.status === 'Failed' ? 'badge-warning' : 'badge-info')}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td>
                      <button onClick={() => deleteDoc(doc.id)} style={{ background: 'none', border: 'none', color: 'var(--error)', cursor: 'pointer', padding: '4px' }}>
                        <Icons.Trash />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}