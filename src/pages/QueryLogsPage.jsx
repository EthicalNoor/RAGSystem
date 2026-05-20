// src/pages/QueryLogsPage.jsx
import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api, Icons, useApp } from '../store';
import '../styles/QueryLogsPage.css';

export default function QueryLogsPage() {
const { 
    documents = [], 
    conversations = [], setConversations, 
    activeChatId, setActiveChatId,
    fetchLogs, fetchMetrics,
    fetchConversations 
  } = useApp();

  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isTTSActive, setIsTTSActive] = useState(false);
  const [activeMessageId, setActiveMessageId] = useState(null); // Tracks active citations panel
  const messagesEndRef = useRef(null);

  const hasDocuments = documents.length > 0;

  const activeChat = (conversations || []).find(c => c.id === activeChatId) || null;
  const activeMessage = activeChat?.messages?.find(m => m.id === activeMessageId);
  const activeCitations = activeMessage?.citations || [];

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages, isTyping]);

  // Clean up TTS when unmounting or changing pages
  useEffect(() => {
    return () => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Fetch chat sessions from database on component mount
  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const speakText = (text) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const cleanText = text.replace(/[*#_`~\[\]]/g, ''); // Strips [1] markers for TTS
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
  };

  const handleSelectChat = async (chatId) => {
    setActiveChatId(chatId);
    setActiveMessageId(null);
    
    const chat = conversations.find(c => c.id === chatId);
    
    // If messages array is empty, fetch the history from the database
    if (chat && (!chat.messages || chat.messages.length === 0)) {
      try {
        const history = await api.getChatSessionHistory(chatId);
        
        const loadedMessages = [];
        history.forEach(log => {
          // 1. Push user query as a separate message
          loadedMessages.push({
            id: `user-${log.id}`,
            role: 'user',
            content: log.query_text
          });
          // 2. Push AI response as a separate message
          loadedMessages.push({
            id: `ai-${log.id}`,
            role: 'ai',
            content: log.response_snippet,
            latency: log.latency_ms,
            citations: [] // Citations aren't stored in DB logs currently
          });
        });
        
        setConversations(prev => prev.map(c => 
          c.id === chatId ? { ...c, messages: loadedMessages } : c
        ));
      } catch (error) {
        console.error("Failed to load chat history:", error);
      }
    }
  };

  const handleNewChat = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    setActiveChatId(null);
    setActiveMessageId(null);
  };

  const handleDeleteChat = async (e, id) => {
    e.stopPropagation();
    if (window.confirm("Delete this conversation?")) {
      try {
        await api.authFetch(`/chat/sessions/${id}`, { method: 'DELETE' }); 
        setConversations(prev => prev.filter(c => c.id !== id));
        if (activeChatId === id) {
          if ('speechSynthesis' in window) window.speechSynthesis.cancel();
          setActiveChatId(null);
          setActiveMessageId(null);
        }
      } catch (error) {
        // Fallback to local delete if API fails
        setConversations(prev => prev.filter(c => c.id !== id));
        if (activeChatId === id) {
          if ('speechSynthesis' in window) window.speechSynthesis.cancel();
          setActiveChatId(null);
          setActiveMessageId(null);
        }
      }
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !hasDocuments || isTyping) return;

    if ('speechSynthesis' in window) window.speechSynthesis.cancel();

    const userQuery = input.trim();
    setInput('');
    setIsTyping(true);

    let currentChatId = activeChatId;
    const userMsg = { id: Date.now().toString(), role: 'user', content: userQuery };

    // Generate new persistent conversation if starting fresh
    if (!currentChatId) {
      currentChatId = Date.now().toString();
      const newChat = {
        id: currentChatId,
        title: userQuery.length > 25 ? userQuery.substring(0, 25) + '...' : userQuery,
        createdAt: Date.now(),
        messages: [userMsg]
      };
      setConversations(prev => [newChat, ...(prev || [])]);
      setActiveChatId(currentChatId);
    } else {
      setConversations(prev => prev.map(c => 
        c.id === currentChatId ? { ...c, messages: [...c.messages, userMsg] } : c
      ));
    }

    try {
      const data = await api.chat(userQuery, currentChatId);
      
      const aiMsg = { 
        id: data.message_id || data.query_id || Date.now().toString(), 
        role: 'ai', 
        content: data.response,
        citations: data.citations || [] 
      };
      
      setConversations(prev => prev.map(c => 
        c.id === currentChatId ? { ...c, messages: [...c.messages, aiMsg] } : c
      ));

      // Auto-open citations panel for the newest AI response
      setActiveMessageId(aiMsg.id);

      if (isTTSActive) {
        speakText(data.response);
      }
      
      fetchLogs();
      fetchMetrics();
    } catch (error) {
      const errorMsg = { id: Date.now().toString(), role: 'ai', content: `Error: ${error.message}` };
      setConversations(prev => prev.map(c => 
        c.id === currentChatId ? { ...c, messages: [...c.messages, errorMsg] } : c
      ));
    } finally {
      setIsTyping(false);
    }
  };

  const toggleTTS = () => {
    setIsTTSActive(!isTTSActive);
    if (isTTSActive && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  };

  // --- Handle opening PDF with auto-navigation & highlighting ---
  const handleCitationClick = (cite) => {
    const backendUrl = import.meta.env.VITE_API_BASE_URL 
      ? import.meta.env.VITE_API_BASE_URL.replace('/api/v1', '') 
      : 'http://localhost:8000';
    
    const fileUrl = `${backendUrl}/uploads/${cite.document}`;

    // Clean up the text for searching (Chrome search works best with a clean string, no line breaks)
    // We take the first 40 characters to guarantee a hit without breaking the URL parser
    const cleanSearchText = cite.content
      .replace(/[\n\r]/g, ' ')
      .trim()
      .substring(0, 40);

    // Native Chrome/Edge PDF Highlighting
    const targetUrl = `${fileUrl}#page=${cite.page}&search=${encodeURIComponent(cleanSearchText)}`;

    window.open(targetUrl, '_blank');
  };

  return (
    <div className="unified-chat-layout">
      {/* 1. Persistent Left Sidebar for Conversation History */}
      <div className="chat-history-sidebar">
        <button className="new-chat-btn" onClick={handleNewChat}>
          <Icons.Plus /> New Chat
        </button>
        
        <div className="chat-list">
          {conversations.length === 0 ? (
            <div style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No previous conversations.
            </div>
          ) : (
            conversations.map(chat => (
              <div 
                key={chat.id} 
                className={`chat-history-item ${activeChatId === chat.id ? 'active' : ''}`}
                onClick={() => handleSelectChat(chat.id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                  <Icons.MessageSquare />
                  <span style={{ whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {chat.title}
                  </span>
                </div>
                <button className="delete-chat-icon" onClick={(e) => handleDeleteChat(e, chat.id)}>
                  <Icons.Trash />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 2-Column Wrapper for Chat & Citations */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* 2. Main Chat Area */}
        <div className="chat-main-area" style={{ flex: activeMessageId ? '0 0 65%' : '1', transition: 'flex 0.3s ease' }}>
          {!hasDocuments && (
            <div className="warning-banner">
              ⚠️ No documents uploaded. Please upload documents in the "Documents" tab before asking AI.
            </div>
          )}

          <div className="chat-messages-container" style={{ padding: '32px 20px' }}>
            {!activeChat ? (
              <div className="empty-chat-state">
                <div className="empty-chat-icon"><Icons.Bot /></div>
                <h2>How can I help you today?</h2>
                <p>Type a message below to start a conversation using your securely uploaded knowledge base.</p>
              </div>
            ) : (
              activeChat.messages.map((msg, idx) => (
                <div 
                  key={msg.id || idx} 
                  className={`message-row ${msg.role} ${activeMessageId === msg.id ? 'selected-msg' : ''}`}
                  onClick={() => msg.role === 'ai' && setActiveMessageId(msg.id)}
                  style={{ cursor: msg.role === 'ai' ? 'pointer' : 'default', maxWidth: '100%' }}
                >
                  <div className={`avatar ${msg.role}`}>
                    {msg.role === 'ai' ? <Icons.Bot /> : <Icons.User />}
                  </div>
                  <div className="message-content" style={{ width: '100%' }}>
                    <div className={`bubble ${msg.content && msg.content.startsWith('Error:') ? 'error-bubble' : ''}`}>
                      {msg.role === 'ai' && !msg.content.startsWith('Error:') ? (
                        <div className="markdown-body">
                          <ReactMarkdown>
                            {/* Regex to wrap [1] markers in a stylable inline code element */}
                            {msg.content.replace(/\[(\d+)\]/g, '`[$1]`')}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        msg.content
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            
            {isTyping && (
              <div className="message-row ai">
                <div className="avatar ai"><Icons.Bot /></div>
                <div className="message-content">
                  <div className="bubble" style={{ padding: '12px 18px' }}>
                    <div className="typing-dots"><span></span><span></span><span></span></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Unified Sticky Input Area */}
          <div className="chat-input-area" style={{ padding: '20px' }}>
            <form className="input-wrapper" onSubmit={handleSend} style={{ maxWidth: '100%' }}>
              <input 
                type="text" 
                placeholder={hasDocuments ? "Ask AI..." : "Upload documents to begin..."}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={!hasDocuments || isTyping}
              />
              <button 
                type="button" 
                className={`tts-toggle-btn ${isTTSActive ? 'active' : ''}`} 
                onClick={toggleTTS}
                title={isTTSActive ? "Disable Text-to-Speech" : "Enable Text-to-Speech"}
              >
                {isTTSActive ? <Icons.Volume2 /> : <Icons.VolumeX />}
              </button>
              <button type="submit" className="send-btn" disabled={!input.trim() || !hasDocuments || isTyping}>
                <Icons.Send />
              </button>
            </form>
            <div className="chat-footer-note">
              Click any AI response to view exact document sources and confidence scores.
            </div>
          </div>
        </div>

        {/* 3. Right Citation Verification Panel */}
        {activeMessageId && (
          <div style={{ width: '35%', background: 'var(--bg-panel)', borderLeft: '1px solid var(--border-light)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '1.1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Icons.Database /> Document Sources
              </h3>
              <button 
                onClick={() => setActiveMessageId(null)} 
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                ✖
              </button>
            </div>
            
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {activeCitations.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', textAlign: 'center', marginTop: '40px' }}>
                  <Icons.Folder />
                  <p style={{ marginTop: '8px' }}>No direct citations mapped for this response.</p>
                </div>
              ) : (
                activeCitations.map((cite) => (
                  <div key={cite.citation_idx} style={{ background: 'var(--bg-app)', border: '1px solid var(--border-medium)', borderRadius: '8px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      
                      {/* Clickable, interactive file name link */}
                      <span 
                        onClick={() => handleCitationClick(cite)}
                        style={{ 
                          fontWeight: 'bold', 
                          color: 'var(--accent-primary)', 
                          fontSize: '0.9rem',
                          cursor: 'pointer',
                          textDecoration: 'underline',
                          textUnderlineOffset: '2px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                        title="Click to open original PDF and highlight text"
                      >
                        [{cite.citation_idx}] {cite.document} 
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                      </span>

                      <span className="badge badge-info">Pg {cite.page}</span>
                    </div>
                    
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
                      Confidence Match: {(cite.score * 100).toFixed(1)}%
                    </div>
                    
                    <p style={{ fontSize: '0.9rem', color: 'var(--text-main)', lineHeight: '1.6', background: 'var(--bg-panel)', padding: '12px', borderRadius: '4px', borderLeft: '3px solid var(--accent-primary)' }}>
                      "{cite.content}"
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}