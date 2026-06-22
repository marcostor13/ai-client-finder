import { useState, useEffect } from 'react';
import { Settings, Save, Plus, Trash2, RotateCcw, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import api from '../api';

const DEFAULT_CONFIG = {
  search_queries: [
    'clínicas dentales Lima sin presencia digital',
    'restaurantes Lima sin página web',
    'spas masajes Lima contacto',
  ],
  target_geos: ['lima', 'peru', 'mexico', 'colombia', 'chile', 'argentina', 'españa'],
  target_industries: ['dental', 'clinica', 'restaurant', 'spa', 'retail', 'hotel', 'educacion'],
  scoring_weights: { geo: 15, industry: 25, has_website: 10, digital_gap: 30, description: 20 },
  brand_voice: '',
  case_studies: [''],
  notification_email: '',
};

// ── Reusable sub-components ──────────────────────────────────────────────────

function Section({ title, children }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '14px', border: '1px solid var(--glass-border)', padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{title}</h3>
      {children}
    </div>
  );
}

function Label({ children }) {
  return <label style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>{children}</label>;
}

function InputStyle() {
  return {
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid var(--glass-border)',
    borderRadius: '8px',
    padding: '9px 12px',
    color: 'var(--text-main)',
    fontSize: '0.88rem',
    width: '100%',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.2s',
  };
}

function TagList({ label, items, onChange }) {
  const [input, setInput] = useState('');

  function add() {
    const val = input.trim().toLowerCase();
    if (val && !items.includes(val)) onChange([...items, val]);
    setInput('');
  }

  function remove(idx) {
    onChange(items.filter((_, i) => i !== idx));
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <Label>{label}</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', minHeight: '32px' }}>
        {items.map((item, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(109,40,217,0.25)', border: '1px solid rgba(167,139,250,0.35)', borderRadius: '20px', padding: '3px 10px 3px 12px', fontSize: '0.8rem', color: 'var(--accent)' }}>
            {item}
            <button onClick={() => remove(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 0 }}>
              <Trash2 size={11} />
            </button>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder="Escribe y presiona Enter"
          style={{ ...InputStyle(), flex: 1 }}
        />
        <button onClick={add} style={{ background: 'rgba(109,40,217,0.4)', border: '1px solid rgba(167,139,250,0.3)', borderRadius: '8px', padding: '9px 13px', cursor: 'pointer', color: 'var(--accent)', display: 'flex', alignItems: 'center' }}>
          <Plus size={15} />
        </button>
      </div>
    </div>
  );
}

function WeightSlider({ label, field, value, onChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Label>{label}</Label>
        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--accent)' }}>{value} pts</span>
      </div>
      <input
        type="range" min={0} max={50} step={5} value={value}
        onChange={e => onChange(field, Number(e.target.value))}
        style={{ accentColor: 'var(--primary-glow)', cursor: 'pointer' }}
      />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ICPConfigForm() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [status, setStatus] = useState('idle'); // idle | loading | saving | saved | error
  const [errorMsg, setErrorMsg] = useState('');
  const [version, setVersion] = useState(null);

  useEffect(() => {
    setStatus('loading');
    api.get('/api/outbound/icp-config')
      .then(res => {
        if (res.data.config?.config_json) {
          setConfig({ ...DEFAULT_CONFIG, ...res.data.config.config_json });
          setVersion(res.data.config.version);
        }
        setStatus('idle');
      })
      .catch(() => setStatus('idle'));
  }, []);

  function setField(key, value) {
    setConfig(prev => ({ ...prev, [key]: value }));
  }

  function setWeight(field, value) {
    setConfig(prev => ({ ...prev, scoring_weights: { ...prev.scoring_weights, [field]: value } }));
  }

  function setCaseStudy(idx, value) {
    const updated = [...config.case_studies];
    updated[idx] = value;
    setConfig(prev => ({ ...prev, case_studies: updated }));
  }

  function addCaseStudy() {
    setConfig(prev => ({ ...prev, case_studies: [...prev.case_studies, ''] }));
  }

  function removeCaseStudy(idx) {
    setConfig(prev => ({ ...prev, case_studies: prev.case_studies.filter((_, i) => i !== idx) }));
  }

  async function handleSave() {
    setStatus('saving');
    setErrorMsg('');
    try {
      const res = await api.post('/api/outbound/icp-config', config);
      setVersion(res.data.config.version);
      setStatus('saved');
      setTimeout(() => setStatus('idle'), 2500);
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Error al guardar');
      setStatus('error');
    }
  }

  const totalWeights = Object.values(config.scoring_weights).reduce((a, b) => a + b, 0);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-deep)' }}>
    <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px 20px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'rgba(109,40,217,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Settings size={20} style={{ color: 'var(--accent)' }} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 800 }}>Configuración ICP</h1>
            {version && <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>versión activa: v{version}</p>}
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={status === 'saving' || status === 'loading'}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', background: status === 'saved' ? 'rgba(34,197,94,0.25)' : 'rgba(109,40,217,0.5)', border: `1px solid ${status === 'saved' ? 'rgba(34,197,94,0.5)' : 'rgba(167,139,250,0.4)'}`, borderRadius: '10px', padding: '10px 20px', color: status === 'saved' ? '#86efac' : 'var(--accent)', fontSize: '0.88rem', fontWeight: 700, cursor: 'pointer', transition: 'var(--transition)', fontFamily: 'inherit' }}
        >
          {status === 'saving' ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> : status === 'saved' ? <CheckCircle size={15} /> : <Save size={15} />}
          {status === 'saving' ? 'Guardando…' : status === 'saved' ? 'Guardado' : 'Guardar versión'}
        </button>
      </div>

      {status === 'error' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '10px', padding: '12px 16px', color: '#fca5a5', fontSize: '0.85rem' }}>
          <AlertCircle size={16} />
          {errorMsg}
        </div>
      )}

      {/* Search queries */}
      <Section title="Consultas de búsqueda">
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>El Job A usa estas queries para encontrar empresas vía DDG cada día.</p>
        {config.search_queries.map((q, i) => (
          <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <input
              value={q}
              onChange={e => {
                const updated = [...config.search_queries];
                updated[i] = e.target.value;
                setField('search_queries', updated);
              }}
              style={{ ...InputStyle(), flex: 1 }}
            />
            <button onClick={() => setField('search_queries', config.search_queries.filter((_, j) => j !== i))} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px' }}>
              <Trash2 size={15} />
            </button>
          </div>
        ))}
        <button onClick={() => setField('search_queries', [...config.search_queries, ''])} style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: '1px dashed rgba(255,255,255,0.2)', borderRadius: '8px', padding: '8px 14px', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.82rem', fontFamily: 'inherit' }}>
          <Plus size={14} /> Añadir query
        </button>
      </Section>

      {/* Geo + Industry tags */}
      <Section title="Segmentación">
        <TagList label="Geos objetivo" items={config.target_geos} onChange={v => setField('target_geos', v)} />
        <TagList label="Industrias objetivo" items={config.target_industries} onChange={v => setField('target_industries', v)} />
      </Section>

      {/* Scoring weights */}
      <Section title={`Pesos de scoring (total: ${totalWeights} pts)`}>
        {totalWeights !== 100 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: '#fbbf24' }}>
            <AlertCircle size={13} /> Los pesos suman {totalWeights}, no 100. El scoring se aplica igual, pero los tiers podrían desbalancearse.
          </div>
        )}
        <WeightSlider label="Geolocalización" field="geo" value={config.scoring_weights.geo ?? 15} onChange={setWeight} />
        <WeightSlider label="Industria" field="industry" value={config.scoring_weights.industry ?? 25} onChange={setWeight} />
        <WeightSlider label="Tiene sitio web" field="has_website" value={config.scoring_weights.has_website ?? 10} onChange={setWeight} />
        <WeightSlider label="Señales de brecha digital" field="digital_gap" value={config.scoring_weights.digital_gap ?? 30} onChange={setWeight} />
        <WeightSlider label="Calidad de descripción" field="description" value={config.scoring_weights.description ?? 20} onChange={setWeight} />
        <button
          onClick={() => setField('scoring_weights', DEFAULT_CONFIG.scoring_weights)}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.8rem', fontFamily: 'inherit', alignSelf: 'flex-start' }}
        >
          <RotateCcw size={12} /> Restaurar defaults
        </button>
      </Section>

      {/* Brand voice */}
      <Section title="Voz de marca">
        <Label>Tono y estilo para los emails generados por el LLM</Label>
        <textarea
          value={config.brand_voice}
          onChange={e => setField('brand_voice', e.target.value)}
          rows={5}
          placeholder="Ej: Tono directo y cercano, sin corporativo. Enfócate en el resultado de negocio, no en la tecnología. Firma siempre con nombre real…"
          style={{ ...InputStyle(), resize: 'vertical', lineHeight: 1.6 }}
        />
      </Section>

      {/* Case studies */}
      <Section title="Casos de éxito">
        <Label>Resúmenes que el LLM puede citar al personalizar emails (máx. 3)</Label>
        {config.case_studies.map((cs, i) => (
          <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <textarea
              value={cs}
              onChange={e => setCaseStudy(i, e.target.value)}
              rows={3}
              placeholder={`Caso ${i + 1}: empresa, problema, solución, resultado en números`}
              style={{ ...InputStyle(), flex: 1, resize: 'vertical', lineHeight: 1.5 }}
            />
            {config.case_studies.length > 1 && (
              <button onClick={() => removeCaseStudy(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '10px 4px' }}>
                <Trash2 size={15} />
              </button>
            )}
          </div>
        ))}
        {config.case_studies.length < 3 && (
          <button onClick={addCaseStudy} style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: '1px dashed rgba(255,255,255,0.2)', borderRadius: '8px', padding: '8px 14px', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.82rem', fontFamily: 'inherit' }}>
            <Plus size={14} /> Añadir caso
          </button>
        )}
      </Section>

      {/* Notification email */}
      <Section title="Notificaciones">
        <Label>Email del dueño — recibe digest diario cuando hay drafts pendientes</Label>
        <input
          type="email"
          value={config.notification_email}
          onChange={e => setField('notification_email', e.target.value)}
          placeholder="tu@email.com"
          style={InputStyle()}
        />
      </Section>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
    </div>
  );
}
