import { useState, useEffect, useRef } from 'react';
import { Send, Mic, Paperclip, Trash2, Bot, User, FileText, CheckCircle } from 'lucide-react';
import api from '../../api';

export default function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const bottomRef = useRef(null);
  const audioRef = useRef(null);
  const docRef = useRef(null);

  useEffect(() => { loadHistory(); }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadHistory() {
    try {
      const { data } = await api.get('/agent/conversations');
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
        setMessages(data.messages || []);
      }
    } catch {}
  }

  async function sendMessage(e) {
    e?.preventDefault();
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput('');
    setError(null);

    setMessages(prev => [...prev, { role: 'user', content: text, created_at: new Date().toISOString() }]);
    setLoading(true);

    try {
      const { data } = await api.post('/agent/chat', {
        message: text,
        conversation_id: conversationId,
      });
      setConversationId(data.conversation_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.image_url ? { type: 'image', url: data.image_url } : data.reply,
        intent: data.intent,
        model_used: data.model_used,
        created_at: new Date().toISOString(),
      }]);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al procesar la solicitud';
      setError(msg);
      setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ ${msg}`, created_at: new Date().toISOString() }]);
    } finally {
      setLoading(false);
    }
  }

  async function sendAudio(file) {
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post('/agent/chat/audio', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setConversationId(data.conversation_id);
      setMessages(prev => [
        ...prev,
        { role: 'user', content: `🎤 Audio: ${file.name}`, created_at: new Date().toISOString() },
        { role: 'assistant', content: data.transcription, model_used: data.model_used, created_at: new Date().toISOString() },
      ]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al transcribir audio');
    } finally {
      setLoading(false);
    }
  }

  async function uploadDoc(file) {
    setUploadingFile(true);
    setError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post('/agent/files', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const chunkInfo = data.has_text
        ? `${data.chunk_count} fragmento${data.chunk_count !== 1 ? 's' : ''} indexado${data.chunk_count !== 1 ? 's' : ''}`
        : 'sin texto extraíble';
      setMessages(prev => [...prev, {
        role: 'user',
        content: { type: 'file', name: data.filename, chunkInfo },
        created_at: new Date().toISOString(),
      }]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al subir el archivo');
    } finally {
      setUploadingFile(false);
      if (docRef.current) docRef.current.value = '';
    }
  }

  async function clearHistory() {
    await api.delete('/agent/conversations');
    setMessages([]);
    setConversationId(null);
  }

  function renderContent(content) {
    if (!content) return null;
    if (typeof content === 'object' && content.type === 'image') {
      return <img src={content.url} alt="Generated" className="agent-image" />;
    }
    if (typeof content === 'object' && content.type === 'file') {
      return (
        <div className="file-bubble">
          <FileText size={16} style={{ flexShrink: 0, color: '#a78bfa' }} />
          <div>
            <div className="file-bubble-name">{content.name}</div>
            <div className="file-bubble-meta">
              <CheckCircle size={10} style={{ color: '#22c55e' }} /> {content.chunkInfo}
            </div>
          </div>
        </div>
      );
    }
    return <span style={{ whiteSpace: 'pre-wrap' }}>{String(content)}</span>;
  }

  return (
    <div className="chat-window">
      {/* Header */}
      <div className="chat-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="chat-avatar-icon"><Bot size={18} /></div>
          <div>
            <div className="chat-title">AI Agent</div>
            <div className="chat-subtitle">Multi-model · Intent-aware · RAG</div>
          </div>
        </div>
        <button className="btn-ghost-sm" onClick={clearHistory} title="Limpiar historial">
          <Trash2 size={15} />
        </button>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <Bot size={40} style={{ color: 'rgba(139,92,246,0.4)', marginBottom: 12 }} />
            <p>¿En qué te puedo ayudar?</p>
            <p style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.25)' }}>
              Escribe, sube archivos (PDF, DOCX, TXT…) o envía audio
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble ${msg.role}`}>
            <div className="bubble-avatar">
              {msg.role === 'user' ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className="bubble-body">
              <div className="bubble-content">{renderContent(msg.content)}</div>
              {msg.model_used && (
                <div className="bubble-meta">{msg.model_used} · {msg.intent}</div>
              )}
            </div>
          </div>
        ))}
        {(loading || uploadingFile) && (
          <div className="chat-bubble assistant">
            <div className="bubble-avatar"><Bot size={14} /></div>
            <div className="bubble-body">
              <div className="typing-dots"><span /><span /><span /></div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form className="chat-input-bar" onSubmit={sendMessage}>
        {/* Hidden inputs */}
        <input
          type="file"
          ref={docRef}
          accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.py,.js,.ts,.jsx,.tsx,.yaml,.yml,.xml"
          style={{ display: 'none' }}
          onChange={e => e.target.files?.[0] && uploadDoc(e.target.files[0])}
        />
        <input
          type="file"
          ref={audioRef}
          accept="audio/*"
          style={{ display: 'none' }}
          onChange={e => e.target.files?.[0] && sendAudio(e.target.files[0])}
        />

        <button
          type="button"
          className="btn-ghost-sm"
          onClick={() => docRef.current?.click()}
          disabled={uploadingFile || loading}
          title="Subir documento (PDF, DOCX, TXT…)"
        >
          <Paperclip size={16} />
        </button>

        <button
          type="button"
          className="btn-ghost-sm"
          onClick={() => audioRef.current?.click()}
          disabled={loading || uploadingFile}
          title="Transcribir audio"
        >
          <Mic size={16} />
        </button>

        <input
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Escribe un mensaje o sube un archivo…"
          disabled={loading || uploadingFile}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(e)}
        />
        <button type="submit" className="btn-send" disabled={!input.trim() || loading || uploadingFile}>
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
