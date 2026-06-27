import { useState, useEffect, useRef } from 'react';
import { Calendar, MessageCircle, Smartphone, CheckCircle, XCircle, Plus, Loader, RefreshCw } from 'lucide-react';
import api from '../../api';

const TABS = ['outlook', 'telegram', 'whatsapp'];
const TAB_ICONS = { outlook: Calendar, telegram: MessageCircle, whatsapp: Smartphone };
const TAB_LABELS = { outlook: 'Outlook', telegram: 'Telegram', whatsapp: 'WhatsApp' };

export default function Connections() {
  const [tab, setTab] = useState('outlook');
  return (
    <div className="connections-panel">
      <div className="conn-tabs">
        {TABS.map(t => {
          const Icon = TAB_ICONS[t];
          return (
            <button key={t} className={`conn-tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              <Icon size={14} />
              <span>{TAB_LABELS[t]}</span>
            </button>
          );
        })}
      </div>
      <div className="conn-body">
        {tab === 'outlook' && <OutlookTab />}
        {tab === 'telegram' && <TelegramTab />}
        {tab === 'whatsapp' && <WhatsAppTab />}
      </div>
    </div>
  );
}

/* ── Outlook ─────────────────────────────────────────────────────────────── */

function OutlookTab() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchStatus(); }, []);

  // Handle OAuth redirect back
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('outlook') === 'connected') {
      window.history.replaceState({}, '', window.location.pathname);
      fetchStatus();
    }
  }, []);

  async function fetchStatus() {
    setLoading(true);
    try {
      const { data } = await api.get('/agent/outlook/status');
      setStatus(data);
    } catch { setStatus({ connected: false }); }
    setLoading(false);
  }

  async function connect() {
    const { data } = await api.get('/agent/outlook/auth-url');
    window.location.href = data.auth_url;
  }

  async function disconnect() {
    await api.delete('/agent/outlook/disconnect');
    setStatus({ connected: false });
  }

  if (loading) return <div className="conn-loading"><Loader size={18} className="spin" /></div>;

  return (
    <div className="conn-section">
      <div className="conn-service-header">
        <Calendar size={20} style={{ color: '#0078d4' }} />
        <span>Microsoft Outlook Calendar</span>
      </div>
      {status?.connected ? (
        <div className="conn-connected">
          <CheckCircle size={14} style={{ color: '#22c55e' }} />
          <div>
            <div style={{ fontWeight: 600 }}>{status.account_email}</div>
            <div className="conn-meta">Conectado desde {new Date(status.connected_at).toLocaleDateString()}</div>
          </div>
          <button className="btn-danger-sm" onClick={disconnect}>Desconectar</button>
        </div>
      ) : (
        <div className="conn-disconnected">
          <XCircle size={14} style={{ color: '#6b7280' }} />
          <span>No conectado</span>
          <button className="btn-primary-sm" onClick={connect}>Conectar Outlook</button>
        </div>
      )}
      <div className="conn-desc">
        Permite al agente leer y crear eventos en tu calendario de Outlook/Microsoft 365.
        El token de refresco dura al menos 90 días sin reautenticación.
      </div>
    </div>
  );
}

/* ── Telegram ────────────────────────────────────────────────────────────── */

function TelegramTab() {
  const [status, setStatus] = useState(null);
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { fetchStatus(); }, []);

  async function fetchStatus() {
    setLoading(true);
    try {
      const { data } = await api.get('/agent/telegram/status');
      setStatus(data);
    } catch { setStatus({ connected: false }); }
    setLoading(false);
  }

  async function connect() {
    setSaving(true);
    setError('');
    try {
      const { data } = await api.post('/agent/telegram/connect', { bot_token: token });
      setStatus({ connected: true, ...data });
      setToken('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Token inválido');
    }
    setSaving(false);
  }

  async function disconnect() {
    await api.delete('/agent/telegram/disconnect');
    setStatus({ connected: false });
  }

  if (loading) return <div className="conn-loading"><Loader size={18} className="spin" /></div>;

  return (
    <div className="conn-section">
      <div className="conn-service-header">
        <MessageCircle size={20} style={{ color: '#229ED9' }} />
        <span>Telegram Bot</span>
      </div>
      {status?.connected ? (
        <div className="conn-connected">
          <CheckCircle size={14} style={{ color: '#22c55e' }} />
          <div>
            <div style={{ fontWeight: 600 }}>{status.bot_username}</div>
            <div className="conn-meta">{status.webhook_registered ? 'Webhook activo' : 'Webhook pendiente'}</div>
          </div>
          <button className="btn-danger-sm" onClick={disconnect}>Desconectar</button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="conn-disconnected">
            <XCircle size={14} style={{ color: '#6b7280' }} />
            <span>No conectado</span>
          </div>
          <input
            className="conn-input"
            type="password"
            placeholder="Bot Token de @BotFather"
            value={token}
            onChange={e => setToken(e.target.value)}
          />
          {error && <div className="conn-error">{error}</div>}
          <button className="btn-primary-sm" onClick={connect} disabled={!token || saving}>
            {saving ? 'Conectando…' : 'Conectar Bot'}
          </button>
        </div>
      )}
      <div className="conn-desc">
        Crea un bot en Telegram con <strong>@BotFather</strong> (/newbot) y pega el token aquí.
        Cada mensaje al bot será respondido por el agente IA.
      </div>
    </div>
  );
}

/* ── WhatsApp ────────────────────────────────────────────────────────────── */

function WhatsAppTab() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const [qrSession, setQrSession] = useState(null);
  const [qrData, setQrData] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => { fetchSessions(); return () => clearInterval(pollRef.current); }, []);

  async function fetchSessions() {
    setLoading(true);
    try {
      const { data } = await api.get('/agent/whatsapp/sessions');
      setSessions(data.sessions || []);
    } catch {}
    setLoading(false);
  }

  async function addSession() {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      const { data } = await api.post('/agent/whatsapp/sessions', { display_name: newName });
      setNewName('');
      setQrSession(data.session_id);
      startQrPoll(data.session_id);
      await fetchSessions();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al crear sesión');
    }
    setAdding(false);
  }

  function startQrPoll(session_id) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/agent/whatsapp/sessions/${session_id}/qr`);
        setQrData(data);
        if (data.status === 'WORKING') {
          clearInterval(pollRef.current);
          setQrSession(null);
          fetchSessions();
        }
      } catch { clearInterval(pollRef.current); }
    }, 3000);
  }

  async function deleteSession(session_id) {
    await api.delete(`/agent/whatsapp/sessions/${session_id}`);
    if (qrSession === session_id) {
      clearInterval(pollRef.current);
      setQrSession(null);
      setQrData(null);
    }
    fetchSessions();
  }

  const statusColor = { WORKING: '#22c55e', SCAN_QR_CODE: '#f59e0b', STOPPED: '#ef4444', PENDING_QR: '#6b7280', UNKNOWN: '#6b7280' };

  if (loading) return <div className="conn-loading"><Loader size={18} className="spin" /></div>;

  return (
    <div className="conn-section">
      <div className="conn-service-header">
        <Smartphone size={20} style={{ color: '#25D366' }} />
        <span>WhatsApp (WAHA)</span>
      </div>

      {/* QR Code modal */}
      {qrSession && qrData && qrData.status !== 'WORKING' && (
        <div className="qr-modal">
          <div className="qr-title">Escanea con WhatsApp</div>
          {qrData.qr_base64 ? (
            <img
              src={qrData.qr_base64.startsWith('data:') ? qrData.qr_base64 : `data:image/png;base64,${qrData.qr_base64}`}
              alt="QR Code"
              className="qr-image"
            />
          ) : (
            <div className="qr-loading"><Loader size={24} className="spin" /> Generando QR…</div>
          )}
          <div className="conn-meta">Abre WhatsApp → Dispositivos vinculados → Vincular dispositivo</div>
          <button className="btn-ghost-sm" onClick={() => { clearInterval(pollRef.current); setQrSession(null); setQrData(null); }}>
            Cancelar
          </button>
        </div>
      )}

      {/* Session list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {sessions.map(s => (
          <div key={s.session_id} className="wa-session-row">
            <span className="status-dot" style={{ background: statusColor[s.status] || '#6b7280' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: '0.83rem' }}>{s.display_name}</div>
              <div className="conn-meta">{s.phone_number || s.status}</div>
            </div>
            {s.status !== 'WORKING' && (
              <button className="btn-ghost-xs" onClick={() => { setQrSession(s.session_id); startQrPoll(s.session_id); }}>
                <RefreshCw size={12} />
              </button>
            )}
            <button className="btn-danger-xs" onClick={() => deleteSession(s.session_id)}>
              <XCircle size={14} />
            </button>
          </div>
        ))}

        {/* Add account */}
        <div className="wa-add-row">
          <input
            className="conn-input"
            placeholder='Nombre (ej. "Personal")'
            value={newName}
            onChange={e => setNewName(e.target.value)}
          />
          <button className="btn-primary-sm" onClick={addSession} disabled={!newName.trim() || adding}>
            <Plus size={14} /> {adding ? 'Creando…' : 'Agregar cuenta'}
          </button>
        </div>
      </div>

      <div className="conn-desc">
        Conecta tu WhatsApp personal escaneando el código QR. Cada cuenta vinculada recibe y envía mensajes a través del agente.
        Requiere que WAHA esté ejecutándose (<code>docker run -p 3000:3000 devlikeapro/waha</code>).
      </div>
    </div>
  );
}
