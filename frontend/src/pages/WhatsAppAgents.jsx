import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Plus, Bot, Trash2, Save, Upload, FileText, X, Smartphone,
  QrCode, Power, PowerOff, LayoutTemplate, Sparkles, RefreshCw, Check,
} from 'lucide-react';
import api from '../api';

const PURPLE = '#6D28D9';
const CARD_BG = 'rgba(255,255,255,0.04)';
const BORDER = '1px solid rgba(255,255,255,0.1)';

const PROFILES = [
  ['ventas', 'Ventas'],
  ['atencion', 'Atención al cliente'],
  ['soporte_tecnico', 'Soporte técnico'],
  ['reservas', 'Reservas y citas'],
  ['general', 'General'],
];

const STATUS_LABEL = {
  WORKING: { t: 'Conectado', c: '#4ade80' },
  SCAN_QR_CODE: { t: 'Escanea el QR', c: '#fbbf24' },
  STARTING: { t: 'Iniciando…', c: '#fbbf24' },
  PENDING_QR: { t: 'Esperando QR', c: '#fbbf24' },
  STOPPED: { t: 'Detenido', c: '#f87171' },
  FAILED: { t: 'Falló', c: '#f87171' },
};

// ── small UI helpers ──────────────────────────────────────────────────────────
const btn = (bg, extra = {}) => ({
  display: 'inline-flex', alignItems: 'center', gap: 7, padding: '9px 15px',
  borderRadius: 10, border: 'none', cursor: 'pointer', fontWeight: 600,
  fontSize: '0.82rem', color: '#fff', background: bg, ...extra,
});
const input = {
  width: '100%', padding: '10px 12px', borderRadius: 10, background: 'rgba(255,255,255,0.05)',
  border: BORDER, color: 'var(--text-main, #ede9fe)', fontSize: '0.86rem', boxSizing: 'border-box',
  fontFamily: 'inherit',
};
const label = { fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.04em', color: '#a78bfa', textTransform: 'uppercase', marginBottom: 6, display: 'block' };

function Card({ children, style }) {
  return <div style={{ background: CARD_BG, border: BORDER, borderRadius: 16, padding: 18, ...style }}>{children}</div>;
}

export default function WhatsAppAgents() {
  const [agents, setAgents] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');

  const flash = (m) => { setToast(m); setTimeout(() => setToast(''), 2600); };

  const loadAgents = useCallback(async () => {
    try {
      const res = await api.get('/agent/wa-agents');
      setAgents(res.data.agents || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  const loadTemplates = useCallback(async () => {
    try {
      const res = await api.get('/agent/wa-agent-templates');
      setTemplates(res.data.templates || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadAgents(); loadTemplates(); }, [loadAgents, loadTemplates]);

  const selected = agents.find(a => a._id === selectedId) || null;

  const createBlank = async () => {
    const res = await api.post('/agent/wa-agents', {
      name: 'Nuevo agente', profile: 'general',
      system_prompt: 'Eres un asistente que atiende por WhatsApp. Responde de forma clara y amable.',
      greeting: '¡Hola! 👋 ¿En qué puedo ayudarte?',
    });
    await loadAgents();
    setSelectedId(res.data._id);
    flash('Agente creado');
  };

  const createFromTemplate = async (template_id) => {
    const res = await api.post('/agent/wa-agents/from-template', { template_id });
    await loadAgents();
    setSelectedId(res.data._id);
    setShowTemplates(false);
    flash('Agente creado desde plantilla');
  };

  return (
    <div className="wa-page" style={{ padding: '26px clamp(16px, 4vw, 40px)', maxWidth: 1280, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ display: 'inline-flex', width: 40, height: 40, borderRadius: 12, background: `linear-gradient(135deg,${PURPLE},#4C1D95)`, alignItems: 'center', justifyContent: 'center' }}>
              <Bot size={22} color="#e9d5ff" />
            </span>
            Agentes de WhatsApp
          </h1>
          <p style={{ margin: '6px 0 0', color: 'var(--text-muted, #94a3b8)', fontSize: '0.88rem' }}>
            Configura multiagentes de IA que atienden por WhatsApp (WAHA), cada uno con su número y su propia base de conocimiento.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button onClick={() => { loadTemplates(); setShowTemplates(true); }} style={btn('rgba(255,255,255,0.08)', { border: BORDER })}>
            <LayoutTemplate size={16} /> Plantillas
          </button>
          <button onClick={createBlank} style={btn(`linear-gradient(135deg,${PURPLE},#4C1D95)`)}>
            <Plus size={16} /> Nuevo agente
          </button>
        </div>
      </div>

      {toast && (
        <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 10, background: 'rgba(74,222,128,0.12)', border: '1px solid rgba(74,222,128,0.3)', color: '#4ade80', fontSize: '0.84rem', display: 'flex', gap: 8, alignItems: 'center' }}>
          <Check size={15} /> {toast}
        </div>
      )}

      <div className="wa-layout" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 320px) minmax(0, 1fr)', gap: 20, alignItems: 'start' }}>
        {/* ── Agent list ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {loading && <Card><span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Cargando…</span></Card>}
          {!loading && agents.length === 0 && (
            <Card style={{ textAlign: 'center' }}>
              <Sparkles size={26} color="#a78bfa" style={{ margin: '4px auto 8px' }} />
              <div style={{ fontSize: '0.88rem', color: '#cbd5e1', marginBottom: 4 }}>Aún no tienes agentes</div>
              <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Crea uno desde cero o usa una plantilla.</div>
            </Card>
          )}
          {agents.map(a => {
            const st = a.session_status?.status;
            const stInfo = STATUS_LABEL[st] || (st ? { t: st, c: '#94a3b8' } : { t: 'Sin número', c: '#64748b' });
            const active = a._id === selectedId;
            return (
              <div key={a._id} onClick={() => setSelectedId(a._id)}
                style={{
                  cursor: 'pointer', borderRadius: 14, padding: 14,
                  background: active ? 'rgba(109,40,217,0.18)' : CARD_BG,
                  border: active ? '1px solid rgba(139,92,246,0.6)' : BORDER,
                  transition: 'background .15s, border-color .15s',
                }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#ede9fe', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</span>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: a.enabled ? '#4ade80' : '#64748b', flexShrink: 0 }} />
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  <Tag>{(PROFILES.find(p => p[0] === a.profile) || [, a.profile])[1]}</Tag>
                  <Tag color={stInfo.c}>{stInfo.t}</Tag>
                  {a.file_count > 0 && <Tag><FileText size={11} style={{ marginRight: 3, verticalAlign: -1 }} />{a.file_count}</Tag>}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Detail ── */}
        <div>
          {selected
            ? <AgentDetail key={selected._id} agent={selected} onChanged={loadAgents}
                onDeleted={() => { setSelectedId(null); loadAgents(); }}
                onTemplateSaved={loadTemplates} flash={flash} />
            : <Card style={{ textAlign: 'center', padding: 48, color: '#94a3b8' }}>
                <Bot size={34} color="#7c3aed" style={{ marginBottom: 10 }} />
                <div style={{ fontSize: '0.95rem' }}>Selecciona un agente para configurarlo</div>
              </Card>}
        </div>
      </div>

      {/* Template picker modal */}
      {showTemplates && (
        <Modal title="Plantillas de agentes" onClose={() => setShowTemplates(false)}>
          <p style={{ color: '#94a3b8', fontSize: '0.82rem', marginTop: 0 }}>
            Al usar una plantilla se crea un agente con los prompts predefinidos. No incluye número ni archivos.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
            {templates.map(t => (
              <div key={t._id} style={{ border: BORDER, borderRadius: 12, padding: 14, background: CARD_BG, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                  <span style={{ fontWeight: 700, color: '#ede9fe' }}>{t.name}</span>
                  {t.built_in ? <Tag color="#a78bfa">Base</Tag> : <Tag color="#38bdf8">Mía</Tag>}
                </div>
                <div style={{ fontSize: '0.76rem', color: '#94a3b8', flex: 1, minHeight: 32 }}>{t.description}</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => createFromTemplate(t._id)} style={{ ...btn(`linear-gradient(135deg,${PURPLE},#4C1D95)`), flex: 1, justifyContent: 'center', padding: '8px 10px' }}>
                    Usar
                  </button>
                  {!t.built_in && (
                    <button title="Eliminar plantilla"
                      onClick={async () => { await api.delete(`/agent/wa-agent-templates/${t._id}`); loadTemplates(); }}
                      style={btn('rgba(248,113,113,0.14)', { padding: '8px 10px', color: '#f87171' })}>
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}

      <style>{`
        @media (max-width: 768px) {
          .wa-page { padding-left: 14px !important; padding-right: 14px !important; }
          .wa-layout { grid-template-columns: 1fr !important; }
          .wa-page button { min-height: 40px; }
        }
      `}</style>
    </div>
  );
}

function Tag({ children, color = '#cbd5e1' }) {
  return (
    <span style={{
      fontSize: '0.68rem', fontWeight: 600, padding: '3px 8px', borderRadius: 7,
      background: 'rgba(255,255,255,0.06)', color, border: '1px solid rgba(255,255,255,0.08)',
    }}>{children}</span>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(3px)', zIndex: 300, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '6vh 16px', overflowY: 'auto' }}>
      <div onClick={e => e.stopPropagation()} style={{ width: 'min(760px, 100%)', maxWidth: '100%', maxHeight: '88vh', overflowY: 'auto', background: 'linear-gradient(180deg,#12102a,#0d0b1f)', border: BORDER, borderRadius: 18, padding: 'clamp(16px, 4vw, 22px)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800 }}>{title}</h3>
          <button onClick={onClose} style={btn('rgba(255,255,255,0.06)', { padding: 8, border: BORDER })}><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ── Detail / editor ───────────────────────────────────────────────────────────
function AgentDetail({ agent, onChanged, onDeleted, onTemplateSaved, flash }) {
  const [form, setForm] = useState({
    name: agent.name, profile: agent.profile, system_prompt: agent.system_prompt,
    greeting: agent.greeting, temperature: agent.temperature ?? 0.5, enabled: agent.enabled,
  });
  const [saving, setSaving] = useState(false);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [qr, setQr] = useState(null);
  const [showQr, setShowQr] = useState(false);
  const fileRef = useRef(null);
  const pollRef = useRef(null);
  const id = agent._id;

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  const loadFiles = useCallback(async () => {
    try { const r = await api.get(`/agent/wa-agents/${id}/files`); setFiles(r.data.files || []); } catch { /* */ }
  }, [id]);
  useEffect(() => { loadFiles(); }, [loadFiles]);

  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/agent/wa-agents/${id}`, {
        ...form, temperature: parseFloat(form.temperature) || 0.5,
      });
      await onChanged();
      flash('Cambios guardados');
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!window.confirm('¿Eliminar este agente, su número y su base de conocimiento?')) return;
    await api.delete(`/agent/wa-agents/${id}`);
    onDeleted();
  };

  const saveTemplate = async () => {
    const name = window.prompt('Nombre de la plantilla:', form.name);
    if (name === null) return;
    await api.post(`/agent/wa-agents/${id}/save-as-template`, { name });
    onTemplateSaved();
    flash('Plantilla guardada (solo prompts)');
  };

  const doUpload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      await api.post(`/agent/wa-agents/${id}/files`, fd);
      await loadFiles();
      await onChanged();
      flash('Archivo agregado a la base de conocimiento');
    } catch (err) {
      flash(err?.response?.data?.detail || 'No se pudo subir el archivo');
    } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; }
  };

  const delFile = async (fid) => {
    await api.delete(`/agent/wa-agents/${id}/files/${fid}`);
    await loadFiles(); await onChanged();
  };

  // ── WhatsApp connection ──
  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  useEffect(() => stopPoll, []);

  const pollQr = useCallback(async () => {
    try {
      const r = await api.get(`/agent/wa-agents/${id}/session/qr`);
      setQr(r.data);
      if (r.data.status === 'WORKING') { stopPoll(); setShowQr(false); onChanged(); flash('WhatsApp conectado ✅'); }
    } catch { /* */ }
  }, [id, onChanged]);

  const connect = async () => {
    setShowQr(true); setQr({ status: 'STARTING' });
    await api.post(`/agent/wa-agents/${id}/session`);
    await onChanged();
    stopPoll();
    pollRef.current = setInterval(pollQr, 2500);
    pollQr();
  };

  const disconnect = async () => {
    stopPoll(); setShowQr(false); setQr(null);
    await api.delete(`/agent/wa-agents/${id}/session`);
    await onChanged();
    flash('Número desconectado');
  };

  const ss = agent.session_status;
  const connected = ss?.status === 'WORKING';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Persona */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800 }}>Configuración del agente</h3>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: '0.82rem', color: '#cbd5e1', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.enabled} onChange={set('enabled')} style={{ width: 16, height: 16, accentColor: PURPLE }} />
            {form.enabled ? 'Activo' : 'Inactivo'}
          </label>
        </div>

        <div className="wa-grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div>
            <label style={label}>Nombre</label>
            <input style={input} value={form.name} onChange={set('name')} placeholder="Ej. Ventas Tienda X" />
          </div>
          <div>
            <label style={label}>Perfil</label>
            <select style={input} value={form.profile} onChange={set('profile')}>
              {PROFILES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        </div>

        <div style={{ marginTop: 14 }}>
          <label style={label}>Mensaje de bienvenida</label>
          <input style={input} value={form.greeting} onChange={set('greeting')} placeholder="Se envía al primer mensaje del cliente" />
        </div>

        <div style={{ marginTop: 14 }}>
          <label style={label}>Prompt / instrucciones</label>
          <textarea style={{ ...input, minHeight: 150, resize: 'vertical', lineHeight: 1.5 }} value={form.system_prompt} onChange={set('system_prompt')}
            placeholder="Describe la personalidad, el objetivo y las reglas del agente…" />
        </div>

        <div style={{ marginTop: 14, maxWidth: 260 }}>
          <label style={label}>Creatividad ({parseFloat(form.temperature).toFixed(1)})</label>
          <input type="range" min="0" max="1.2" step="0.1" value={form.temperature} onChange={set('temperature')} style={{ width: '100%', accentColor: PURPLE }} />
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 18, flexWrap: 'wrap' }}>
          <button onClick={save} disabled={saving} style={btn(`linear-gradient(135deg,${PURPLE},#4C1D95)`, { opacity: saving ? 0.6 : 1 })}>
            <Save size={16} /> {saving ? 'Guardando…' : 'Guardar'}
          </button>
          <button onClick={saveTemplate} style={btn('rgba(255,255,255,0.08)', { border: BORDER })}>
            <LayoutTemplate size={16} /> Guardar como plantilla
          </button>
          <button onClick={remove} style={btn('rgba(248,113,113,0.14)', { color: '#f87171', marginLeft: 'auto' })}>
            <Trash2 size={16} /> Eliminar
          </button>
        </div>
      </Card>

      {/* WhatsApp number */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <Smartphone size={18} color="#a78bfa" />
          <h3 style={{ margin: 0, fontSize: '1.02rem', fontWeight: 800 }}>Número de WhatsApp</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
            {connected
              ? <><span style={{ color: '#4ade80', fontWeight: 700 }}>● Conectado</span>{ss?.phone_number ? ` · ${ss.phone_number}` : ''}</>
              : ss?.session_id
                ? <span style={{ color: '#fbbf24' }}>● {STATUS_LABEL[ss.status]?.t || ss.status}</span>
                : <span style={{ color: '#94a3b8' }}>Sin número vinculado</span>}
          </div>
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
            {!connected && (
              <button onClick={connect} style={btn(`linear-gradient(135deg,#25D366,#128C7E)`)}>
                <QrCode size={16} /> {ss?.session_id ? 'Ver QR' : 'Conectar número'}
              </button>
            )}
            {ss?.session_id && (
              <button onClick={disconnect} style={btn('rgba(248,113,113,0.14)', { color: '#f87171' })}>
                {connected ? <PowerOff size={16} /> : <X size={16} />} Desconectar
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* Knowledge base */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <FileText size={18} color="#a78bfa" />
            <h3 style={{ margin: 0, fontSize: '1.02rem', fontWeight: 800 }}>Base de conocimiento (RAG)</h3>
          </div>
          <button onClick={() => fileRef.current?.click()} disabled={uploading} style={btn('rgba(255,255,255,0.08)', { border: BORDER, opacity: uploading ? 0.6 : 1 })}>
            <Upload size={15} /> {uploading ? 'Subiendo…' : 'Subir archivo'}
          </button>
          <input ref={fileRef} type="file" hidden onChange={doUpload}
            accept=".pdf,.docx,.doc,.txt,.md,.csv,.json" />
        </div>
        <p style={{ margin: '0 0 12px', fontSize: '0.76rem', color: '#94a3b8' }}>
          Sube PDF, Word, TXT, CSV o Markdown. El agente usará su contenido para responder con precisión.
        </p>
        {files.length === 0
          ? <div style={{ fontSize: '0.82rem', color: '#64748b', padding: '8px 0' }}>Aún no hay archivos.</div>
          : <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {files.map(f => (
                <div key={f._id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 10, background: 'rgba(255,255,255,0.03)', border: BORDER }}>
                  <FileText size={15} color="#a78bfa" style={{ flexShrink: 0 }} />
                  <span style={{ fontSize: '0.82rem', color: '#ede9fe', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{f.filename}</span>
                  {f.has_text
                    ? <Tag color="#4ade80">{f.chunk_count} frag.</Tag>
                    : <Tag color="#fbbf24">sin texto</Tag>}
                  <button onClick={() => delFile(f._id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#f87171', display: 'flex', padding: 3 }}><Trash2 size={14} /></button>
                </div>
              ))}
            </div>}
      </Card>

      {/* QR modal */}
      {showQr && (
        <Modal title="Conectar WhatsApp" onClose={() => { stopPoll(); setShowQr(false); }}>
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: '#94a3b8', fontSize: '0.84rem', marginTop: 0 }}>
              Abre WhatsApp → Dispositivos vinculados → Vincular dispositivo, y escanea el código.
            </p>
            <div style={{ minHeight: 240, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {qr?.qr_base64
                ? <img src={qr.qr_base64} alt="QR" style={{ width: 240, height: 240, borderRadius: 12, background: '#fff', padding: 8 }} />
                : qr?.status === 'WORKING'
                  ? <div style={{ color: '#4ade80', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}><Check size={40} /> Conectado</div>
                  : <div style={{ color: '#a78bfa', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
                      <RefreshCw size={30} className="wa-spin" /> Generando QR…
                    </div>}
            </div>
            <div style={{ fontSize: '0.76rem', color: '#64748b' }}>Estado: {STATUS_LABEL[qr?.status]?.t || qr?.status || '—'}</div>
          </div>
        </Modal>
      )}

      <style>{`
        .wa-spin { animation: waSpin 1s linear infinite; }
        @keyframes waSpin { to { transform: rotate(360deg); } }
        @media (max-width: 768px) {
          .wa-grid-2 { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
