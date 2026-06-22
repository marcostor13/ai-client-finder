import { useState, useEffect } from 'react';
import {
  Send, RefreshCw, MessageCircle, Loader2,
  AlertCircle, MailOpen, Mail, XCircle, TrendingUp,
} from 'lucide-react';
import api from '../api';

const STATUS_CFG = {
  sent:    { label: 'Enviado',    color: '#60a5fa', bg: 'rgba(59,130,246,0.15)',  border: 'rgba(59,130,246,0.4)' },
  replied: { label: 'Respondió', color: '#22c55e', bg: 'rgba(34,197,94,0.15)',   border: 'rgba(34,197,94,0.4)' },
  bounced: { label: 'Rebotó',    color: '#ef4444', bg: 'rgba(239,68,68,0.15)',   border: 'rgba(239,68,68,0.4)' },
};

function StatusBadge({ status }) {
  const c = STATUS_CFG[status] || STATUS_CFG.sent;
  return (
    <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '3px 10px', borderRadius: '20px', background: c.bg, color: c.color, border: `1px solid ${c.border}`, whiteSpace: 'nowrap' }}>
      {c.label}
    </span>
  );
}

function SentCard({ email, onReply, onBounce }) {
  const [expanded, setExpanded] = useState(false);
  const [replying, setReplying] = useState(false);
  const [notes, setNotes] = useState(email.reply_notes || '');
  const [saving, setSaving] = useState(false);

  async function confirmReply() {
    setSaving(true);
    await onReply(email._id, notes);
    setSaving(false);
    setReplying(false);
  }

  const fmt = iso => iso
    ? new Date(iso).toLocaleDateString('es-PE', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '—';

  const inputStyle = {
    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(34,197,94,0.4)',
    borderRadius: '8px', padding: '8px 11px', color: 'var(--text-main)',
    fontSize: '0.84rem', fontFamily: 'inherit', resize: 'vertical', outline: 'none', width: '100%',
  };

  return (
    <div style={{
      background: 'var(--bg-card)', border: `1px solid ${email.status === 'replied' ? 'rgba(34,197,94,0.35)' : 'var(--glass-border)'}`,
      borderRadius: '14px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px',
      backdropFilter: 'blur(12px)',
      boxShadow: email.status === 'replied' ? '0 0 0 1px rgba(34,197,94,0.15)' : 'none',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>{email.company_name}</span>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {email.contact_full_name && `${email.contact_full_name} · `}
            <span style={{ fontFamily: 'monospace' }}>{email.contact_email}</span>
          </span>
        </div>
        <StatusBadge status={email.status} />
      </div>

      {/* Subject */}
      <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{email.subject}</div>

      {/* Dates */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
        <span>📤 {fmt(email.sent_at)}</span>
        {email.reply_received_at && (
          <span style={{ color: '#22c55e' }}>💬 Respondió el {fmt(email.reply_received_at)}</span>
        )}
      </div>

      {/* Reply notes */}
      {email.reply_notes && (
        <div style={{ background: 'rgba(34,197,94,0.07)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: '8px', padding: '10px 14px', fontSize: '0.82rem', color: '#86efac', fontStyle: 'italic' }}>
          "{email.reply_notes}"
        </div>
      )}

      {/* Expanded body */}
      {expanded && (
        <pre style={{ fontSize: '0.83rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap', lineHeight: 1.7, background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', margin: 0, fontFamily: 'inherit' }}>
          {email.body_text}
        </pre>
      )}

      {/* Reply form */}
      {replying && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', background: 'rgba(34,197,94,0.08)', borderRadius: '10px', border: '1px solid rgba(34,197,94,0.25)' }}>
          <span style={{ fontSize: '0.8rem', color: '#86efac', fontWeight: 600 }}>¿Qué respondió el cliente?</span>
          <textarea
            autoFocus
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={2}
            placeholder="Ej: Está interesado, quiere reunirse la próxima semana..."
            style={inputStyle}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={confirmReply} disabled={saving} style={{ flex: 1, padding: '8px', background: 'rgba(34,197,94,0.25)', border: '1px solid rgba(34,197,94,0.4)', borderRadius: '8px', color: '#86efac', cursor: 'pointer', fontSize: '0.82rem', fontFamily: 'inherit', fontWeight: 600 }}>
              {saving ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : 'Guardar respuesta'}
            </button>
            <button onClick={() => setReplying(false)} style={{ padding: '8px 14px', background: 'none', border: '1px solid var(--glass-border)', borderRadius: '8px', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.82rem', fontFamily: 'inherit' }}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      {!replying && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setExpanded(v => !v)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--glass-border)', borderRadius: '8px', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem', fontFamily: 'inherit' }}
          >
            {expanded ? <MailOpen size={13} /> : <Mail size={13} />}
            {expanded ? 'Ocultar email' : 'Ver email'}
          </button>

          {email.status !== 'bounced' && (
            <button
              onClick={() => { setNotes(email.reply_notes || ''); setReplying(true); }}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.35)', borderRadius: '8px', color: '#86efac', cursor: 'pointer', fontSize: '0.8rem', fontFamily: 'inherit', fontWeight: 600 }}
            >
              <MessageCircle size={13} />
              {email.status === 'replied' ? 'Editar respuesta' : 'Respondió'}
            </button>
          )}

          {email.status === 'sent' && (
            <button
              onClick={() => onBounce(email._id)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', background: 'none', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '8px', color: '#fca5a5', cursor: 'pointer', fontSize: '0.8rem', fontFamily: 'inherit', opacity: 0.7 }}
            >
              <XCircle size={13} /> Rebotó
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const TABS = [
  { key: null,      label: 'Todos' },
  { key: 'sent',    label: 'Enviados' },
  { key: 'replied', label: 'Respondieron' },
  { key: 'bounced', label: 'Rebotaron' },
];

export default function SentEmails() {
  const [emails, setEmails] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(null);
  const [toast, setToast] = useState(null);

  function showToast(msg, type = 'success') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  async function fetchEmails(tab) {
    setLoading(true);
    setError('');
    try {
      const qs = tab ? `?status=${tab}&limit=200` : '?limit=200';
      const res = await api.get(`/api/outbound/sent${qs}`);
      setEmails(res.data.emails);
      setTotal(res.data.total);
    } catch {
      setError('No se pudo cargar los emails enviados. ¿El backend está corriendo?');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchEmails(activeTab); }, [activeTab]);

  async function handleReply(draftId, notes) {
    try {
      await api.post(`/api/outbound/sent/${draftId}/reply`, { notes });
      setEmails(prev => prev.map(e =>
        e._id === draftId
          ? { ...e, status: 'replied', reply_notes: notes, reply_received_at: new Date().toISOString() }
          : e
      ));
      showToast('Respuesta registrada');
    } catch {
      showToast('Error al guardar la respuesta', 'error');
    }
  }

  async function handleBounce(draftId) {
    try {
      await api.post(`/api/outbound/sent/${draftId}/bounce`);
      setEmails(prev => prev.map(e => e._id === draftId ? { ...e, status: 'bounced' } : e));
      showToast('Marcado como rebotado');
    } catch {
      showToast('Error', 'error');
    }
  }

  const allSent = emails.length;
  const replied = emails.filter(e => e.status === 'replied').length;
  const rate = allSent > 0 ? Math.round((replied / allSent) * 100) : 0;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-deep)' }}>


      <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px 20px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{ width: '44px', height: '44px', borderRadius: '13px', background: 'rgba(109,40,217,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <Send size={21} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.3rem', fontWeight: 800 }}>Emails Enviados</h1>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {loading ? 'Cargando…' : `${total} email${total !== 1 ? 's' : ''} en total`}
              </p>
            </div>
          </div>
          <button
            onClick={() => fetchEmails(activeTab)}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--glass-border)', borderRadius: '8px', padding: '8px 14px', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem', fontFamily: 'inherit', flexShrink: 0 }}
          >
            {loading ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <RefreshCw size={13} />}
            Actualizar
          </button>
        </div>

        {/* Stats */}
        {!loading && total > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {[
              { label: 'Total enviados', value: total,    color: '#60a5fa' },
              { label: 'Respondieron',   value: replied,  color: '#22c55e' },
              { label: 'Tasa respuesta', value: `${rate}%`, color: rate >= 20 ? '#22c55e' : rate >= 10 ? '#eab308' : '#f87171' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ background: 'var(--bg-card)', border: '1px solid var(--glass-border)', borderRadius: '12px', padding: '16px', textAlign: 'center', backdropFilter: 'blur(8px)' }}>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, color }}>{value}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '4px', border: '1px solid var(--glass-border)' }}>
          {TABS.map(tab => (
            <button
              key={String(tab.key)}
              onClick={() => setActiveTab(tab.key)}
              style={{
                flex: 1, padding: '7px 10px', borderRadius: '7px', border: 'none', cursor: 'pointer',
                fontSize: '0.8rem', fontFamily: 'inherit', fontWeight: activeTab === tab.key ? 700 : 400,
                background: activeTab === tab.key ? 'rgba(109,40,217,0.5)' : 'transparent',
                color: activeTab === tab.key ? '#e9d5ff' : 'var(--text-muted)',
                transition: 'all 0.15s',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '10px', padding: '12px 16px', color: '#fca5a5', fontSize: '0.85rem' }}>
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {/* Empty */}
        {!loading && !error && emails.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px', padding: '64px 20px', color: 'var(--text-muted)', textAlign: 'center' }}>
            <div style={{ width: '60px', height: '60px', borderRadius: '18px', background: 'rgba(109,40,217,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <TrendingUp size={28} style={{ color: 'rgba(109,40,217,0.5)' }} />
            </div>
            <div>
              <p style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>Sin emails enviados aún</p>
              <p style={{ fontSize: '0.84rem' }}>Los emails aparecerán aquí automáticamente cuando apruebes drafts en la cola.</p>
            </div>
            <button
              onClick={() => navigate('/outbound/approvals')}
              style={{ padding: '10px 20px', background: 'rgba(109,40,217,0.25)', border: '1px solid rgba(167,139,250,0.4)', borderRadius: '10px', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.86rem', fontFamily: 'inherit', fontWeight: 600 }}
            >
              Ir a la cola de aprobación
            </button>
          </div>
        )}

        {/* List */}
        {!loading && emails.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {emails.map(email => (
              <SentCard key={email._id} email={email} onReply={handleReply} onBounce={handleBounce} />
            ))}
          </div>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '24px',
          background: toast.type === 'error' ? 'rgba(239,68,68,0.95)' : 'rgba(34,197,94,0.95)',
          color: '#fff', borderRadius: '10px', padding: '12px 20px',
          fontSize: '0.88rem', fontWeight: 600, boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
          animation: 'fadeIn 0.2s ease', zIndex: 50,
        }}>
          {toast.msg}
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}
