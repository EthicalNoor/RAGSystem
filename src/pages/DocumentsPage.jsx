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
  const [isDeleting, setIsDeleting] = useState(false); // UI lock state
  const [selectedIds, setSelectedIds] = useState([]); 
  const [uiMessage, setUiMessage] = useState(null);

  const handleFiles = async (filesList, isFolder = false) => {
    if (!filesList.length) return;
    
    if (!window.confirm(`Are you sure you want to upload and index ${filesList.length} document(s)?`)) {
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (folderInputRef.current) folderInputRef.current.value = '';
      return;
    }

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
    if (!window.confirm("Are you sure you want to permanently delete this document and its vector data?")) return;

    setIsDeleting(true); // Lock UI to prevent double-clicks
    try {
      await api.deleteDoc(id);
      
      const remainingDocs = await api.getDocs();
      if (remainingDocs.length === 0) {
        await api.clearLogs();
        setConversations([]);
        setActiveChatId(null);
        setUiMessage({ type: 'success', text: 'All documents deleted. Chat history automatically cleared.' });
        fetchLogs(); 
      } else {
        setUiMessage({ type: 'success', text: 'Document deleted successfully.' });
      }

      await fetchDocuments();
      fetchMetrics();
      fetchHealth();
      setSelectedIds(prev => prev.filter(selectedId => selectedId !== id));
    } catch (err) {
      setUiMessage({ type: 'error', text: `Delete failed: ${err.message}` });
    } finally {
      setIsDeleting(false); // Unlock UI
    }
  };

  const toggleSelectAll = (checked) => setSelectedIds(checked ? documents.map(d => d.id) : []);
  const toggleSelect = (id) => setSelectedIds(prev => prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]);

  const handleBulkDelete = async () => {
    if (!window.confirm(`Are you sure you want to permanently delete ${selectedIds.length} document(s)?`)) return;
    
    setIsDeleting(true); // Lock UI to prevent double-clicks
    try {
      await Promise.all(selectedIds.map(id => api.deleteDoc(id)));
      
      const remainingDocs = await api.getDocs();
      if (remainingDocs.length === 0) {
        await api.clearLogs();
        setConversations([]);
        setActiveChatId(null);
        setUiMessage({ type: 'success', text: `Successfully deleted ${selectedIds.length} document(s). All chat history automatically cleared.` });
        fetchLogs(); 
      } else {
        setUiMessage({ type: 'success', text: `Successfully deleted ${selectedIds.length} document(s).` });
      }

      await fetchDocuments();
      fetchMetrics();
      fetchHealth();
      setSelectedIds([]);
    } catch (err) {
      setUiMessage({ type: 'error', text: `Bulk delete failed: ${err.message}` });
    } finally {
      setIsDeleting(false); // Unlock UI
    }
  };

  const handleBulkRerun = async () => {
    if (!window.confirm(`Are you sure you want to queue ${selectedIds.length} document(s) for reprocessing?`)) return;

    try {
      await Promise.all(selectedIds.map(id => api.rerunDoc(id)));
      await fetchDocuments();
      setUiMessage({ type: 'success', text: `Successfully queued ${selectedIds.length} document(s) for reprocessing.` });
      setSelectedIds([]);
    } catch (err) {
      setUiMessage({ type: 'error', text: `Bulk rerun failed: ${err.message}` });
    }
  };

  const handleBulkArchive = () => {
    if (!window.confirm(`Are you sure you want to archive ${selectedIds.length} document(s)?`)) return;

    setUiMessage({ type: 'success', text: `Archived ${selectedIds.length} document(s) successfully.` });
    setSelectedIds([]);
  };

  const handleViewDocument = (fileName) => {
    const backendUrl = import.meta.env.VITE_API_BASE_URL 
      ? import.meta.env.VITE_API_BASE_URL.replace('/api/v1', '') 
      : 'http://localhost:8000';
    
    const fileUrl = `${backendUrl}/uploads/${fileName}`;
    window.open(fileUrl, '_blank');
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
            <button className="btn btn-primary" disabled={isUploading || isDeleting} onClick={() => fileInputRef.current.click()}>
              {isUploading ? 'Uploading...' : 'Upload Files'}
            </button>
            <button className="btn btn-secondary" disabled={isUploading || isDeleting} onClick={() => folderInputRef.current.click()}>
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
            <button className="btn btn-secondary" disabled={isDeleting} onClick={handleBulkRerun} style={{ fontSize: '0.8rem', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Icons.Activity /> Rerun Selected
            </button>
            <button className="btn btn-secondary" disabled={isDeleting} onClick={handleBulkArchive} style={{ fontSize: '0.8rem', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Icons.Archive /> Archive
            </button>
            <button 
              className="btn btn-secondary" 
              onClick={handleBulkDelete} 
              disabled={isDeleting} 
              style={{ fontSize: '0.8rem', padding: '6px 12px', color: 'var(--error)', display: 'flex', alignItems: 'center', gap: '6px', opacity: isDeleting ? 0.5 : 1 }}
            >
              <Icons.Trash /> {isDeleting ? 'Deleting...' : 'Delete'}
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
                  <th style={{ textAlign: 'center' }}>View Document</th>
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
                      <button 
                        onClick={() => deleteDoc(doc.id)} 
                        disabled={isDeleting} 
                        style={{ background: 'none', border: 'none', color: 'var(--error)', cursor: isDeleting ? 'not-allowed' : 'pointer', padding: '4px', opacity: isDeleting ? 0.5 : 1 }}
                      >
                        <Icons.Trash />
                      </button>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button 
                        onClick={() => handleViewDocument(doc.name)} 
                        style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', padding: '4px' }}
                        title="View Document"
                      >
                        <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                          <circle cx="12" cy="12" r="3"></circle>
                        </svg>
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