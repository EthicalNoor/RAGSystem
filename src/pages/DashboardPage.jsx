// src/pages/DashboardPage.jsx
import React, { useEffect } from 'react';
import { Icons, useApp } from '../store';
import '../styles/DashboardPage.css';

export default function DashboardPage() {
  const { metrics, fetchMetrics } = useApp();

  // ONLY fetch metrics if we don't have them yet
  useEffect(() => {
    if (!metrics) {
      fetchMetrics();
    }
  }, [metrics, fetchMetrics]);

  if (!metrics) return <div style={{ padding: '20px' }}>Loading metrics...</div>;

  return (
    <div className="page-container">
      <h2 style={{ fontSize: '1.5rem' }}>System Dashboard</h2>
      
      <div className="grid-stats">
        <div className="stat-card">
          <div className="stat-header">Total Documents <Icons.Folder /></div>
          <div className="stat-value">{metrics.total_documents}</div>
        </div>
        <div className="stat-card">
          <div className="stat-header">Total Chunks <Icons.Database /></div>
          <div className="stat-value">{metrics.total_chunks}</div>
        </div>
        <div className="stat-card">
          <div className="stat-header">Storage Used <Icons.Upload /></div>
          <div className="stat-value">{metrics.storage_used_mb.toFixed(2)} MB</div>
        </div>
        <div className="stat-card">
          <div className="stat-header">Total Queries <Icons.Activity /></div>
          <div className="stat-value">{metrics.total_queries}</div>
        </div>
      </div>

      <div className="dashboard-card" style={{ marginTop: '16px' }}>
        <h3 className="card-title">Recent Activity</h3>
        <table style={{ marginTop: '16px' }}>
          <tbody>
            {metrics.recent_activity && metrics.recent_activity.map((act, i) => (
              <tr key={i}>
                <td><span className="badge badge-info">{act.action}</span></td>
                <td>{act.time}</td>
              </tr>
            ))}
            {(!metrics.recent_activity || metrics.recent_activity.length === 0) && (
              <tr><td colSpan="2" style={{ color: 'var(--text-muted)' }}>No recent activity to display.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}