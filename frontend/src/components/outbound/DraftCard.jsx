import { useState } from 'react';
import {
  CheckCircle, X, Edit2, Building2, User, Star, Tag,
  ChevronDown, ChevronUp, Save, Loader2,
} from 'lucide-react';

const TIER_COLOR = { A: '#22c55e', B: '#eab308', C: '#94a3b8' };
const SCORE_COLOR = s => s >= 70 ? '#22c55e' : s >= 40 ? '#eab308' : '#ef4444';

function Chip({ label, color = 'rgba(167,139,250,0.2)', textColor = 'var(--accent)' }) {
  return (
    <span style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '20px', background: color, color: textColor, border: `1px solid ${textColor}30`, whiteSpace: 'nowrap' }}>
      {label}
    </span>
  );
}

export default function DraftCard({ draft, focused, onApprove, onReject, onEdit }) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editSubject, setEditSubject] = useState(draft.subject);
  const [editBody, setEditBody] = useState(draft.body_text);
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [saving, setSaving] = useState(false);

  async function handleSaveEdit() {
    setSaving(true);
    await onEdit(draft._id, { subject: editSubject, body_text: editBody });
    setSaving(false);
    setEditing(false);
  }

  async function handleRejectConfirm() {
    await onReject(draft._id, rejectReason);
    setRejecting(false);
    setRejectReason('');
  }

  const inputStyle = {
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid var(--glass-border)',
    borderRadius: '8px',
    padding: '8px 11px',
    color: 'var(--text-main)',
    fontSize: '0.86rem',
    width: '100%',
    fontFamily: 'inherit',
    outline: 'none',
  };

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: `1px solid ${focused ? 'rgba(167,139,250,0.6)' : 'var(--glass-border)'}`,
      borderRadius: '14px',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px',
      backdropFilter: 'blur(12px)',
      boxShadow: focused ? '0 0 0 2px rgba(167,139,250,0.25)' : 'none',
      transition: 'border-color 0.2s, box-shadow 0.2s',
    }}>

      {/* Header: company + contact + badges */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Building2 size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>{draft.company_name}</span>
          </div>
          {draft.contact_full_name && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', paddingLeft: '22px' }}>
              <User size={12} style={{ color: 'var(--text-muted)' }} />
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{draft.contact_full_name}</span>
              {draft.contact_email && (
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', opacity: 0.7 }}>· {draft.contact_email}</span>
              )}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
          {draft.tier && (
            <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '3px 10px', borderRadius: '20px', background: `${TIER_COLOR[draft.tier]}20`, color: TIER_COLOR[draft.tier], border: `1px solid ${TIER_COLOR[draft.tier]}50` }}>
              Tier {draft.tier}
            </span>
          )}
          {typeof draft.icp_score === 'number' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Star size={12} style={{ color: SCORE_COLOR(draft.icp_score) }} />
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: SCORE_COLOR(draft.icp_score) }}>{draft.icp_score}</span>
            </div>
          )}
        </div>
      </div>

      {/* Signals */}
      {(draft.signals_detected || []).length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', paddingLeft: '2px' }}>
          {draft.signals_detected.map((s, i) => <Chip key={i} label={s} />)}
        </div>
      )}

      {/* Subject */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Asunto</span>
        {editing ? (
          <input value={editSubject} onChange={e => setEditSubject(e.target.value)} style={inputStyle} />
        ) : (
          <span style={{ fontSize: '0.92rem', fontWeight: 600 }}>{draft.subject}</span>
        )}
      </div>

      {/* Body (collapsible) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <button
          onClick={() => setExpanded(v => !v)}
          style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.75rem', fontFamily: 'inherit', alignSelf: 'flex-start', padding: 0 }}
        >
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          {expanded ? 'Ocultar cuerpo' : 'Ver cuerpo del email'}
        </button>
        {expanded && (
          editing ? (
            <textarea
              value={editBody}
              onChange={e => setEditBody(e.target.value)}
              rows={6}
              style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.6 }}
            />
          ) : (
            <pre style={{ fontSize: '0.84rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap', lineHeight: 1.7, background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', margin: 0, fontFamily: 'inherit' }}>
              {draft.body_text}
            </pre>
          )
        )}
      </div>

      {/* Provider badge */}
      {draft.llm_provider && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Tag size={11} style={{ color: 'var(--text-muted)' }} />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{draft.llm_provider} / {draft.llm_model}</span>
        </div>
      )}

      {/* Reject reason input */}
      {rejecting && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', background: 'rgba(239,68,68,0.08)', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.25)' }}>
          <span style={{ fontSize: '0.8rem', color: '#fca5a5' }}>Motivo del rechazo (opcional)</span>
          <input
            autoFocus
            value={rejectReason}
            onChange={e => setRejectReason(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleRejectConfirm(); if (e.key === 'Escape') setRejecting(false); }}
            placeholder="Email muy genérico, no personalizado..."
            style={{ ...inputStyle, borderColor: 'rgba(239,68,68,0.4)' }}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={handleRejectConfirm} style={{ flex: 1, padding: '8px', background: 'rgba(239,68,68,0.25)', border: '1px solid rgba(239,68,68,0.4)', borderRadius: '8px', color: '#fca5a5', cursor: 'pointer', fontSize: '0.82rem', fontFamily: 'inherit' }}>
              Confirmar rechazo
            </button>
            <button onClick={() => setRejecting(false)} style={{ padding: '8px 14px', background: 'none', border: '1px solid var(--glass-border)', borderRadius: '8px', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.82rem', fontFamily: 'inherit' }}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Action buttons */}
      {!rejecting && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {editing ? (
            <>
              <button
                onClick={handleSaveEdit}
                disabled={saving}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, justifyContent: 'center', padding: '9px', background: 'rgba(59,130,246,0.25)', border: '1px solid rgba(59,130,246,0.4)', borderRadius: '9px', color: '#93c5fd', cursor: 'pointer', fontSize: '0.84rem', fontFamily: 'inherit', fontWeight: 600 }}
              >
                {saving ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
                Guardar
              </button>
              <button onClick={() => { setEditing(false); setEditSubject(draft.subject); setEditBody(draft.body_text); }} style={{ padding: '9px 14px', background: 'none', border: '1px solid var(--glass-border)', borderRadius: '9px', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.84rem', fontFamily: 'inherit' }}>
                Cancelar
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => onApprove(draft._id)}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, justifyContent: 'center', padding: '9px', background: 'rgba(34,197,94,0.2)', border: '1px solid rgba(34,197,94,0.4)', borderRadius: '9px', color: '#86efac', cursor: 'pointer', fontSize: '0.84rem', fontFamily: 'inherit', fontWeight: 600 }}
              >
                <CheckCircle size={14} /> Aprobar <kbd style={{ fontSize: '0.68rem', opacity: 0.6, background: 'rgba(255,255,255,0.1)', padding: '1px 5px', borderRadius: '4px' }}>A</kbd>
              </button>
              <button
                onClick={() => { setEditing(true); setExpanded(true); }}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 14px', background: 'rgba(59,130,246,0.2)', border: '1px solid rgba(59,130,246,0.35)', borderRadius: '9px', color: '#93c5fd', cursor: 'pointer', fontSize: '0.84rem', fontFamily: 'inherit', fontWeight: 600 }}
              >
                <Edit2 size={14} /> Editar <kbd style={{ fontSize: '0.68rem', opacity: 0.6, background: 'rgba(255,255,255,0.1)', padding: '1px 5px', borderRadius: '4px' }}>E</kbd>
              </button>
              <button
                onClick={() => setRejecting(true)}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 14px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.35)', borderRadius: '9px', color: '#fca5a5', cursor: 'pointer', fontSize: '0.84rem', fontFamily: 'inherit', fontWeight: 600 }}
              >
                <X size={14} /> Rechazar <kbd style={{ fontSize: '0.68rem', opacity: 0.6, background: 'rgba(255,255,255,0.1)', padding: '1px 5px', borderRadius: '4px' }}>R</kbd>
              </button>
            </>
          )}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
