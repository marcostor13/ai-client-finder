import { useState, useEffect, useRef } from 'react';
import { Send, Mic, Paperclip, Trash2, Bot, User, FileText, Download } from 'lucide-react';
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

  // Build an assistant message object from a chat/upload/audio response.
  function assistantFromData(data) {
    return {
      role: 'assistant',
      content: data.reply || '',
      image_url: data.image_url || null,
      audio_b64: data.audio_b64 || null,
      file: data.file || null,
      intent: data.intent,
      model_used: data.model_used,
      created_at: new Date().toISOString(),
    };
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
      const { data } = await api.post('/agent/chat', { message: text, conversation_id: conversationId });
      setConversationId(data.conversation_id);
      setMessages(prev => [...prev, assistantFromData(data)]);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al procesar la solicitud';
      setError(msg);
      setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ ${msg}`, created_at: new Date().toISOString() }]);
    } finally {
      setLoading(false);
    }
  }

  // Voice message in → reply spoken back (audio out).
  async function sendAudio(file) {
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.append('file', file);
    if (conversationId) form.append('conversation_id', conversationId);
    try {
      const { data } = await api.post('/agent/chat/audio', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setConversationId(data.conversation_id);
      setMessages(prev => [
        ...prev,
        { role: 'user', content: `🎤 ${data.transcription || file.name}`, created_at: new Date().toISOString() },
        assistantFromData(data),
      ]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al procesar el audio');
    } finally {
      setLoading(false);
      if (audioRef.current) audioRef.current.value = '';
    }
  }

  // Any file in → analysed and answered (image=vision, audio=stt, docs=extract…).
  async function uploadFile(file) {
    setUploadingFile(true);
    setError(null);
    setMessages(prev => [...prev, {
      role: 'user',
      content: { type: 'file', name: file.name },
      created_at: new Date().toISOString(),
    }]);
    const form = new FormData();
    form.append('file', file);
    if (conversationId) form.append('conversation_id', conversationId);
    try {
      const { data } = await api.post('/agent/chat/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setConversationId(data.conversation_id);
      setMessages(prev => [...prev, assistantFromData(data)]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al procesar el archivo');
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
    if (content === null || content === undefined || content === '') return null;
    if (typeof content === 'object' && content.type === 'image') {
      return <img src={content.url} alt="imagen" className="agent-image" />;
    }
    if (typeof content === 'object' && content.type === 'file') {
      return (
        <div className="file-bubble">
          <FileText size={16} style={{ flexShrink: 0, color: '#a78bfa' }} />
          <div className="file-bubble-name">{content.name}</div>
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
            <div className="chat-subtitle">Multimodal · Voz · Visión · Imágenes · RAG</div>
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
              Escribe, envía audio (te respondo con voz), sube imágenes o cualquier archivo, o pídeme imágenes
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble ${msg.role}`}>
            <div className="bubble-avatar">
              {msg.role === 'user' ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className="bubble-body">
              {(msg.content !== null && msg.content !== undefined && msg.content !== '') && (
                <div className="bubble-content">{renderContent(msg.content)}</div>
              )}
              {msg.image_url && (
                <img src={msg.image_url} alt="imagen generada" className="agent-image" />
              )}
              {msg.audio_b64 && (
                <audio controls src={msg.audio_b64} style={{ marginTop: 8, width: '100%', maxWidth: 320 }} />
              )}
              {msg.file && (
                <a
                  className="file-bubble"
                  href={`data:${msg.file.mime || 'application/octet-stream'};base64,${msg.file.content_b64}`}
                  download={msg.file.filename}
                  style={{ textDecoration: 'none', marginTop: 8 }}
                >
                  <Download size={16} style={{ flexShrink: 0, color: '#a78bfa' }} />
                  <div className="file-bubble-name">{msg.file.filename}</div>
                </a>
              )}
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
        {/* Hidden inputs — any file type accepted */}
        <input
          type="file"
          ref={docRef}
          style={{ display: 'none' }}
          onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0])}
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
          title="Subir cualquier archivo (imagen, PDF, audio…) y analizarlo"
        >
          <Paperclip size={16} />
        </button>

        <button
          type="button"
          className="btn-ghost-sm"
          onClick={() => audioRef.current?.click()}
          disabled={loading || uploadingFile}
          title="Enviar audio (te respondo con voz)"
        >
          <Mic size={16} />
        </button>

        <input
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Escribe, envía audio o sube cualquier archivo…"
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
