import { useState, useEffect, useCallback, useRef } from 'react';
import { Inbox, CheckCircle, RefreshCw, Loader2, AlertCircle, Zap, CheckCheck } from 'lucide-react';
import api from '../api';
import DraftCard from '../components/outbound/DraftCard';

export default function ApprovalQueue() {
  const [drafts, setDrafts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [focusedIdx, setFocusedIdx] = useState(0);
  const [toast, setToast] = useState(null); // { msg, type }
  const [approvingAll, setApprovingAll] = useState(false);
  const containerRef = useRef(null);

  function showToast(msg, type = 'success') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2500);
  }

  async function fetchDrafts() {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/outbound/approvals?status=pending_approval&limit=50');
      setDrafts(res.data.drafts);
      setTotal(res.data.total);
      setFocusedIdx(0);
    } catch {
      setError('No se pudo cargar la cola. ¿El backend está corriendo?');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchDrafts(); }, []);

  // Remove a draft from local state and adjust focus
  function removeDraft(draftId) {
    setDrafts(prev => {
      const idx = prev.findIndex(d => d._id === draftId);
      const next = prev.filter(d => d._id !== draftId);
      setFocusedIdx(i => Math.min(i, Math.max(0, next.length - 1)));
      return next;
    });
    setTotal(t => t - 1);
  }

  async function handleApprove(draftId) {
    try {
      await api.post(`/api/outbound/approvals/${draftId}/approve`);
      removeDraft(draftId);
      showToast('Email aprobado');
    } catch {
      showToast('Error al aprobar', 'error');
    }
  }

  async function handleReject(draftId, reason) {
    try {
      await api.post(`/api/outbound/approvals/${draftId}/reject`, { reason });
      removeDraft(draftId);
      showToast('Email rechazado');
    } catch {
      showToast('Error al rechazar', 'error');
    }
  }

  async function handleApproveAll() {
    if (!drafts.length) return;
    setApprovingAll(true);
    try {
      const res = await api.post('/api/outbound/approvals/approve-all');
      const count = res.data.approved ?? drafts.length;
      setDrafts([]);
      setTotal(0);
      showToast(`${count} email${count !== 1 ? 's' : ''} aprobado${count !== 1 ? 's' : ''}`);
    } catch {
      showToast('Error al aprobar todos', 'error');
    } finally {
      setApprovingAll(false);
    }
  }

  async function handleEdit(draftId, updates) {
    try {
      const res = await api.patch(`/api/outbound/approvals/${draftId}`, updates);
      setDrafts(prev => prev.map(d => d._id === draftId ? res.data.draft : d));
      showToast('Email editado');
    } catch {
      showToast('Error al guardar edición', 'error');
    }
  }

  // Keyboard shortcuts (A approve, R reject, E edit — act on focused card)
  const handleKey = useCallback((e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (!drafts.length) return;

    const focused = drafts[focusedIdx];
    if (!focused) return;

    if (e.key === 'ArrowDown' || e.key === 'j') {
      e.preventDefault();
      setFocusedIdx(i => Math.min(i + 1, drafts.length - 1));
    } else if (e.key === 'ArrowUp' || e.key === 'k') {
      e.preventDefault();
      setFocusedIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'a' || e.key === 'A') {
      handleApprove(focused._id);
    } else if (e.key === 'r' || e.key === 'R') {
      // Trigger reject flow on the card — we do it via a ref-based approach:
      // easiest: just call reject without reason from keyboard
      handleReject(focused._id, '');
    }
  }, [drafts, focusedIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  // Scroll focused card into view
  useEffect(() => {
    const card = containerRef.current?.children[focusedIdx];
    card?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [focusedIdx]);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-deep)' }}>
    <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px 20px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(109,40,217,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Inbox size={20} style={{ color: 'var(--accent)' }} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 800 }}>Cola de aprobación</h1>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              {loading ? 'Cargando…' : `${total} email${total !== 1 ? 's' : ''} pendiente${total !== 1 ? 's' : ''}`}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {drafts.length > 0 && (
            <button
              onClick={handleApproveAll}
              disabled={approvingAll}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                background: 'linear-gradient(135deg, rgba(34,197,94,0.3), rgba(16,185,129,0.2))',
                border: '1px solid rgba(34,197,94,0.5)',
                borderRadius: '10px', padding: '9px 18px',
                color: '#86efac', cursor: approvingAll ? 'wait' : 'pointer',
                fontSize: '0.84rem', fontFamily: 'inherit', fontWeight: 700,
                boxShadow: '0 0 12px rgba(34,197,94,0.15)',
              }}
            >
              {approvingAll
                ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                : <CheckCheck size={14} />}
              Aprobar todo ({drafts.length})
            </button>
          )}
          <button
            onClick={fetchDrafts}
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '7px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--glass-border)', borderRadius: '10px', padding: '9px 16px', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.84rem', fontFamily: 'inherit' }}
          >
            {loading ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <RefreshCw size={14} />}
            Actualizar
          </button>
        </div>
      </div>

      {/* Keyboard hint */}
      {drafts.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(109,40,217,0.1)', border: '1px solid rgba(167,139,250,0.2)', borderRadius: '10px', padding: '10px 14px' }}>
          <Zap size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Teclas rápidas: <b style={{ color: 'var(--accent)' }}>A</b> aprobar · <b style={{ color: 'var(--accent)' }}>R</b> rechazar · <b style={{ color: 'var(--accent)' }}>↑↓</b> navegar
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '10px', padding: '12px 16px', color: '#fca5a5', fontSize: '0.85rem' }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && drafts.length === 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', padding: '60px 20px', color: 'var(--text-muted)', textAlign: 'center' }}>
          <CheckCircle size={40} style={{ color: 'rgba(34,197,94,0.4)' }} />
          <p style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-main)' }}>Todo al día</p>
          <p style={{ fontSize: '0.85rem' }}>No hay emails pendientes de aprobar. El Job B generará nuevos drafts mañana a las 9am.</p>
        </div>
      )}

      {/* Draft cards */}
      {!loading && (
        <div ref={containerRef} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {drafts.map((draft, idx) => (
            <DraftCard
              key={draft._id}
              draft={draft}
              focused={idx === focusedIdx}
              onApprove={handleApprove}
              onReject={handleReject}
              onEdit={handleEdit}
            />
          ))}
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '24px',
          background: toast.type === 'error' ? 'rgba(239,68,68,0.9)' : 'rgba(34,197,94,0.9)',
          color: '#fff', borderRadius: '10px', padding: '12px 20px',
          fontSize: '0.88rem', fontWeight: 600, boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
          animation: 'fadeIn 0.2s ease',
        }}>
          {toast.msg}
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
    </div>
  );
}
