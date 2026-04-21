// src/pages/SettingsPage.jsx
import React, { useState, useEffect } from 'react';
import { api, Icons, useApp } from '../store';

export default function SettingsPage() {
  const { settings: globalSettings, fetchSettings } = useApp();
  
  const [settings, setSettings] = useState(null);
  const [keysModified, setKeysModified] = useState({ openai: false, gemini: false });
  const [uiMessage, setUiMessage] = useState(null); 
  const [isSaving, setIsSaving] = useState(false);

  const MASK = "••••••••••••••••••••••••••••••••";

  useEffect(() => {
    if (globalSettings) {
      setSettings({
        ...globalSettings,
        openai_api_key: globalSettings.openai_api_key ? MASK : '',
        gemini_api_key: globalSettings.gemini_api_key ? MASK : ''
      });
      setKeysModified({ openai: false, gemini: false });
    }
  }, [globalSettings]);

  if (!settings) return <div>Loading Settings...</div>;

  const handleChange = (e) => {
    const { name, value } = e.target;
    
    if (name === 'openai_api_key') setKeysModified(prev => ({ ...prev, openai: true }));
    if (name === 'gemini_api_key') setKeysModified(prev => ({ ...prev, gemini: true }));

    setSettings(prev => {
      const next = { ...prev, [name]: name === 'chunk_size' ? parseInt(value) : (name === 'temperature' ? parseFloat(value) : value) };
      
      if (name === 'api_provider') {
        if (value === 'gemini') {
          next.llm_model = 'gemini-1.5-pro';
          next.embedding_model = 'models/text-embedding-004';
        } else {
          next.llm_model = 'gpt-4o';
          next.embedding_model = 'text-embedding-3-large';
        }
      }
      return next;
    });
  };

  const handleKeyFocus = (provider) => {
    if (settings[`${provider}_api_key`] === MASK) {
      setSettings(prev => ({ ...prev, [`${provider}_api_key`]: '' }));
      setKeysModified(prev => ({ ...prev, [provider]: true }));
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setUiMessage(null);
    setIsSaving(true);

    const payload = { ...settings };
    if (!keysModified.openai) delete payload.openai_api_key;
    if (!keysModified.gemini) delete payload.gemini_api_key;

    try {
      await api.updateSettings(payload);
      await fetchSettings(); 
      setUiMessage({ type: 'success', text: 'System configuration and API keys securely saved.' });
    } catch (err) {
      setUiMessage({ type: 'error', text: `Update Failed: ${err.message}` });
    } finally {
      setIsSaving(false);
    }
  };

  const llmOptions = settings.api_provider === 'openai' 
    ? ['gpt-4o', 'gpt-3.5-turbo'] : ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash'];
  const embeddingOptions = settings.api_provider === 'openai'
    ? ['text-embedding-3-large', 'text-embedding-3-small'] : ['models/text-embedding-004', 'models/embedding-001'];

  return (
    <div className="page-container">
      <h2 style={{ fontSize: '1.5rem' }}>System Settings</h2>
      
      {uiMessage && (
        <div className={`ui-alert ${uiMessage.type}`}>
          {uiMessage.type === 'success' ? <Icons.CheckCircle /> : <Icons.AlertCircle />}
          {uiMessage.text}
        </div>
      )}
      
      <div className="dashboard-card" style={{ maxWidth: '700px' }}>
        <form onSubmit={handleSave}>
          <div className="grid-2-col" style={{ gap: '16px', marginBottom: '24px' }}>
            <div className="control-group" style={{ marginBottom: 0 }}>
              <label className="control-label">OpenAI API Key</label>
              <input name="openai_api_key" type="password" className="control-input" placeholder="sk-..." value={settings.openai_api_key} onChange={handleChange} onFocus={() => handleKeyFocus('openai')} autoComplete="new-password" />
            </div>
            <div className="control-group" style={{ marginBottom: 0 }}>
              <label className="control-label">Google Gemini API Key</label>
              <input name="gemini_api_key" type="password" className="control-input" placeholder="AIzaSy..." value={settings.gemini_api_key} onChange={handleChange} onFocus={() => handleKeyFocus('gemini')} autoComplete="new-password" />
            </div>
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-light)', margin: '24px 0' }} />

          <div className="control-group">
            <label className="control-label">Active API Provider</label>
            <select name="api_provider" className="control-input" value={settings.api_provider} onChange={handleChange}>
              <option value="openai">OpenAI</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>

          <div className="grid-2-col" style={{ gap: '16px' }}>
            <div className="control-group">
              <label className="control-label">Embedding Model</label>
              <select name="embedding_model" className="control-input" value={settings.embedding_model} onChange={handleChange}>
                {embeddingOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
            <div className="control-group">
              <label className="control-label">LLM Generation Model</label>
              <select name="llm_model" className="control-input" value={settings.llm_model} onChange={handleChange}>
                {llmOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
          </div>

          <div className="grid-2-col" style={{ gap: '16px' }}>
            <div className="control-group">
              <label className="control-label">Chunk Size (Tokens)</label>
              <input name="chunk_size" type="number" className="control-input" value={settings.chunk_size} onChange={handleChange} />
            </div>
            <div className="control-group">
              <label className="control-label">Temperature (0.0 - 1.0)</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input name="temperature" type="range" min="0" max="1" step="0.1" value={settings.temperature} onChange={handleChange} style={{ flex: 1 }} />
                <span style={{ fontWeight: 600, width: '30px' }}>{settings.temperature}</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
             <button type="submit" className="btn btn-primary" disabled={isSaving}>
               {isSaving ? 'Saving...' : 'Save Configuration'}
             </button>
          </div>
        </form>
      </div>
    </div>
  );
}