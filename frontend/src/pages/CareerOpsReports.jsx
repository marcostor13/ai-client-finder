import { useState, useEffect, useCallback } from 'react';
import api from '../api';

const GRADE_COLOR = { A: '#22c55e', B: '#84cc16', C: '#eab308', D: '#f97316', F: '#ef4444' };
const REC_COLOR   = { apply: '#22c55e', maybe: '#eab308', skip: '#ef4444' };

const STATUS_LABELS = {
  evaluated: { label: 'Evaluado',   color: '#a78bfa', bg: 'rgba(167,139,250,0.12)' },
  applied:   { label: 'Aplicado',   color: '#60a5fa', bg: 'rgba(96,165,250,0.12)'  },
  responded: { label: 'Respondió',  color: '#34d399', bg: 'rgba(52,211,153,0.12)'  },
  interview: { label: 'Entrevista', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)'  },
  offer:     { label: 'Oferta',     color: '#22c55e', bg: 'rgba(34,197,94,0.12)'   },
  rejected:  { label: 'Rechazado',  color: '#ef4444', bg: 'rgba(239,68,68,0.12)'   },
  discarded: { label: 'Descartado', color: '#6b7280', bg: 'rgba(107,114,128,0.12)' },
};
const STATUS_OPTIONS = Object.entries(STATUS_LABELS).map(([v, { label }]) => ({ value: v, label }));

/* ── Checkbox ────────────────────────────────────────────────────────────────── */
function Checkbox({ checked, indeterminate, onChange, onClick }) {
  return (
    <div
      onClick={e => { e.stopPropagation(); onClick?.(); onChange?.(!checked); }}
      style={{
        width: '18px', height: '18px', borderRadius: '5px', flexShrink: 0,
        border: `2px solid ${checked || indeterminate ? '#7C3AED' : 'rgba(255,255,255,0.2)'}`,
        background: checked ? '#7C3AED' : indeterminate ? 'rgba(124,58,237,0.4)' : 'transparent',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', transition: 'all 0.15s',
      }}
    >
      {checked && <span style={{ color: '#fff', fontSize: '11px', lineHeight: 1, fontWeight: 900 }}>✓</span>}
      {!checked && indeterminate && <span style={{ color: '#c4b5fd', fontSize: '11px', lineHeight: 1, fontWeight: 900 }}>−</span>}
    </div>
  );
}

/* ── Stat card ───────────────────────────────────────────────────────────────── */
function StatCard({ value, label, color = '#a78bfa', sub }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '20px 24px' }}>
      <p style={{ margin: 0, fontSize: '2rem', fontWeight: 900, color }}>{value}</p>
      <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)', fontWeight: 600 }}>{label}</p>
      {sub && <p style={{ margin: '4px 0 0', fontSize: '0.72rem', color: 'rgba(255,255,255,0.25)' }}>{sub}</p>}
    </div>
  );
}

function GradeBar({ grade, count, total }) {
  if (!count) return null;
  const pct = total ? Math.round((count / total) * 100) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
      <span style={{ width: '22px', fontWeight: 900, color: GRADE_COLOR[grade], fontSize: '0.88rem' }}>{grade}</span>
      <div style={{ flex: 1, height: '8px', background: 'rgba(255,255,255,0.07)', borderRadius: '99px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: GRADE_COLOR[grade], borderRadius: '99px', transition: 'width 0.5s ease' }} />
      </div>
      <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', minWidth: '42px', textAlign: 'right' }}>{count} ({pct}%)</span>
    </div>
  );
}

/* ── Cover letter modal ──────────────────────────────────────────────────────── */
function CoverLetterModal({ coverLetter, jobTitle, jobUrl, onClose }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(coverLetter).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  };
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 999, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: 'linear-gradient(180deg,#0f0a20,#0a0818)', border: '1px solid rgba(167,139,250,0.25)', borderRadius: '20px', padding: '28px', width: '100%', maxWidth: '640px', boxShadow: '0 24px 64px rgba(0,0,0,0.6)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '18px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: '#c4b5fd' }}>Cover Letter generada</h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: 'rgba(255,255,255,0.35)' }}>{jobTitle}</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', fontSize: '1.2rem', lineHeight: 1 }}>✕</button>
        </div>
        <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '12px', padding: '16px', marginBottom: '16px', maxHeight: '320px', overflowY: 'auto', fontSize: '0.83rem', color: 'rgba(255,255,255,0.75)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
          {coverLetter}
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={copy} style={{ flex: 1, padding: '10px', borderRadius: '10px', cursor: 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', background: copied ? 'rgba(34,197,94,0.2)' : 'rgba(109,40,217,0.3)', border: `1px solid ${copied ? 'rgba(34,197,94,0.4)' : 'rgba(109,40,217,0.5)'}`, color: copied ? '#86efac' : '#c4b5fd' }}>
            {copied ? '✓ Copiado' : 'Copiar texto'}
          </button>
          {jobUrl && (
            <a href={jobUrl} target="_blank" rel="noreferrer" style={{ flex: 1, padding: '10px', borderRadius: '10px', background: 'rgba(96,165,250,0.15)', border: '1px solid rgba(96,165,250,0.3)', color: '#93c5fd', fontWeight: 700, fontSize: '0.85rem', textDecoration: 'none', textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              Abrir oferta →
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────────── */
export default function CareerOpsReports() {
  const [stats, setStats]     = useState(null);
  const [evals, setEvals]     = useState([]);
  const [total, setTotal]     = useState(0);
  const [page, setPage]       = useState(1);
  const [filter, setFilter]   = useState('');
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating]   = useState(null);
  const [expanded, setExpanded]   = useState(null);
  const [applying, setApplying]   = useState(null);
  const [modal, setModal]         = useState(null);
  const [selected, setSelected]   = useState(new Set());   // Set of _id strings
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const loadStats = useCallback(async () => {
    try { const { data } = await api.get('/career-ops/stats'); setStats(data.stats); } catch {}
  }, []);

  const loadEvals = useCallback(async (p = 1, st = '') => {
    setLoading(true);
    setSelected(new Set());
    try {
      const params = { page: p, limit: 15 };
      if (st) params.status = st;
      const { data } = await api.get('/career-ops/evaluations', { params });
      setEvals(data.evaluations || []);
      setTotal(data.total || 0);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadStats(); loadEvals(1, filter); }, [loadStats, loadEvals, filter]);

  /* ── Selection helpers ──────────────────────────────────────────────────────── */
  const allIds       = evals.map(e => e._id);
  const allSelected  = allIds.length > 0 && allIds.every(id => selected.has(id));
  const someSelected = allIds.some(id => selected.has(id));

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(allIds));
    }
  };

  const toggleOne = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  /* ── Actions ────────────────────────────────────────────────────────────────── */
  const handleStatus = async (id, status) => {
    setUpdating(id);
    try {
      await api.patch(`/career-ops/evaluations/${id}/status`, { status });
      setEvals(ev => ev.map(e => e._id === id ? { ...e, status } : e));
      loadStats();
    } catch {}
    setUpdating(null);
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar esta evaluación?')) return;
    try {
      await api.delete(`/career-ops/evaluations/${id}`);
      setEvals(ev => ev.filter(e => e._id !== id));
      setTotal(t => t - 1);
      setSelected(prev => { const next = new Set(prev); next.delete(id); return next; });
      loadStats();
    } catch {}
  };

  const handleBulkDelete = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    if (!confirm(`¿Eliminar ${ids.length} evaluación${ids.length > 1 ? 'es' : ''}?`)) return;
    setBulkDeleting(true);
    try {
      const { data } = await api.post('/career-ops/evaluations/bulk-delete', { ids });
      setEvals(ev => ev.filter(e => !selected.has(e._id)));
      setTotal(t => t - (data.deleted || ids.length));
      setSelected(new Set());
      loadStats();
    } catch {}
    setBulkDeleting(false);
  };

  const handleAutoApply = async (ev) => {
    setApplying(ev._id);
    try {
      const { data } = await api.post(`/career-ops/evaluations/${ev._id}/auto-apply`);
      const result = data.result;
      setModal({ coverLetter: result.cover_letter, jobTitle: ev.job_title, jobUrl: ev.job_url });
      if (result.applied) {
        setEvals(list => list.map(e => e._id === ev._id ? { ...e, status: 'applied' } : e));
        loadStats();
      }
    } catch { alert('Error al generar la aplicación. Intenta nuevamente.'); }
    setApplying(null);
  };

  const totalPages = Math.ceil(total / 15);
  const grades = ['A', 'B', 'C', 'D', 'F'];
  const COLS = 9; // checkbox + 7 data cols + delete

  return (
    <div style={{ padding: '32px', maxWidth: '1100px', margin: '0 auto' }}>
      {modal && <CoverLetterModal coverLetter={modal.coverLetter} jobTitle={modal.jobTitle} jobUrl={modal.jobUrl} onClose={() => setModal(null)} />}

      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(90deg,#a78bfa,#c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Career Ops — Reportes
        </h1>
        <p style={{ margin: '8px 0 0', color: 'rgba(255,255,255,0.4)', fontSize: '0.88rem' }}>
          Seguimiento de todas las evaluaciones y tu pipeline de aplicaciones.
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
            <StatCard value={stats.total} label="Total evaluadas" />
            <StatCard value={stats.avg_score?.toFixed(1) || '—'} label="Score promedio" color={stats.avg_score >= 4 ? '#22c55e' : stats.avg_score >= 3 ? '#eab308' : '#ef4444'} sub="sobre 5.0" />
            <StatCard value={stats.high_score_count} label="Score ≥ 4.0" color="#22c55e" sub="Recomendadas para aplicar" />
            <StatCard value={(stats.by_status?.interview || 0) + (stats.by_status?.offer || 0)} label="En proceso activo" color="#f59e0b" sub="Entrevistas + Ofertas" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px', marginBottom: '28px' }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '20px 24px' }}>
              <p style={{ margin: '0 0 16px', fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Distribución de grados</p>
              {grades.map(g => <GradeBar key={g} grade={g} count={stats.grades?.[g] || 0} total={stats.total} />)}
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '20px 24px' }}>
              <p style={{ margin: '0 0 16px', fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Pipeline de aplicaciones</p>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                {STATUS_OPTIONS.map(({ value, label }) => {
                  const count = stats.by_status?.[value] || 0;
                  const s = STATUS_LABELS[value];
                  return (
                    <div key={value} style={{ padding: '12px 16px', borderRadius: '12px', background: count > 0 ? s.bg : 'rgba(255,255,255,0.02)', border: `1px solid ${count > 0 ? s.color + '33' : 'rgba(255,255,255,0.06)'}`, minWidth: '90px', textAlign: 'center' }}>
                      <p style={{ margin: 0, fontSize: '1.4rem', fontWeight: 900, color: count > 0 ? s.color : 'rgba(255,255,255,0.18)' }}>{count}</p>
                      <p style={{ margin: '2px 0 0', fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)', fontWeight: 600 }}>{label}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'rgba(255,255,255,0.35)', fontWeight: 600 }}>Estado:</p>
        {[{ value: '', label: 'Todos' }, ...STATUS_OPTIONS].map(({ value, label }) => (
          <button key={value} onClick={() => { setFilter(value); setPage(1); }} style={{
            padding: '5px 12px', borderRadius: '99px', border: 'none',
            fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
            background: filter === value ? 'rgba(109,40,217,0.4)' : 'rgba(255,255,255,0.05)',
            color: filter === value ? '#c4b5fd' : 'rgba(255,255,255,0.35)',
            transition: 'all 0.15s',
          }}>{label}</button>
        ))}
      </div>

      {/* Table */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
              {/* Select-all checkbox */}
              <th style={{ padding: '12px 8px 12px 16px', width: '40px' }}>
                <Checkbox
                  checked={allSelected}
                  indeterminate={someSelected && !allSelected}
                  onChange={toggleAll}
                  onClick={toggleAll}
                />
              </th>
              {['Puesto / Empresa', 'Score', 'Grado', 'Recomendación', 'Estado', 'Fecha', '', ''].map(h => (
                <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, color: 'rgba(255,255,255,0.25)', textTransform: 'uppercase', letterSpacing: '0.07em', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={COLS} style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.25)', fontSize: '0.88rem' }}>Cargando…</td></tr>
            ) : evals.length === 0 ? (
              <tr><td colSpan={COLS} style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.25)', fontSize: '0.88rem' }}>Sin evaluaciones aún. Corre un scan o evalúa una oferta manualmente.</td></tr>
            ) : evals.map(ev => {
              const grade  = ev.evaluation?.grade;
              const score  = ev.evaluation?.overall_score;
              const rec    = ev.evaluation?.recommendation;
              const isExp  = expanded === ev._id;
              const isSel  = selected.has(ev._id);

              return (
                <>
                  <tr
                    key={ev._id}
                    onClick={() => setExpanded(isExp ? null : ev._id)}
                    style={{
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                      cursor: 'pointer',
                      transition: 'background 0.12s',
                      background: isSel
                        ? 'rgba(109,40,217,0.12)'
                        : isExp ? 'rgba(109,40,217,0.07)' : 'transparent',
                    }}
                    onMouseEnter={e => { if (!isExp && !isSel) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                    onMouseLeave={e => { if (!isExp && !isSel) e.currentTarget.style.background = 'transparent'; }}
                  >
                    {/* Checkbox cell */}
                    <td style={{ padding: '14px 8px 14px 16px' }} onClick={e => e.stopPropagation()}>
                      <Checkbox checked={isSel} onChange={() => toggleOne(ev._id)} onClick={() => toggleOne(ev._id)} />
                    </td>

                    <td style={{ padding: '14px 16px' }}>
                      <p style={{ margin: 0, fontWeight: 700, fontSize: '0.88rem', color: '#e9d5ff' }}>{ev.job_title || 'Sin título'}</p>
                      <p style={{ margin: '2px 0 0', fontSize: '0.75rem', color: 'rgba(255,255,255,0.35)' }}>{ev.company_name || '—'}</p>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontWeight: 800, fontSize: '1rem', color: GRADE_COLOR[grade] || '#9ca3af' }}>{score?.toFixed(1) || '—'}</span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ width: '30px', height: '30px', borderRadius: '8px', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', background: `${GRADE_COLOR[grade] || '#9ca3af'}22`, border: `1px solid ${GRADE_COLOR[grade] || '#9ca3af'}44`, fontWeight: 900, fontSize: '0.9rem', color: GRADE_COLOR[grade] || '#9ca3af' }}>
                        {grade || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: REC_COLOR[rec] || '#9ca3af' }}>
                        {{ apply: 'Aplicar', maybe: 'Considerar', skip: 'Descartar' }[rec] || rec || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }} onClick={e => e.stopPropagation()}>
                      <select
                        value={ev.status}
                        onChange={e => handleStatus(ev._id, e.target.value)}
                        disabled={updating === ev._id}
                        style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#e9d5ff', borderRadius: '8px', padding: '5px 10px', fontSize: '0.78rem', cursor: 'pointer', outline: 'none' }}
                      >
                        {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: '0.75rem', color: 'rgba(255,255,255,0.3)', whiteSpace: 'nowrap' }}>
                      {ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleDateString('es', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}
                    </td>
                    <td style={{ padding: '14px 16px' }} onClick={e => e.stopPropagation()}>
                      <button
                        onClick={() => handleAutoApply(ev)}
                        disabled={applying === ev._id || ev.status === 'applied'}
                        title={ev.status === 'applied' ? 'Ya aplicado' : 'Auto-aplicar con IA'}
                        style={{
                          padding: '6px 12px', borderRadius: '8px', cursor: applying === ev._id || ev.status === 'applied' ? 'not-allowed' : 'pointer',
                          background: ev.status === 'applied' ? 'rgba(34,197,94,0.15)' : 'rgba(109,40,217,0.25)',
                          border: `1px solid ${ev.status === 'applied' ? 'rgba(34,197,94,0.3)' : 'rgba(109,40,217,0.4)'}`,
                          color: ev.status === 'applied' ? '#86efac' : '#c4b5fd',
                          fontSize: '0.75rem', fontWeight: 700, whiteSpace: 'nowrap',
                          opacity: applying === ev._id ? 0.6 : 1, transition: 'all 0.15s',
                        }}
                      >
                        {applying === ev._id ? '⏳ Generando…' : ev.status === 'applied' ? '✓ Aplicado' : '⚡ Auto-aplicar'}
                      </button>
                    </td>
                    {/* Individual delete */}
                    <td style={{ padding: '14px 12px' }} onClick={e => e.stopPropagation()}>
                      <button
                        onClick={() => handleDelete(ev._id)}
                        title="Eliminar"
                        style={{ background: 'none', border: '1px solid transparent', borderRadius: '7px', cursor: 'pointer', color: 'rgba(255,255,255,0.2)', fontSize: '0.9rem', padding: '5px 8px', lineHeight: 1, transition: 'all 0.15s' }}
                        onMouseEnter={e => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.3)'; e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)'; e.currentTarget.style.borderColor = 'transparent'; e.currentTarget.style.background = 'none'; }}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>

                  {/* Expanded detail row */}
                  {isExp && ev.evaluation && (
                    <tr key={`${ev._id}-exp`} style={{ background: isSel ? 'rgba(109,40,217,0.08)' : 'rgba(109,40,217,0.05)' }}>
                      <td colSpan={COLS} style={{ padding: '0 16px 20px 56px' }}>
                        <p style={{ margin: '12px 0 8px', fontSize: '0.82rem', color: 'rgba(255,255,255,0.5)', lineHeight: 1.6, background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '12px 16px' }}>
                          {ev.evaluation.summary}
                        </p>
                        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                          {ev.evaluation.strengths?.slice(0, 3).map((s, i) => (
                            <span key={i} style={{ fontSize: '0.75rem', color: '#86efac', background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.15)', borderRadius: '6px', padding: '3px 10px' }}>✓ {s}</span>
                          ))}
                          {ev.evaluation.red_flags?.slice(0, 2).map((s, i) => (
                            <span key={i} style={{ fontSize: '0.75rem', color: '#fca5a5', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: '6px', padding: '3px 10px' }}>⚠ {s}</span>
                          ))}
                          {ev.cover_letter && (
                            <button
                              onClick={e => { e.stopPropagation(); setModal({ coverLetter: ev.cover_letter, jobTitle: ev.job_title, jobUrl: ev.job_url }); }}
                              style={{ marginLeft: 'auto', padding: '4px 12px', borderRadius: '8px', border: '1px solid rgba(167,139,250,0.3)', background: 'rgba(167,139,250,0.1)', color: '#c4b5fd', fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer' }}
                            >
                              Ver cover letter
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '20px' }}>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
            <button key={p} onClick={() => { setPage(p); loadEvals(p, filter); }} style={{
              width: '36px', height: '36px', borderRadius: '8px', border: 'none', cursor: 'pointer',
              background: page === p ? 'rgba(109,40,217,0.5)' : 'rgba(255,255,255,0.06)',
              color: page === p ? '#c4b5fd' : 'rgba(255,255,255,0.35)', fontWeight: 700, fontSize: '0.85rem',
            }}>{p}</button>
          ))}
        </div>
      )}

      {/* ── Bulk action bar (floats at bottom when items selected) ─────────────── */}
      <div style={{
        position: 'fixed', bottom: '28px', left: '50%', transform: `translateX(-50%) translateY(${selected.size > 0 ? '0' : '120px'})`,
        transition: 'transform 0.3s cubic-bezier(0.4,0,0.2,1)',
        zIndex: 100,
        display: 'flex', alignItems: 'center', gap: '16px',
        background: 'linear-gradient(135deg,rgba(15,10,32,0.97),rgba(10,8,24,0.97))',
        border: '1px solid rgba(167,139,250,0.3)',
        borderRadius: '16px', padding: '14px 20px',
        boxShadow: '0 16px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(109,40,217,0.2)',
        backdropFilter: 'blur(16px)',
        minWidth: '320px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ width: '28px', height: '28px', borderRadius: '8px', background: 'rgba(109,40,217,0.4)', border: '1px solid rgba(109,40,217,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, fontSize: '0.82rem', color: '#c4b5fd' }}>
            {selected.size}
          </span>
          <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', fontWeight: 600 }}>
            seleccionada{selected.size !== 1 ? 's' : ''}
          </span>
        </div>

        <button
          onClick={() => setSelected(new Set())}
          style={{ padding: '7px 14px', borderRadius: '9px', border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)', fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s' }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
        >
          Deseleccionar
        </button>

        <button
          onClick={handleBulkDelete}
          disabled={bulkDeleting}
          style={{
            padding: '7px 18px', borderRadius: '9px', fontWeight: 800, fontSize: '0.82rem', cursor: bulkDeleting ? 'not-allowed' : 'pointer',
            background: bulkDeleting ? 'rgba(239,68,68,0.1)' : 'rgba(239,68,68,0.2)',
            border: '1px solid rgba(239,68,68,0.4)', color: '#fca5a5',
            transition: 'all 0.15s', opacity: bulkDeleting ? 0.6 : 1,
          }}
          onMouseEnter={e => { if (!bulkDeleting) e.currentTarget.style.background = 'rgba(239,68,68,0.35)'; }}
          onMouseLeave={e => { if (!bulkDeleting) e.currentTarget.style.background = 'rgba(239,68,68,0.2)'; }}
        >
          {bulkDeleting ? 'Eliminando…' : `🗑 Eliminar ${selected.size}`}
        </button>
      </div>
    </div>
  );
}
