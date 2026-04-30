// src/pages/QueryLogsPage.jsx
import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api, Icons, useApp } from '../store';
import '../styles/QueryLogsPage.css';

export default function QueryLogsPage() {
  const { 
    documents, 
    conversations, setConversations, 
    activeChatId, setActiveChatId,
    fetchLogs, fetchMetrics 
  } = useApp();

  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isTTSActive, setIsTTSActive] = useState(false); // TTS State
  const messagesEndRef = useRef(null);

  const hasDocuments = documents.length > 0;
  const activeChat = conversations.find(c => c.id === activeChatId) || null;

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

  const speakText = (text) => {
    if (!('speechSynthesis' in window)) return;
    
    // Stop any ongoing speech before starting a new one
    window.speechSynthesis.cancel();
    
    // Clean markdown characters (**, ##, _, `) so they aren't spoken aloud
    const cleanText = text.replace(/[*#_`~]/g, '');
    
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0; // Normal speed
    window.speechSynthesis.speak(utterance);
  };

  const handleNewChat = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    setActiveChatId(null);
  };

  const handleDeleteChat = (e, id) => {
    e.stopPropagation();
    if (window.confirm("Delete this conversation?")) {
      setConversations(prev => prev.filter(c => c.id !== id));
      if (activeChatId === id) {
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        setActiveChatId(null);
      }
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !hasDocuments || isTyping) return;

    if ('speechSynthesis' in window) window.speechSynthesis.cancel(); // Stop speaking previous msg

    const userQuery = input.trim();
    setInput('');
    setIsTyping(true);

    let currentChatId = activeChatId;
    const userMsg = { role: 'user', content: userQuery };

    // Generate new persistent conversation if starting fresh
    if (!currentChatId) {
      currentChatId = Date.now().toString();
      const newChat = {
        id: currentChatId,
        title: userQuery.length > 25 ? userQuery.substring(0, 25) + '...' : userQuery,
        createdAt: Date.now(),
        messages: [userMsg]
      };
      setConversations(prev => [newChat, ...prev]);
      setActiveChatId(currentChatId);
    } else {
      setConversations(prev => prev.map(c => 
        c.id === currentChatId ? { ...c, messages: [...c.messages, userMsg] } : c
      ));
    }

    try {
      const data = await api.chat(userQuery, currentChatId);
      
      const aiMsg = { role: 'ai', content: data.response };
      
      setConversations(prev => prev.map(c => 
        c.id === currentChatId ? { ...c, messages: [...c.messages, aiMsg] } : c
      ));

      // Trigger Text-to-Speech if enabled
      if (isTTSActive) {
        speakText(data.response);
      }
      
      fetchLogs();
      fetchMetrics();
    } catch (error) {
      const errorMsg = { role: 'ai', content: `Error: ${error.message}` };
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
      window.speechSynthesis.cancel(); // Stop speaking immediately if turned off
    }
  };

  return (
    <div className="unified-chat-layout">
      {/* Persistent Left Sidebar for Conversation History */}
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
                onClick={() => setActiveChatId(chat.id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                  <Icons.MessageSquare />
                  <span style={{ whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {chat.title}
                  </span>
                </div>
                <button 
                  className="delete-chat-icon" 
                  onClick={(e) => handleDeleteChat(e, chat.id)}
                  title="Delete Chat"
                >
                  <Icons.Trash />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="chat-main-area">
        {!hasDocuments && (
          <div className="warning-banner">
            ⚠️ No documents uploaded. Please upload documents in the "Documents" tab before asking AI.
          </div>
        )}

        <div className="chat-messages-container">
          {!activeChat ? (
            <div className="empty-chat-state">
              <div className="empty-chat-icon"><Icons.Bot /></div>
              <h2>How can I help you today?</h2>
              <p>Type a message below to start a new conversation using your securely uploaded knowledge base.</p>
            </div>
          ) : (
            activeChat.messages.map((msg, idx) => (
              <div key={idx} className={`message-row ${msg.role}`}>
                <div className={`avatar ${msg.role}`}>
                  {msg.role === 'ai' ? <Icons.Bot /> : <Icons.User />}
                </div>
                <div className="message-content">
                  <div className={`bubble ${msg.content && msg.content.startsWith('Error:') ? 'error-bubble' : ''}`}>
                    {msg.role === 'ai' && !msg.content.startsWith('Error:') ? (
                      <div className="markdown-body">
                        <ReactMarkdown>
                          {msg.content}
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
        <div className="chat-input-area">
          <form className="input-wrapper" onSubmit={handleSend}>
            <input 
              type="text" 
              placeholder={hasDocuments ? "Message Ask AI..." : "Upload documents to begin..."}
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
            AI can make mistakes. Verify important information.
          </div>
        </div>
      </div>
    </div>
  );
}