import { useState, useEffect, useCallback, useRef } from 'react';
import api from '../api';

const GRADE_COLOR  = { A: '#22c55e', B: '#84cc16', C: '#eab308', D: '#f97316', F: '#ef4444' };
const GRADE_BG     = { A: 'rgba(34,197,94,0.12)', B: 'rgba(132,204,22,0.12)', C: 'rgba(234,179,8,0.12)', D: 'rgba(249,115,22,0.12)', F: 'rgba(239,68,68,0.12)' };
const REC_COLOR    = { apply: '#22c55e', maybe: '#eab308', skip: '#ef4444' };
const REC_BG       = { apply: 'rgba(34,197,94,0.12)', maybe: 'rgba(234,179,8,0.12)', skip: 'rgba(239,68,68,0.12)' };
const REC_LABEL    = { apply: 'Aplicar', maybe: 'Considerar', skip: 'Descartar' };

const STATUS_LABELS = {
  evaluated: { label: 'Evaluado',   color: '#a78bfa' },
  applied:   { label: 'Aplicado',   color: '#60a5fa' },
  responded: { label: 'Respondió',  color: '#34d399' },
  interview: { label: 'Entrevista', color: '#f59e0b' },
  offer:     { label: 'Oferta',     color: '#22c55e' },
  rejected:  { label: 'Rechazado',  color: '#ef4444' },
  discarded: { label: 'Descartado', color: '#6b7280' },
};

const SORT_OPTIONS = [
  { value: 'score_desc', label: 'Mayor score' },
  { value: 'score_asc',  label: 'Menor score' },
  { value: 'date_desc',  label: 'Más recientes' },
  { value: 'date_asc',   label: 'Más antiguos'  },
];

/* ── Cover Letter Modal ─────────────────────────────────────────────────────── */
function CoverLetterModal({ coverLetter, jobTitle, jobUrl, onClose }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(coverLetter).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 999, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}
    >
      <div onClick={e => e.stopPropagation()} style={{ background: 'linear-gradient(180deg,#0f0a20,#0a0818)', border: '1px solid rgba(167,139,250,0.25)', borderRadius: '20px', padding: '28px', width: '100%', maxWidth: '640px', boxShadow: '0 24px 64px rgba(0,0,0,0.7)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '18px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: '#c4b5fd' }}>Cover Letter generada con IA</h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: 'rgba(255,255,255,0.35)' }}>{jobTitle}</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', fontSize: '1.3rem', lineHeight: 1 }}>✕</button>
        </div>
        <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '12px', padding: '16px', marginBottom: '16px', maxHeight: '340px', overflowY: 'auto', fontSize: '0.83rem', color: 'rgba(255,255,255,0.78)', lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
          {coverLetter}
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={copy} style={{ flex: 1, padding: '10px', borderRadius: '10px', cursor: 'pointer', fontWeight: 700, fontSize: '0.85rem', transition: 'all 0.2s', background: copied ? 'rgba(34,197,94,0.2)' : 'rgba(109,40,217,0.3)', border: `1px solid ${copied ? 'rgba(34,197,94,0.4)' : 'rgba(109,40,217,0.5)'}`, color: copied ? '#86efac' : '#c4b5fd' }}>
            {copied ? '✓ Copiado' : 'Copiar texto'}
          </button>
          {jobUrl && (
            <a href={jobUrl} target="_blank" rel="noreferrer" style={{ flex: 1, padding: '10px', borderRadius: '10px', background: 'rgba(96,165,250,0.15)', border: '1px solid rgba(96,165,250,0.3)', color: '#93c5fd', fontWeight: 700, fontSize: '0.85rem', textDecoration: 'none', textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              Abrir oferta →
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Score Ring ─────────────────────────────────────────────────────────────── */
function ScoreRing({ score, grade }) {
  const color = GRADE_COLOR[grade] || '#9ca3af';
  const pct   = ((score || 0) / 5) * 100;
  const r = 28, circ = 2 * Math.PI * r;
  return (
    <div style={{ position: 'relative', width: 72, height: 72, flexShrink: 0 }}>
      <svg width={72} height={72} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={36} cy={36} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={5} />
        <circle cx={36} cy={36} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${(pct / 100) * circ} ${circ}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.6s ease', filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0px' }}>
        <span style={{ fontSize: '1.05rem', fontWeight: 900, color, lineHeight: 1 }}>{score?.toFixed(1) ?? '—'}</span>
        <span style={{ fontSize: '0.68rem', fontWeight: 800, color: 'rgba(255,255,255,0.35)' }}>{grade ?? '—'}</span>
      </div>
    </div>
  );
}

/* ── Job Card ───────────────────────────────────────────────────────────────── */
function JobCard({ ev, onAutoApply, applying, onShowCoverLetter, onDelete, selected, onToggleSelect }) {
  const [expanded, setExpanded] = useState(false);
  const grade     = ev.evaluation?.grade;
  const score     = ev.evaluation?.overall_score;
  const rec       = ev.evaluation?.recommendation;
  const st        = STATUS_LABELS[ev.status] || { label: ev.status, color: '#9ca3af' };
  const isApplied = ev.status === 'applied';
  const isSel     = selected;

  return (
    <div style={{
      background: isSel ? 'rgba(109,40,217,0.1)' : 'rgba(255,255,255,0.03)',
      border: `1px solid ${isSel ? 'rgba(109,40,217,0.5)' : grade ? GRADE_COLOR[grade] + '22' : 'rgba(255,255,255,0.08)'}`,
      borderRadius: '18px',
      overflow: 'hidden',
      transition: 'box-shadow 0.2s, transform 0.2s, border-color 0.15s, background 0.15s',
      display: 'flex', flexDirection: 'column',
      position: 'relative',
    }}
      onMouseEnter={e => { if (!isSel) { e.currentTarget.style.boxShadow = `0 8px 32px ${grade ? GRADE_COLOR[grade] + '18' : 'rgba(0,0,0,0.3)'}`; e.currentTarget.style.transform = 'translateY(-2px)'; } }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'none'; }}
    >
      {/* Checkbox top-right */}
      <div
        onClick={e => { e.stopPropagation(); onToggleSelect(); }}
        style={{
          position: 'absolute', top: '12px', right: '12px', zIndex: 2,
          width: '20px', height: '20px', borderRadius: '6px',
          border: `2px solid ${isSel ? '#7C3AED' : 'rgba(255,255,255,0.18)'}`,
          background: isSel ? '#7C3AED' : 'rgba(0,0,0,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', transition: 'all 0.15s',
          backdropFilter: 'blur(4px)',
        }}
      >
        {isSel && <span style={{ color: '#fff', fontSize: '12px', fontWeight: 900, lineHeight: 1 }}>✓</span>}
      </div>
      {/* Card header */}
      <div style={{ padding: '18px 18px 14px', display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
        <ScoreRing score={score} grade={grade} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
            {rec && (
              <span style={{ padding: '2px 8px', borderRadius: '99px', fontSize: '0.68rem', fontWeight: 700, background: REC_BG[rec], color: REC_COLOR[rec], border: `1px solid ${REC_COLOR[rec]}33` }}>
                {REC_LABEL[rec]}
              </span>
            )}
            <span style={{ padding: '2px 8px', borderRadius: '99px', fontSize: '0.68rem', fontWeight: 700, color: st.color, background: `${st.color}18`, border: `1px solid ${st.color}33` }}>
              {st.label}
            </span>
          </div>
          <p style={{ margin: 0, fontWeight: 800, fontSize: '0.9rem', color: '#e9d5ff', lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
            {ev.job_title || 'Sin título'}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', fontWeight: 600 }}>
            {ev.company_name || '—'}
          </p>
        </div>
      </div>

      {/* Summary */}
      {ev.evaluation?.summary && (
        <div style={{ padding: '0 18px', marginBottom: '12px' }}>
          <p style={{ margin: 0, fontSize: '0.78rem', color: 'rgba(255,255,255,0.45)', lineHeight: 1.6,
            overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box',
            WebkitLineClamp: expanded ? 20 : 2, WebkitBoxOrient: 'vertical',
            transition: 'all 0.2s',
          }}>
            {ev.evaluation.summary}
          </p>
        </div>
      )}

      {/* Strengths */}
      {ev.evaluation?.strengths?.length > 0 && (
        <div style={{ padding: '0 18px', marginBottom: '12px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {ev.evaluation.strengths.slice(0, expanded ? 10 : 2).map((s, i) => (
            <span key={i} style={{ fontSize: '0.7rem', color: '#86efac', background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.15)', borderRadius: '6px', padding: '2px 8px' }}>✓ {s}</span>
          ))}
        </div>
      )}

      {/* Red flags (expanded only) */}
      {expanded && ev.evaluation?.red_flags?.length > 0 && (
        <div style={{ padding: '0 18px', marginBottom: '12px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {ev.evaluation.red_flags.map((s, i) => (
            <span key={i} style={{ fontSize: '0.7rem', color: '#fca5a5', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: '6px', padding: '2px 8px' }}>⚠ {s}</span>
          ))}
        </div>
      )}

      {/* Dimension scores (expanded) */}
      {expanded && ev.evaluation && (
        <div style={{ padding: '0 18px', marginBottom: '14px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          {['role_fit', 'compensation', 'growth', 'culture', 'location', 'team'].map(dim => {
            const d = ev.evaluation[dim];
            if (!d) return null;
            return (
              <div key={dim} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.67rem', color: 'rgba(255,255,255,0.3)', textTransform: 'capitalize', minWidth: '62px', fontWeight: 600 }}>{dim.replace('_', ' ')}</span>
                <div style={{ flex: 1, height: '5px', background: 'rgba(255,255,255,0.07)', borderRadius: '99px', overflow: 'hidden' }}>
                  <div style={{ width: `${(d.score / 5) * 100}%`, height: '100%', background: GRADE_COLOR[d.score >= 4.5 ? 'A' : d.score >= 3.5 ? 'B' : d.score >= 2.5 ? 'C' : 'D'], borderRadius: '99px' }} />
                </div>
                <span style={{ fontSize: '0.67rem', color: 'rgba(255,255,255,0.35)', minWidth: '22px', textAlign: 'right' }}>{d.score?.toFixed(1)}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer actions */}
      <div style={{ marginTop: 'auto', padding: '12px 18px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button
          onClick={() => setExpanded(v => !v)}
          style={{ padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.45)', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600, transition: 'all 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)'; e.currentTarget.style.color = 'rgba(255,255,255,0.7)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.color = 'rgba(255,255,255,0.45)'; }}
        >
          {expanded ? '▲ Menos' : '▼ Más'}
        </button>

        {ev.job_url && (
          <a href={ev.job_url} target="_blank" rel="noreferrer" style={{ padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(96,165,250,0.25)', background: 'rgba(96,165,250,0.08)', color: '#93c5fd', fontSize: '0.75rem', fontWeight: 700, textDecoration: 'none', transition: 'all 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(96,165,250,0.18)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(96,165,250,0.08)'; }}
          >
            Ver oferta ↗
          </a>
        )}

        {ev.cover_letter && (
          <button
            onClick={() => onShowCoverLetter(ev)}
            style={{ padding: '6px 10px', borderRadius: '8px', border: '1px solid rgba(167,139,250,0.25)', background: 'rgba(167,139,250,0.08)', color: '#c4b5fd', fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(167,139,250,0.18)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(167,139,250,0.08)'; }}
          >
            Ver cover
          </button>
        )}

        <button
          onClick={() => onAutoApply(ev)}
          disabled={applying === ev._id || isApplied}
          style={{
            marginLeft: 'auto',
            padding: '7px 14px', borderRadius: '9px', cursor: applying === ev._id || isApplied ? 'not-allowed' : 'pointer',
            fontWeight: 800, fontSize: '0.78rem', transition: 'all 0.18s',
            background: isApplied ? 'rgba(34,197,94,0.2)' : 'linear-gradient(135deg,#6D28D9,#4C1D95)',
            border: isApplied ? '1px solid rgba(34,197,94,0.35)' : '1px solid transparent',
            color: isApplied ? '#86efac' : '#e9d5ff',
            boxShadow: isApplied ? 'none' : '0 3px 12px rgba(109,40,217,0.35)',
            opacity: applying === ev._id ? 0.6 : 1,
          }}
        >
          {applying === ev._id ? '⏳ Generando…' : isApplied ? '✓ Aplicado' : '⚡ Auto-aplicar'}
        </button>

        {/* Delete individual */}
        <button
          onClick={e => { e.stopPropagation(); onDelete(ev._id); }}
          title="Eliminar"
          style={{ padding: '6px 9px', borderRadius: '8px', border: '1px solid transparent', background: 'none', color: 'rgba(255,255,255,0.2)', fontSize: '0.9rem', cursor: 'pointer', lineHeight: 1, transition: 'all 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.color = '#ef4444'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.35)'; e.currentTarget.style.background = 'rgba(239,68,68,0.1)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)'; e.currentTarget.style.borderColor = 'transparent'; e.currentTarget.style.background = 'none'; }}
        >✕</button>
      </div>
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────────────── */
export default function CareerOpsOffers() {
  const [evals, setEvals]       = useState([]);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [loading, setLoading]   = useState(true);
  const [applying, setApplying] = useState(null);
  const [modal, setModal]       = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Filters
  const [search, setSearch]       = useState('');
  const [gradeFilter, setGrade]   = useState('');    // '' | 'A' | 'B' | 'C' | 'D' | 'F'
  const [recFilter, setRec]       = useState('');    // '' | 'apply' | 'maybe' | 'skip'
  const [statusFilter, setStatus] = useState('');
  const [sort, setSort]           = useState('score_desc');

  const LIMIT = 18;

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    setSelected(new Set());
    try {
      const params = { page: p, limit: LIMIT };
      if (statusFilter) params.status = statusFilter;
      const { data } = await api.get('/career-ops/evaluations', { params });
      setEvals(data.evaluations || []);
      setTotal(data.total || 0);
    } catch {}
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => { setPage(1); load(1); }, [load]);

  /* Client-side filtering & sorting (works on current page) */
  const visible = evals
    .filter(ev => {
      if (gradeFilter && ev.evaluation?.grade !== gradeFilter) return false;
      if (recFilter   && ev.evaluation?.recommendation !== recFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!(ev.job_title || '').toLowerCase().includes(q) && !(ev.company_name || '').toLowerCase().includes(q)) return false;
      }
      return true;
    })
    .sort((a, b) => {
      const sa = a.evaluation?.overall_score ?? 0;
      const sb = b.evaluation?.overall_score ?? 0;
      if (sort === 'score_desc') return sb - sa;
      if (sort === 'score_asc')  return sa - sb;
      if (sort === 'date_desc')  return (b.evaluated_at || '').localeCompare(a.evaluated_at || '');
      return (a.evaluated_at || '').localeCompare(b.evaluated_at || '');
    });

  const totalPages = Math.ceil(total / LIMIT);

  const handleAutoApply = async (ev) => {
    setApplying(ev._id);
    try {
      const { data } = await api.post(`/career-ops/evaluations/${ev._id}/auto-apply`);
      const result = data.result;
      setModal({ coverLetter: result.cover_letter, jobTitle: ev.job_title, jobUrl: ev.job_url });
      if (result.applied) {
        setEvals(list => list.map(e => e._id === ev._id ? { ...e, status: 'applied' } : e));
      }
    } catch {
      alert('Error al generar la aplicación. Intenta nuevamente.');
    }
    setApplying(null);
  };

  const handleDelete = async (id) => {
    if (!confirm('¿Eliminar esta oferta?')) return;
    try {
      await api.delete(`/career-ops/evaluations/${id}`);
      setEvals(ev => ev.filter(e => e._id !== id));
      setTotal(t => t - 1);
      setSelected(prev => { const next = new Set(prev); next.delete(id); return next; });
    } catch {}
  };

  const handleBulkDelete = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    if (!confirm(`¿Eliminar ${ids.length} oferta${ids.length > 1 ? 's' : ''}?`)) return;
    setBulkDeleting(true);
    try {
      const { data } = await api.post('/career-ops/evaluations/bulk-delete', { ids });
      setEvals(ev => ev.filter(e => !selected.has(e._id)));
      setTotal(t => t - (data.deleted || ids.length));
      setSelected(new Set());
    } catch {}
    setBulkDeleting(false);
  };

  const toggleOne = (id) => setSelected(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const allVisibleSelected = visible.length > 0 && visible.every(ev => selected.has(ev._id));
  const toggleSelectAll = () => {
    if (allVisibleSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(visible.map(ev => ev._id)));
    }
  };

  const filterBtn = (active) => ({
    padding: '6px 14px', borderRadius: '99px', border: 'none', cursor: 'pointer',
    fontWeight: 700, fontSize: '0.78rem', transition: 'all 0.15s',
    background: active ? 'rgba(109,40,217,0.45)' : 'rgba(255,255,255,0.05)',
    color: active ? '#c4b5fd' : 'rgba(255,255,255,0.35)',
    border: active ? '1px solid rgba(109,40,217,0.6)' : '1px solid rgba(255,255,255,0.08)',
  });

  return (
    <div style={{ padding: '32px', maxWidth: '1280px', margin: '0 auto' }}>
      {modal && <CoverLetterModal coverLetter={modal.coverLetter} jobTitle={modal.jobTitle} jobUrl={modal.jobUrl} onClose={() => setModal(null)} />}

      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(90deg,#a78bfa,#c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Bandeja de Ofertas
        </h1>
        <p style={{ margin: '8px 0 0', color: 'rgba(255,255,255,0.4)', fontSize: '0.88rem' }}>
          {total} ofertas evaluadas · filtrá, ordená y aplicá en un clic
        </p>
      </div>

      {/* Filter bar */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '16px 20px', marginBottom: '24px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Search */}
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Buscar empresa o puesto…"
          style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', padding: '8px 14px', color: '#e9d5ff', fontSize: '0.82rem', outline: 'none', width: '220px' }}
        />

        {/* Grade filters */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.25)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Grado</span>
          <button onClick={() => setGrade('')} style={filterBtn(gradeFilter === '')}>Todos</button>
          {['A','B','C','D','F'].map(g => (
            <button key={g} onClick={() => setGrade(g === gradeFilter ? '' : g)}
              style={{ ...filterBtn(gradeFilter === g), color: gradeFilter === g ? GRADE_COLOR[g] : 'rgba(255,255,255,0.35)', border: gradeFilter === g ? `1px solid ${GRADE_COLOR[g]}55` : '1px solid rgba(255,255,255,0.08)', background: gradeFilter === g ? GRADE_BG[g] : 'rgba(255,255,255,0.05)' }}
            >{g}</button>
          ))}
        </div>

        {/* Rec filter */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.25)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Rec.</span>
          {[{v:'',l:'Todos'},{v:'apply',l:'Aplicar'},{v:'maybe',l:'Considerar'},{v:'skip',l:'Descartar'}].map(({v,l}) => (
            <button key={v} onClick={() => setRec(v === recFilter ? '' : v)} style={filterBtn(recFilter === v)}>{l}</button>
          ))}
        </div>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={e => { setStatus(e.target.value); setPage(1); }}
          style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', padding: '8px 12px', color: '#e9d5ff', fontSize: '0.8rem', outline: 'none', cursor: 'pointer', marginLeft: 'auto' }}
        >
          <option value="">Todos los estados</option>
          {Object.entries(STATUS_LABELS).map(([v,{label}]) => <option key={v} value={v}>{label}</option>)}
        </select>

        {/* Sort */}
        <select
          value={sort}
          onChange={e => setSort(e.target.value)}
          style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', padding: '8px 12px', color: '#e9d5ff', fontSize: '0.8rem', outline: 'none', cursor: 'pointer' }}
        >
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* Select all bar */}
      {!loading && visible.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
          <button
            onClick={toggleSelectAll}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '6px 14px', borderRadius: '8px', cursor: 'pointer',
              fontWeight: 700, fontSize: '0.78rem', transition: 'all 0.15s',
              background: allVisibleSelected ? 'rgba(109,40,217,0.3)' : 'rgba(255,255,255,0.05)',
              border: allVisibleSelected ? '1px solid rgba(109,40,217,0.55)' : '1px solid rgba(255,255,255,0.1)',
              color: allVisibleSelected ? '#c4b5fd' : 'rgba(255,255,255,0.45)',
            }}
            onMouseEnter={e => e.currentTarget.style.background = allVisibleSelected ? 'rgba(109,40,217,0.4)' : 'rgba(255,255,255,0.09)'}
            onMouseLeave={e => e.currentTarget.style.background = allVisibleSelected ? 'rgba(109,40,217,0.3)' : 'rgba(255,255,255,0.05)'}
          >
            <span style={{
              width: '16px', height: '16px', borderRadius: '4px', flexShrink: 0,
              border: `2px solid ${allVisibleSelected ? '#7C3AED' : 'rgba(255,255,255,0.25)'}`,
              background: allVisibleSelected ? '#7C3AED' : 'transparent',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {allVisibleSelected && <span style={{ color: '#fff', fontSize: '10px', fontWeight: 900, lineHeight: 1 }}>✓</span>}
            </span>
            {allVisibleSelected ? 'Deseleccionar todo' : `Seleccionar todo (${visible.length})`}
          </button>
          {selected.size > 0 && (
            <span style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.35)' }}>
              {selected.size} seleccionada{selected.size !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 0', color: 'rgba(255,255,255,0.25)' }}>
          <div style={{ width: '40px', height: '40px', border: '3px solid rgba(167,139,250,0.2)', borderTopColor: '#7C3AED', borderRadius: '50%', margin: '0 auto 16px', animation: 'spin 0.8s linear infinite' }} />
          Cargando ofertas…
        </div>
      ) : visible.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <p style={{ fontSize: '2rem', marginBottom: '12px' }}>🔍</p>
          <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.95rem' }}>
            {evals.length === 0
              ? 'Sin ofertas aún. Ve al Scanner y ejecuta un escaneo.'
              : 'Ninguna oferta coincide con los filtros.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px', marginBottom: '28px' }}>
          {visible.map(ev => (
            <JobCard
              key={ev._id}
              ev={ev}
              onAutoApply={handleAutoApply}
              applying={applying}
              onShowCoverLetter={ev => setModal({ coverLetter: ev.cover_letter, jobTitle: ev.job_title, jobUrl: ev.job_url })}
              onDelete={handleDelete}
              selected={selected.has(ev._id)}
              onToggleSelect={() => toggleOne(ev._id)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }}>
          <button onClick={() => { setPage(p => p - 1); load(page - 1); }} disabled={page === 1}
            style={{ padding: '8px 16px', borderRadius: '9px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: page === 1 ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.6)', cursor: page === 1 ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.82rem' }}>
            ← Anterior
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map(p => (
            <button key={p} onClick={() => { setPage(p); load(p); }}
              style={{ width: '38px', height: '38px', borderRadius: '9px', border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: '0.85rem', background: page === p ? 'rgba(109,40,217,0.5)' : 'rgba(255,255,255,0.05)', color: page === p ? '#c4b5fd' : 'rgba(255,255,255,0.35)' }}>
              {p}
            </button>
          ))}
          <button onClick={() => { setPage(p => p + 1); load(page + 1); }} disabled={page === totalPages}
            style={{ padding: '8px 16px', borderRadius: '9px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: page === totalPages ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.6)', cursor: page === totalPages ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: '0.82rem' }}>
            Siguiente →
          </button>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* Bulk action bar */}
      <div style={{
        position: 'fixed', bottom: '28px', left: '50%',
        transform: `translateX(-50%) translateY(${selected.size > 0 ? '0' : '120px'})`,
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
          style={{ padding: '7px 18px', borderRadius: '9px', fontWeight: 800, fontSize: '0.82rem', cursor: bulkDeleting ? 'not-allowed' : 'pointer', background: bulkDeleting ? 'rgba(239,68,68,0.1)' : 'rgba(239,68,68,0.2)', border: '1px solid rgba(239,68,68,0.4)', color: '#fca5a5', transition: 'all 0.15s', opacity: bulkDeleting ? 0.6 : 1 }}
          onMouseEnter={e => { if (!bulkDeleting) e.currentTarget.style.background = 'rgba(239,68,68,0.35)'; }}
          onMouseLeave={e => { if (!bulkDeleting) e.currentTarget.style.background = 'rgba(239,68,68,0.2)'; }}
        >
          {bulkDeleting ? 'Eliminando…' : `🗑 Eliminar ${selected.size}`}
        </button>
      </div>
    </div>
  );
}
