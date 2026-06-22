import { useState } from 'react';
import api from '../api';

const GRADE_COLOR = { A: '#22c55e', B: '#84cc16', C: '#eab308', D: '#f97316', F: '#ef4444' };
const GRADE_BG   = { A: 'rgba(34,197,94,0.15)', B: 'rgba(132,204,22,0.15)', C: 'rgba(234,179,8,0.15)', D: 'rgba(249,115,22,0.15)', F: 'rgba(239,68,68,0.15)' };

const REC_COLOR = { apply: '#22c55e', maybe: '#eab308', skip: '#ef4444' };
const REC_LABEL = { apply: 'Aplicar', maybe: 'Considerar', skip: 'Descartar' };

const STATUS_OPTIONS = [
  { value: 'evaluated', label: 'Evaluado' },
  { value: 'applied',   label: 'Aplicado' },
  { value: 'responded', label: 'Respondió' },
  { value: 'interview', label: 'Entrevista' },
  { value: 'offer',     label: 'Oferta' },
  { value: 'rejected',  label: 'Rechazado' },
  { value: 'discarded', label: 'Descartado' },
];

function ScoreBar({ score }) {
  const pct = ((score - 1) / 4) * 100;
  const color = score >= 4 ? '#22c55e' : score >= 3 ? '#eab308' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '99px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: '99px', transition: 'width 0.6s ease' }} />
      </div>
      <span style={{ fontSize: '0.8rem', fontWeight: 700, color, minWidth: '28px', textAlign: 'right' }}>{score.toFixed(1)}</span>
    </div>
  );
}

function DimensionRow({ label, dim }) {
  if (!dim) return null;
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'rgba(255,255,255,0.6)' }}>{label}</span>
        <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.3)' }}>{dim.label}</span>
      </div>
      <ScoreBar score={dim.score} />
      {dim.notes && <p style={{ margin: '6px 0 0', fontSize: '0.76rem', color: 'rgba(255,255,255,0.35)', lineHeight: 1.5 }}>{dim.notes}</p>}
    </div>
  );
}

function EvalResult({ data, onStatusChange }) {
  const ev = data.evaluation;
  const [status, setStatus] = useState(data.status || 'evaluated');
  const [updating, setUpdating] = useState(false);

  const handleStatus = async (val) => {
    setUpdating(true);
    try {
      await api.patch(`/career-ops/evaluations/${data._id}/status`, { status: val });
      setStatus(val);
    } catch {}
    setUpdating(false);
    onStatusChange?.();
  };

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${GRADE_COLOR[ev.grade] || 'rgba(255,255,255,0.08)'}33`,
      borderRadius: '20px',
      padding: '28px',
      marginTop: '28px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
            <span style={{
              width: '48px', height: '48px', borderRadius: '14px', flexShrink: 0,
              background: GRADE_BG[ev.grade], border: `2px solid ${GRADE_COLOR[ev.grade]}55`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.5rem', fontWeight: 900, color: GRADE_COLOR[ev.grade],
            }}>{ev.grade}</span>
            <div>
              <p style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#e9d5ff' }}>
                {data.job_title || 'Oferta evaluada'}{data.company_name ? ` · ${data.company_name}` : ''}
              </p>
              <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: 'rgba(255,255,255,0.35)' }}>
                Score global: <strong style={{ color: GRADE_COLOR[ev.grade] }}>{ev.overall_score?.toFixed(1)}/5.0</strong>
              </p>
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{
            padding: '5px 14px', borderRadius: '99px', fontSize: '0.8rem', fontWeight: 700,
            background: `${REC_COLOR[ev.recommendation]}22`,
            border: `1px solid ${REC_COLOR[ev.recommendation]}44`,
            color: REC_COLOR[ev.recommendation],
          }}>
            {REC_LABEL[ev.recommendation] || ev.recommendation}
          </span>
          <select
            value={status}
            onChange={e => handleStatus(e.target.value)}
            disabled={updating}
            style={{
              background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)',
              color: '#e9d5ff', borderRadius: '10px', padding: '6px 12px',
              fontSize: '0.8rem', cursor: 'pointer', outline: 'none',
            }}
          >
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* Summary */}
      <p style={{ margin: '0 0 24px', fontSize: '0.88rem', color: 'rgba(255,255,255,0.55)', lineHeight: 1.65, background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '14px 18px' }}>
        {ev.summary}
      </p>

      {/* Dimensions */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 32px', marginBottom: '24px' }}>
        <div>
          <DimensionRow label="Fit con el rol" dim={ev.role_fit} />
          <DimensionRow label="Compensación" dim={ev.compensation} />
          <DimensionRow label="Crecimiento" dim={ev.growth} />
        </div>
        <div>
          <DimensionRow label="Cultura" dim={ev.culture} />
          <DimensionRow label="Ubicación / Modalidad" dim={ev.location} />
          <DimensionRow label="Equipo" dim={ev.team} />
        </div>
      </div>

      {/* Strengths & Red flags */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
        {ev.strengths?.length > 0 && (
          <div style={{ background: 'rgba(34,197,94,0.07)', border: '1px solid rgba(34,197,94,0.15)', borderRadius: '12px', padding: '16px' }}>
            <p style={{ margin: '0 0 10px', fontSize: '0.72rem', fontWeight: 700, color: '#86efac', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Fortalezas</p>
            {ev.strengths.map((s, i) => <p key={i} style={{ margin: '0 0 5px', fontSize: '0.8rem', color: 'rgba(255,255,255,0.55)' }}>✓ {s}</p>)}
          </div>
        )}
        {ev.red_flags?.length > 0 && (
          <div style={{ background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: '12px', padding: '16px' }}>
            <p style={{ margin: '0 0 10px', fontSize: '0.72rem', fontWeight: 700, color: '#fca5a5', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Red flags</p>
            {ev.red_flags.map((s, i) => <p key={i} style={{ margin: '0 0 5px', fontSize: '0.8rem', color: 'rgba(255,255,255,0.55)' }}>⚠ {s}</p>)}
          </div>
        )}
      </div>

      {/* Talking points */}
      {ev.talking_points?.length > 0 && (
        <div style={{ background: 'rgba(109,40,217,0.1)', border: '1px solid rgba(109,40,217,0.2)', borderRadius: '12px', padding: '16px' }}>
          <p style={{ margin: '0 0 10px', fontSize: '0.72rem', fontWeight: 700, color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Puntos clave para tu aplicación</p>
          {ev.talking_points.map((t, i) => <p key={i} style={{ margin: '0 0 5px', fontSize: '0.8rem', color: 'rgba(255,255,255,0.55)' }}>→ {t}</p>)}
        </div>
      )}
    </div>
  );
}

export default function CareerOpsPipeline() {
  const [jobText, setJobText] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [company, setCompany] = useState('');
  const [jobUrl, setJobUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const evaluate = async () => {
    if (!jobText.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const { data } = await api.post('/career-ops/evaluate', {
        job_text: jobText,
        job_title: jobTitle,
        company_name: company,
        job_url: jobUrl,
      });
      setResult(data.evaluation);
    } catch (e) {
      setError(e.response?.data?.detail || 'Error evaluando la oferta');
    }
    setLoading(false);
  };

  return (
    <div style={{ padding: '32px', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(90deg, #a78bfa, #c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Career Ops — Evaluar oferta
        </h1>
        <p style={{ margin: '8px 0 0', color: 'rgba(255,255,255,0.4)', fontSize: '0.88rem' }}>
          Pega la descripción de trabajo y la IA la evalúa contra tu perfil con un score A–F.
        </p>
      </div>

      {/* Input form */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          {[
            { label: 'Título del puesto', val: jobTitle, set: setJobTitle, ph: 'Ej: Senior AI Engineer' },
            { label: 'Empresa', val: company, set: setCompany, ph: 'Ej: OpenAI' },
            { label: 'URL de la oferta (opcional)', val: jobUrl, set: setJobUrl, ph: 'https://…' },
          ].map(({ label, val, set, ph }) => (
            <div key={label}>
              <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: 'rgba(255,255,255,0.4)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</label>
              <input value={val} onChange={e => set(e.target.value)} placeholder={ph} style={{
                width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '10px', padding: '10px 12px', color: '#e9d5ff', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box',
              }} />
            </div>
          ))}
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: 'rgba(255,255,255,0.4)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Descripción del puesto *
          </label>
          <textarea
            value={jobText}
            onChange={e => setJobText(e.target.value)}
            placeholder="Pega aquí el texto completo de la oferta de trabajo…"
            style={{
              width: '100%', minHeight: '220px', background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px',
              padding: '14px', color: '#e9d5ff', fontSize: '0.88rem', outline: 'none',
              resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.6, boxSizing: 'border-box',
            }}
          />
        </div>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '10px', padding: '12px 16px', color: '#fca5a5', fontSize: '0.85rem', marginBottom: '14px' }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={evaluate}
            disabled={loading || !jobText.trim()}
            style={{
              background: loading ? 'rgba(109,40,217,0.3)' : 'linear-gradient(135deg, #6D28D9, #4C1D95)',
              border: 'none', color: '#e9d5ff', borderRadius: '12px', padding: '12px 32px',
              fontSize: '0.9rem', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: loading ? 'none' : '0 4px 20px rgba(109,40,217,0.4)',
              display: 'flex', alignItems: 'center', gap: '10px', transition: 'all 0.2s',
            }}
          >
            {loading ? (
              <>
                <span style={{ width: '16px', height: '16px', borderRadius: '50%', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#a78bfa', animation: 'spin 0.8s linear infinite', display: 'inline-block' }} />
                Evaluando…
              </>
            ) : '⚡ Evaluar oferta'}
          </button>
        </div>
      </div>

      {result && <EvalResult data={result} />}
    </div>
  );
}
