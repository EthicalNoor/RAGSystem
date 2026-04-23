// src/pages/VectorDBPage.jsx
import React, { useEffect } from 'react';
import { Icons, useApp } from '../store';
import '../styles/VectorDBPage.css';

export default function VectorDBPage() {
  const { health, fetchHealth } = useApp();

  // ONLY fetch health if we don't have it yet
  useEffect(() => {
    if (!health) {
      fetchHealth();
    }
  }, [health, fetchHealth]);

  if (!health) return <div style={{ padding: '20px' }}>Loading vector database status...</div>;

  const maxStorageMB = 1024; 
  const storagePercentage = Math.min((health.storage_used_mb / maxStorageMB) * 100, 100).toFixed(2);

  return (
    <div className="page-container">
      <h2 style={{ fontSize: '1.5rem' }}>Vector Database Health</h2>
      
      <div className="grid-2-col">
        <div className="dashboard-card">
          <h3 className="card-title">Index Metrics</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Status</span>
              <span className={`badge ${health.status === 'Healthy' ? 'badge-success' : 'badge-warning'}`}>{health.status}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Total Embeddings</span>
              <span style={{ fontWeight: 600 }}>{health.total_embeddings} vectors</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Last Checked</span>
              <span style={{ fontWeight: 600 }}>{new Date(health.last_updated).toLocaleTimeString()}</span>
            </div>
          </div>
        </div>

        <div className="dashboard-card">
          <h3 className="card-title">Storage Capacity</h3>
          <p style={{ fontSize: '0.85rem', marginBottom: '12px' }}>{health.storage_used_mb.toFixed(2)} MB used of 1 GB allocated limit.</p>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${storagePercentage}%` }}></div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '8px' }}>
            <span>{storagePercentage}%</span>
            <span>1 GB</span>
          </div>
        </div>
      </div>
    </div>
  );
}