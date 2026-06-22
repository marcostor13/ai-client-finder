import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search, Building2, Loader2, Mail, Phone,
  Globe, MapPin, Crown, FileText, AlertTriangle,
  Package, Users, ExternalLink, BadgeCheck, PenLine, Check,
} from 'lucide-react';
import api from '../api';

// ── Helpers ──────────────────────────────────────────────────────────────────

const RANK_LABELS = {
  0: 'Dueño / Fundador', 1: 'Alta dirección (C-Level)', 2: 'Subgerencia / Dirección',
  3: 'Gerencia / Jefatura', 4: 'Coordinación / Supervisión', 5: 'Senior / Especialista',
  6: 'Staff / Analista', 9: 'Sin clasificar',
};
const RANK_COLOR = {
  0: '#FAB014', 1: '#a78bfa', 2: '#22d3ee', 3: '#4ade80',
  4: '#60a5fa', 5: '#cbd5e1', 6: '#94a3b8', 9: '#6b7280',
};

const STATUS_TEXT = {
  pending: 'En cola…', resolving: 'Resolviendo empresa…', crawling: 'Crawleando web…',
  discovering: 'Descubriendo personas…', enriching: 'Enriqueciendo contactos…',
  analyzing: 'Generando informes…', done: 'Completado', failed: 'Error',
};

const SOCIAL_ICON = {};  // todas las redes → ícono Globe (lucide quitó iconos de marca)

const card = {
  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '16px', padding: '20px', backdropFilter: 'blur(12px)',
};

function SocialLinks({ socials }) {
  if (!socials?.length) return null;
  return (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      {socials.map((s, i) => {
        const Icon = SOCIAL_ICON[s.network] || Globe;
        return (
          <a key={i} href={s.url} target="_blank" rel="noreferrer"
            title={s.network}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '5px',
              background: 'rgba(109,40,217,0.18)', color: '#a78bfa', padding: '4px 9px',
              borderRadius: '8px', fontSize: '0.72rem', textDecoration: 'none' }}>
            <Icon size={12} /> {s.network}
          </a>
        );
      })}
    </div>
  );
}

function PersonRow({ p, onDraft, draftState }) {
  const color = RANK_COLOR[p.rank] ?? '#6b7280';
  const hasEmail = (p.emails || []).length > 0;
  return (
    <div style={{ ...card, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: 34, height: 34, borderRadius: '50%', background: `${color}22`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            {p.rank <= 1 ? <Crown size={16} style={{ color }} /> : <Users size={15} style={{ color }} />}
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-main)' }}>{p.name}</div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{p.title || '—'}</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {hasEmail && (
            <button onClick={onDraft} disabled={draftState === 'loading' || draftState === 'done'}
              title="Redactar email de prospección y enviarlo a la cola de aprobación"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '5px 10px',
                borderRadius: '8px', border: '1px solid rgba(109,40,217,0.4)', cursor: 'pointer',
                background: draftState === 'done' ? 'rgba(34,197,94,0.15)' : 'rgba(109,40,217,0.15)',
                color: draftState === 'done' ? '#4ade80' : '#a78bfa', fontSize: '0.72rem', fontWeight: 600 }}>
              {draftState === 'loading' ? <Loader2 size={12} className="spin" />
                : draftState === 'done' ? <Check size={12} /> : <PenLine size={12} />}
              {draftState === 'done' ? 'En cola' : draftState === 'loading' ? '…' : 'Redactar'}
            </button>
          )}
          <span style={{ fontSize: '0.68rem', color, background: `${color}1a`, padding: '3px 9px',
            borderRadius: '99px', fontWeight: 600, whiteSpace: 'nowrap' }}>
            {RANK_LABELS[p.rank] ?? 'Sin clasificar'}
          </span>
        </div>
      </div>
      {(p.emails?.length || p.phones?.length || p.socials?.length) ? (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          {p.emails?.map((e, i) => (
            <a key={`e${i}`} href={`mailto:${e}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px',
              background: 'rgba(34,197,94,0.12)', color: '#4ade80', padding: '4px 9px', borderRadius: '8px',
              fontSize: '0.74rem', textDecoration: 'none' }}><Mail size={12} /> {e}</a>
          ))}
          {p.phones?.map((ph, i) => (
            <a key={`p${i}`} href={`tel:${ph}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px',
              background: 'rgba(96,165,250,0.12)', color: '#60a5fa', padding: '4px 9px', borderRadius: '8px',
              fontSize: '0.74rem', textDecoration: 'none' }}><Phone size={12} /> {ph}</a>
          ))}
          <SocialLinks socials={p.socials} />
        </div>
      ) : (
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>Sin contacto directo encontrado</span>
      )}
      {p.sources?.length ? (
        <div style={{ fontSize: '0.64rem', color: 'rgba(255,255,255,0.35)' }}>
          fuentes: {p.sources.join(', ')}
        </div>
      ) : null}
    </div>
  );
}

function ReportBlock({ icon: Icon, title, text, accent }) {
  if (!text) return null;
  return (
    <div style={card}>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95rem',
        margin: '0 0 12px', color: accent }}>
        <Icon size={16} /> {title}
      </h3>
      <p style={{ fontSize: '0.85rem', lineHeight: 1.7, color: 'var(--text-main)',
        whiteSpace: 'pre-wrap', margin: 0 }}>{text}</p>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function CompanyIntel() {
  const [query, setQuery] = useState('');
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [draftStates, setDraftStates] = useState({});   // idx -> idle|loading|done
  const [draftMsg, setDraftMsg] = useState('');
  const pollRef = useRef(null);

  const stopPolling = () => { if (pollRef.current) clearInterval(pollRef.current); pollRef.current = null; };
  useEffect(() => stopPolling, []);

  const poll = useCallback((id) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get(`/api/company-intel/jobs/${id}`);
        setJob(data);
        if (data.status === 'done' || data.status === 'failed') {
          stopPolling();
          setLoading(false);
          if (data.status === 'failed') setError(data.error || 'Falló el análisis.');
        }
      } catch (e) { stopPolling(); setLoading(false); setError('Error consultando el job.'); }
    }, 1500);
  }, []);

  const run = async (e) => {
    e?.preventDefault();
    if (query.trim().length < 3) { setError('Ingresa un RUC o nombre válido.'); return; }
    setError(''); setJob(null); setLoading(true);
    try {
      const { data } = await api.post('/api/company-intel/search', { query: query.trim() });
      poll(data.id);
    } catch (e) {
      setLoading(false);
      setError(e?.response?.data?.detail || 'No se pudo iniciar la búsqueda.');
    }
  };

  const draftOne = async (idx) => {
    if (!job?.id) return;
    setDraftStates((s) => ({ ...s, [idx]: 'loading' }));
    try {
      const { data } = await api.post(`/api/company-intel/jobs/${job.id}/draft`, { indices: [idx] });
      const r = (data.results || [])[0];
      setDraftStates((s) => ({ ...s, [idx]: r?.status === 'drafted' ? 'done' : 'idle' }));
      if (r && r.status !== 'drafted') setDraftMsg(`${r.name}: ${r.reason || 'no se pudo redactar'}`);
    } catch (e) {
      setDraftStates((s) => ({ ...s, [idx]: 'idle' }));
      setDraftMsg(e?.response?.data?.detail || 'Error al redactar.');
    }
  };

  const draftAll = async () => {
    if (!job?.id) return;
    const idxs = people.map((p, i) => (p.emails?.length ? i : null)).filter((i) => i !== null);
    setDraftStates((s) => { const n = { ...s }; idxs.forEach((i) => (n[i] = 'loading')); return n; });
    setDraftMsg('Redactando…');
    try {
      const { data } = await api.post(`/api/company-intel/jobs/${job.id}/draft`, {});
      const byName = {};
      (data.results || []).forEach((r) => { byName[r.name] = r.status; });
      setDraftStates((s) => {
        const n = { ...s };
        people.forEach((p, i) => { if (byName[p.name]) n[i] = byName[p.name] === 'drafted' ? 'done' : 'idle'; });
        return n;
      });
      setDraftMsg(`${data.drafted} redactados · ${data.skipped} omitidos · ${data.errors} errores. Revisa la Cola de aprobación.`);
    } catch (e) {
      setDraftMsg(e?.response?.data?.detail || 'Error al redactar.');
    }
  };

  const company = job?.company;
  const people = job?.people || [];
  const products = job?.products || [];
  const report = job?.report;
  const progress = job?.progress || 0;

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '8px 4px 60px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '1.5rem', margin: '0 0 6px' }}>
          <Building2 style={{ color: 'var(--primary-glow)' }} /> Inteligencia de empresas
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', margin: 0 }}>
          Ingresa el RUC o nombre de una empresa. Obtendrás su organigrama (gerentes → empleados)
          con contactos públicos, redes, productos/servicios e informe de falencias.
        </p>
      </div>

      <form onSubmit={run} style={{ display: 'flex', gap: '10px', marginBottom: '24px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 260 }}>
          <Search size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="RUC (11 dígitos) o nombre de la empresa…"
            style={{ width: '100%', padding: '13px 14px 13px 40px', borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.05)',
              color: 'var(--text-main)', fontSize: '0.92rem', outline: 'none' }} />
        </div>
        <button type="submit" disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '13px 22px',
            borderRadius: '12px', border: 'none', cursor: loading ? 'wait' : 'pointer',
            background: 'linear-gradient(135deg, #6D28D9, #4C1D95)', color: '#fff', fontWeight: 600,
            fontSize: '0.92rem', opacity: loading ? 0.7 : 1 }}>
          {loading ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
          {loading ? 'Analizando…' : 'Analizar'}
        </button>
      </form>

      {error && (
        <div style={{ ...card, borderColor: 'rgba(239,68,68,0.4)', color: '#fca5a5', marginBottom: '20px',
          display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem' }}>
          <AlertTriangle size={15} /> {error}
        </div>
      )}

      {loading && (
        <div style={{ ...card, marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
            <Loader2 size={16} className="spin" style={{ color: 'var(--primary-glow)' }} />
            <span style={{ fontSize: '0.88rem' }}>{STATUS_TEXT[job?.status] || 'Procesando…'}</span>
            <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--text-muted)' }}>{progress}%</span>
          </div>
          <div style={{ height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{ width: `${progress}%`, height: '100%', borderRadius: 99,
              background: 'linear-gradient(90deg, #6D28D9, #22d3ee)', transition: 'width 0.5s ease' }} />
          </div>
        </div>
      )}

      {company && (
        <div style={{ ...card, marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
            <div>
              <h2 style={{ margin: '0 0 4px', fontSize: '1.15rem' }}>
                {company.legal_name || company.trade_name || company.query}
              </h2>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {company.ruc && <span><BadgeCheck size={12} style={{ verticalAlign: -2 }} /> RUC {company.ruc}</span>}
                {company.status && <span>{company.status}</span>}
                {company.address && <span><MapPin size={12} style={{ verticalAlign: -2 }} /> {company.address}</span>}
              </div>
            </div>
            {company.website && (
              <a href={company.website} target="_blank" rel="noreferrer"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#a78bfa',
                  fontSize: '0.8rem', textDecoration: 'none' }}>
                <Globe size={13} /> {company.domain} <ExternalLink size={11} />
              </a>
            )}
          </div>
          {(company.emails?.length || company.phones?.length) ? (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
              {company.emails?.map((e, i) => (
                <a key={i} href={`mailto:${e}`} style={{ fontSize: '0.74rem', background: 'rgba(34,197,94,0.12)',
                  color: '#4ade80', padding: '4px 9px', borderRadius: '8px', textDecoration: 'none' }}>
                  <Mail size={11} style={{ verticalAlign: -2 }} /> {e}</a>
              ))}
              {company.phones?.map((p, i) => (
                <span key={i} style={{ fontSize: '0.74rem', background: 'rgba(96,165,250,0.12)',
                  color: '#60a5fa', padding: '4px 9px', borderRadius: '8px' }}>
                  <Phone size={11} style={{ verticalAlign: -2 }} /> {p}</span>
              ))}
            </div>
          ) : null}
          <div style={{ marginTop: '12px' }}><SocialLinks socials={company.socials} /></div>
        </div>
      )}

      {report && (
        <div style={{ display: 'grid', gap: '16px', marginBottom: '20px' }}>
          <ReportBlock icon={FileText} title="Información de la empresa" text={report.company_overview} accent="#a78bfa" />
          <ReportBlock icon={Package} title="Productos y servicios" text={report.products_services} accent="#22d3ee" />
          <ReportBlock icon={AlertTriangle} title="Informe de falencias" text={report.weaknesses} accent="#FAB014" />
        </div>
      )}

      {people.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '12px' }}>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.05rem', margin: 0 }}>
              <Users size={17} style={{ color: 'var(--primary-glow)' }} /> Personas ({people.length}) · de mayor a menor rango
            </h2>
            {people.some((p) => p.emails?.length) && (
              <button onClick={draftAll}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 14px',
                  borderRadius: '10px', border: 'none', cursor: 'pointer',
                  background: 'linear-gradient(135deg, #6D28D9, #4C1D95)', color: '#fff',
                  fontWeight: 600, fontSize: '0.8rem' }}>
                <PenLine size={14} /> Redactar a todos con email
              </button>
            )}
          </div>
          {draftMsg && (
            <div style={{ ...card, padding: '10px 14px', marginBottom: '12px', fontSize: '0.8rem',
              color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Check size={14} style={{ color: '#4ade80' }} /> {draftMsg}
            </div>
          )}
          <div style={{ display: 'grid', gap: '10px' }}>
            {people.map((p, i) => (
              <PersonRow key={i} p={p} draftState={draftStates[i] || 'idle'} onDraft={() => draftOne(i)} />
            ))}
          </div>
        </div>
      )}

      {products.length > 0 && (
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.05rem', margin: '0 0 12px' }}>
            <Package size={17} style={{ color: 'var(--primary-glow)' }} /> Productos / Servicios ({products.length})
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px' }}>
            {products.map((pr, i) => (
              <div key={i} style={{ ...card, padding: '14px' }}>
                <div style={{ fontWeight: 600, fontSize: '0.86rem', marginBottom: '4px' }}>{pr.name}</div>
                {pr.description && <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>{pr.description}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {job?.status === 'done' && people.length === 0 && (
        <div style={{ ...card, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          No se encontraron personas con datos públicos. Prueba con el RUC exacto o el nombre legal completo.
        </div>
      )}

      <style>{`.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}
