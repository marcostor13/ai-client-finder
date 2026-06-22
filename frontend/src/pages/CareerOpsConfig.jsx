import { useState, useEffect, useRef } from 'react';
import api from '../api';

const SECTION = ({ title, children }) => (
  <div style={{
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '16px',
    padding: '24px',
    marginBottom: '20px',
  }}>
    <h3 style={{ margin: '0 0 20px', fontSize: '0.85rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'rgba(167,139,250,0.8)' }}>
      {title}
    </h3>
    {children}
  </div>
);

const Field = ({ label, highlight, children }) => (
  <div style={{ marginBottom: '16px' }}>
    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', fontWeight: 600, color: 'rgba(255,255,255,0.45)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
      {label}
      {highlight && (
        <span style={{ fontSize: '0.65rem', background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.3)', color: '#86efac', borderRadius: '99px', padding: '1px 7px', fontWeight: 700, textTransform: 'none', letterSpacing: 0 }}>
          ✓ auto
        </span>
      )}
    </label>
    {children}
  </div>
);

const mkInputStyle = (highlight) => ({
  width: '100%',
  background: highlight ? 'rgba(34,197,94,0.06)' : 'rgba(255,255,255,0.05)',
  border: `1px solid ${highlight ? 'rgba(34,197,94,0.35)' : 'rgba(255,255,255,0.1)'}`,
  borderRadius: '10px',
  padding: '10px 14px',
  color: '#e9d5ff',
  fontSize: '0.88rem',
  outline: 'none',
  boxSizing: 'border-box',
  transition: 'border-color 0.3s, background 0.3s',
});

const ROW = ({ children }) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>{children}</div>
);

function TagInput({ value, onChange, placeholder, highlight }) {
  const [input, setInput] = useState('');
  const tags = Array.isArray(value) ? value : [];

  const add = () => {
    const v = input.trim();
    if (v && !tags.includes(v)) onChange([...tags, v]);
    setInput('');
  };

  return (
    <div style={{
      border: `1px solid ${highlight ? 'rgba(34,197,94,0.35)' : 'rgba(255,255,255,0.1)'}`,
      background: highlight ? 'rgba(34,197,94,0.06)' : 'rgba(255,255,255,0.05)',
      borderRadius: '10px', padding: '8px 10px',
      transition: 'border-color 0.3s, background 0.3s',
    }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: tags.length ? '8px' : 0 }}>
        {tags.map((t, i) => (
          <span key={i} style={{
            background: 'rgba(109,40,217,0.35)', border: '1px solid rgba(124,58,237,0.4)',
            borderRadius: '20px', padding: '3px 10px', fontSize: '0.8rem', color: '#c4b5fd',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            {t}
            <span onClick={() => onChange(tags.filter((_, j) => j !== i))} style={{ cursor: 'pointer', opacity: 0.6 }}>×</span>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
          placeholder={placeholder || 'Escribir y Enter…'}
          style={{ flex: 1, background: 'transparent', border: 'none', color: '#e9d5ff', fontSize: '0.85rem', outline: 'none' }}
        />
        <button onClick={add} style={{
          background: 'rgba(109,40,217,0.4)', border: '1px solid rgba(124,58,237,0.5)',
          color: '#a78bfa', borderRadius: '8px', padding: '0 12px', cursor: 'pointer', fontSize: '1.1rem',
        }}>+</button>
      </div>
    </div>
  );
}

// ── Country data ─────────────────────────────────────────────────────────────
const COUNTRIES = [
  // LatAm primero
  'Perú', 'Argentina', 'México', 'Colombia', 'Chile', 'Brasil', 'Uruguay',
  'Ecuador', 'Bolivia', 'Paraguay', 'Venezuela', 'Panamá', 'Costa Rica',
  'Guatemala', 'Honduras', 'El Salvador', 'Nicaragua', 'República Dominicana',
  'Cuba', 'Puerto Rico',
  // Resto del mundo
  'España', 'Estados Unidos', 'Canada', 'Reino Unido', 'Alemania', 'Francia',
  'Italia', 'Portugal', 'Países Bajos', 'Suiza', 'Suecia', 'Noruega',
  'Australia', 'Nueva Zelanda', 'India', 'Singapur', 'Japón', 'Israel',
  'Emiratos Árabes', 'Sudáfrica',
];

// ── Country selector component ────────────────────────────────────────────────
function CountrySelector({ value, onChange, highlight }) {
  const [search, setSearch] = useState('');
  const [open, setOpen]     = useState(false);
  const ref                 = useRef(null);
  const selected            = Array.isArray(value) ? value : [];

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = COUNTRIES.filter(c =>
    !selected.includes(c) && c.toLowerCase().includes(search.toLowerCase())
  );

  const add    = (c) => { onChange([...selected, c]); setSearch(''); };
  const remove = (c) => onChange(selected.filter(x => x !== c));

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {/* Selected chips */}
      {selected.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
          {selected.map(c => (
            <span key={c} style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              background: highlight ? 'rgba(34,197,94,0.15)' : 'rgba(109,40,217,0.3)',
              border: `1px solid ${highlight ? 'rgba(34,197,94,0.4)' : 'rgba(124,58,237,0.45)'}`,
              borderRadius: '20px', padding: '4px 12px',
              fontSize: '0.82rem', color: highlight ? '#86efac' : '#c4b5fd',
            }}>
              🌍 {c}
              <span
                onClick={() => remove(c)}
                style={{ cursor: 'pointer', opacity: 0.6, fontSize: '1rem', lineHeight: 1 }}
              >×</span>
            </span>
          ))}
        </div>
      )}

      {/* Search input */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          background: highlight ? 'rgba(34,197,94,0.06)' : 'rgba(255,255,255,0.05)',
          border: `1px solid ${highlight ? 'rgba(34,197,94,0.35)' : open ? 'rgba(124,58,237,0.5)' : 'rgba(255,255,255,0.1)'}`,
          borderRadius: '10px', padding: '8px 12px',
          transition: 'border-color 0.2s',
        }}
        onClick={() => setOpen(true)}
      >
        <input
          value={search}
          onChange={e => { setSearch(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder={selected.length ? 'Agregar otro país…' : 'Buscar y seleccionar países…'}
          style={{ flex: 1, background: 'transparent', border: 'none', color: '#e9d5ff', fontSize: '0.85rem', outline: 'none' }}
        />
        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.8rem' }}>▾</span>
      </div>

      {/* Dropdown */}
      {open && filtered.length > 0 && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, zIndex: 50,
          background: 'linear-gradient(180deg,#0f0a20,#0a0818)',
          border: '1px solid rgba(124,58,237,0.3)',
          borderRadius: '12px', overflow: 'hidden',
          boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
          maxHeight: '220px', overflowY: 'auto',
        }}>
          {filtered.map(c => (
            <div
              key={c}
              onMouseDown={e => { e.preventDefault(); add(c); setOpen(false); }}
              style={{
                padding: '9px 14px', cursor: 'pointer', fontSize: '0.85rem',
                color: 'rgba(255,255,255,0.7)', transition: 'background 0.1s',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(109,40,217,0.25)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              🌍 {c}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const CURRENCIES = ['PEN', 'USD', 'EUR', 'GBP', 'ARS', 'CLP', 'MXN', 'BRL', 'COP', 'CRC'];

// Mirror of backend _ROLE_ES
const ROLE_ES = {
  'frontend developer': 'desarrollador frontend',
  'front end developer': 'desarrollador frontend',
  'backend developer': 'desarrollador backend',
  'full stack developer': 'desarrollador full stack',
  'fullstack developer': 'desarrollador full stack',
  'software engineer': 'ingeniero de software',
  'software developer': 'desarrollador de software',
  'web developer': 'desarrollador web',
  'react developer': 'desarrollador react',
  'python developer': 'desarrollador python',
  'data scientist': 'cientifico de datos',
  'data engineer': 'ingeniero de datos',
  'devops engineer': 'ingeniero devops',
  'mobile developer': 'desarrollador movil',
  'tech lead': 'lider tecnico',
  'engineering manager': 'gerente de ingenieria',
};

function expandRoles(roles) {
  const seen = {};
  for (const role of roles) {
    seen[role] = true;
    const low = role.toLowerCase();
    for (const [en, es] of Object.entries(ROLE_ES)) {
      if (low.includes(en)) { seen[es] = true; break; }
    }
  }
  return Object.keys(seen).slice(0, 8);
}

// Mirror of backend _COUNTRY_SCRAPERS
const COUNTRY_SCRAPERS = {
  'Perú':       ['Computrabajo Perú', 'Bumeran Perú', 'Aptitus'],
  'México':     ['Computrabajo México'],
  'Argentina':  ['Computrabajo Argentina', 'Bumeran Argentina'],
  'Colombia':   ['Computrabajo Colombia', 'Bumeran Colombia'],
  'Chile':      ['Computrabajo Chile', 'Bumeran Chile'],
  'Ecuador':    ['Computrabajo Ecuador'],
  'Bolivia':    ['Computrabajo Bolivia'],
  'Venezuela':  ['Computrabajo Venezuela'],
  'Panamá':     ['Computrabajo Panamá'],
  'Costa Rica': ['Computrabajo Costa Rica'],
};
const LATAM_SET = new Set(['Perú','Argentina','México','Colombia','Chile','Brasil','Uruguay','Ecuador','Bolivia','Paraguay','Venezuela','Panamá','Costa Rica','Guatemala','Honduras']);
const LATAM_ATS = ['Rappi','Despegar','dLocal','Aleph','Crehana','Kavak','Konfío','Pomelo','Kushki','Frubana','Lemon Cash','Mercado Libre','Globant','NEORIS','Endava','Wizeline','Gorilla Logic','CI&T','10Pearls','Encora','Softtek','Bitso'];
const GLOBAL_ATS = ['Notion','Vercel','Retool','Weights & Biases','Replit','Hugging Face','Stripe','Scale AI','Cognizant','Slalom','Linear'];

function ScanPreview({ countries, roles }) {
  const rawRoles       = roles?.length ? roles.slice(0, 4) : [];
  const effectiveRoles = rawRoles.length ? expandRoles(rawRoles) : ['desarrollador', 'programador', 'software engineer'];

  const scraperPlatforms = [];
  for (const c of countries) {
    if (COUNTRY_SCRAPERS[c]) scraperPlatforms.push(...COUNTRY_SCRAPERS[c]);
  }

  const totalSearches = scraperPlatforms.length * effectiveRoles.length;
  const hasLatam      = countries.some(c => LATAM_SET.has(c));

  // LATAM ATS companies shown when: LatAm country selected (secondary source) OR no countries (free-for-all)
  const latamAtsShown  = countries.length === 0 || hasLatam;
  const globalAtsShown = countries.length === 0;

  const atsCompanies = [
    ...(latamAtsShown  ? LATAM_ATS  : []),
    ...(globalAtsShown ? GLOBAL_ATS : []),
  ];

  if (countries.length === 0) {
    return (
      <div style={{ marginTop: '10px', padding: '12px 16px', background: 'rgba(255,255,255,0.03)', border: '1px dashed rgba(255,255,255,0.1)', borderRadius: '10px' }}>
        <p style={{ margin: 0, fontSize: '0.78rem', color: 'rgba(255,255,255,0.3)' }}>
          Sin países configurados el escáner revisa todas las empresas tech en modo libre ({atsCompanies.length} empresas). Selecciona un país para activar también las plataformas locales.
        </p>
      </div>
    );
  }

  return (
    <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {/* Local scrapers */}
      {scraperPlatforms.length > 0 ? (
        <div style={{ background: 'rgba(109,40,217,0.1)', border: '1px solid rgba(124,58,237,0.25)', borderRadius: '10px', padding: '12px 16px' }}>
          <p style={{ margin: '0 0 8px', fontSize: '0.72rem', fontWeight: 700, color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Plataformas locales — {totalSearches} búsquedas
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
            {scraperPlatforms.map(p => (
              <span key={p} style={{ background: 'rgba(109,40,217,0.3)', border: '1px solid rgba(124,58,237,0.4)', borderRadius: '99px', padding: '3px 10px', fontSize: '0.78rem', color: '#c4b5fd' }}>{p}</span>
            ))}
          </div>
          <p style={{ margin: '0 0 4px', fontSize: '0.7rem', fontWeight: 700, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Términos de búsqueda (ES + EN):</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {effectiveRoles.map(r => (
              <span key={r} style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', padding: '2px 8px', fontSize: '0.72rem', color: 'rgba(255,255,255,0.5)' }}>{r}</span>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ padding: '12px 16px', background: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.2)', borderRadius: '10px' }}>
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#fcd34d' }}>
            No hay plataformas locales para los países seleccionados. Disponible para: Perú, México, Argentina, Colombia, Chile, Ecuador, Bolivia, Venezuela, Panamá, Costa Rica.
          </p>
        </div>
      )}

      {/* LATAM ATS companies (secondary source) */}
      {atsCompanies.length > 0 && (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '10px', padding: '12px 16px' }}>
          <p style={{ margin: '0 0 6px', fontSize: '0.72rem', fontWeight: 700, color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Empresas LATAM tech ({atsCompanies.length}) — remoto/LATAM filtrado
          </p>
          <p style={{ margin: '0 0 8px', fontSize: '0.72rem', color: 'rgba(255,255,255,0.28)' }}>
            APIs directas (sin bloqueo). Solo se muestran ofertas remotas o LATAM open.
          </p>
          <p style={{ margin: 0, fontSize: '0.78rem', color: 'rgba(255,255,255,0.45)', lineHeight: 1.6 }}>
            {atsCompanies.slice(0, 10).join(', ')}{atsCompanies.length > 10 ? ` +${atsCompanies.length - 10} más` : ''}
          </p>
        </div>
      )}
    </div>
  );
}

const EMPTY_PROFILE = {
  full_name: '', email: '', phone: '', location: '', linkedin: '', portfolio_url: '', github: '',
  primary_roles: [], headline: '', exit_story: '', superpowers: [],
  target_range: '', target_min: 0, target_max: 0, salary_period: 'monthly',
  currency: 'PEN', minimum_salary: '', location_flexibility: '',
  country: '', city: '', timezone: '', visa_status: '',
  deal_breakers: [], must_haves: [],
  preferred_countries: [],
};

function isFieldFilled(val) {
  if (Array.isArray(val)) return val.length > 0;
  return typeof val === 'string' && val.trim() !== '';
}

function CVUploadZone({ onExtracted }) {
  const [dragOver, setDragOver] = useState(false);
  const [state, setState] = useState('idle'); // idle | loading | success | error
  const [result, setResult]   = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const inputRef = useRef();

  const process = async (file) => {
    if (!file) return;
    setState('loading');
    setResult(null);
    setErrorMsg('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const { data } = await api.post('/career-ops/config/extract-from-cv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult({ filled: data.fields_filled, profile: data.profile });
      setState('success');
      onExtracted(data.profile);
    } catch (e) {
      setErrorMsg(e.response?.data?.detail || 'Error al procesar el archivo.');
      setState('error');
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) process(file);
  };

  const onClick = () => inputRef.current?.click();

  return (
    <div style={{ marginBottom: '28px' }}>
      {/* Drop zone */}
      <div
        onClick={onClick}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        style={{
          border: `2px dashed ${dragOver ? '#7C3AED' : state === 'success' ? 'rgba(34,197,94,0.5)' : state === 'error' ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.12)'}`,
          borderRadius: '16px',
          padding: '32px',
          textAlign: 'center',
          cursor: state === 'loading' ? 'wait' : 'pointer',
          background: dragOver
            ? 'rgba(109,40,217,0.08)'
            : state === 'success' ? 'rgba(34,197,94,0.05)' : 'rgba(255,255,255,0.02)',
          transition: 'all 0.2s ease',
          position: 'relative',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt,.md"
          style={{ display: 'none' }}
          onChange={e => process(e.target.files[0])}
        />

        {state === 'loading' ? (
          <>
            <div style={{
              width: '40px', height: '40px', margin: '0 auto 12px',
              borderRadius: '50%', border: '3px solid rgba(167,139,250,0.2)',
              borderTopColor: '#a78bfa', animation: 'spin 0.8s linear infinite',
            }} />
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.5)', fontSize: '0.9rem' }}>
              Analizando con IA…
            </p>
            <p style={{ margin: '4px 0 0', color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem' }}>
              GPT-4o mini está leyendo tu CV
            </p>
          </>
        ) : state === 'success' ? (
          <>
            <div style={{ fontSize: '2rem', marginBottom: '8px' }}>✓</div>
            <p style={{ margin: 0, fontWeight: 700, color: '#86efac', fontSize: '0.95rem' }}>
              {result?.filled} campos completados automáticamente
            </p>
            <p style={{ margin: '6px 0 0', color: 'rgba(255,255,255,0.3)', fontSize: '0.75rem' }}>
              Revisa y ajusta la información abajo · Haz clic para subir otro archivo
            </p>
          </>
        ) : (
          <>
            <div style={{
              width: '44px', height: '44px', margin: '0 auto 14px',
              borderRadius: '12px', background: 'rgba(109,40,217,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem',
            }}>📄</div>
            <p style={{ margin: '0 0 4px', fontWeight: 700, color: 'rgba(255,255,255,0.7)', fontSize: '0.95rem' }}>
              Sube tu CV para autocompletar el perfil
            </p>
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.3)', fontSize: '0.78rem' }}>
              Arrastra aquí o haz clic · PDF, DOCX, TXT · máx. 10 MB
            </p>
          </>
        )}
      </div>

      {state === 'error' && (
        <div style={{
          marginTop: '10px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: '10px', padding: '10px 14px', color: '#fca5a5', fontSize: '0.82rem',
        }}>
          {errorMsg}
        </div>
      )}
    </div>
  );
}

export default function CareerOpsConfig() {
  const [form, setForm] = useState(EMPTY_PROFILE);
  const [highlighted, setHighlighted] = useState(new Set());
  const [saveStatus, setSaveStatus] = useState('idle');

  useEffect(() => {
    api.get('/career-ops/config').then(r => {
      if (r.data.config) {
        const { _id, user_email, ...rest } = r.data.config;
        setForm({ ...EMPTY_PROFILE, ...rest });
      }
    }).catch(() => {});
  }, []);

  const set = (key, val) => {
    setForm(f => ({ ...f, [key]: val }));
    setHighlighted(h => { const n = new Set(h); n.delete(key); return n; });
  };

  const onExtracted = (extracted) => {
    const newHighlighted = new Set();
    setForm(prev => {
      const merged = { ...prev };
      for (const [k, v] of Object.entries(extracted)) {
        if (k in EMPTY_PROFILE && isFieldFilled(v)) {
          merged[k] = v;
          newHighlighted.add(k);
        }
      }
      return merged;
    });
    setHighlighted(newHighlighted);
    // Clear highlight after 8 seconds
    setTimeout(() => setHighlighted(new Set()), 8000);
  };

  const save = async () => {
    setSaveStatus('saving');
    try {
      await api.post('/career-ops/config', form);
      setSaveStatus('saved');
      setHighlighted(new Set());
      setTimeout(() => setSaveStatus('idle'), 2500);
    } catch {
      setSaveStatus('error');
    }
  };

  const hl = (key) => highlighted.has(key);
  const inp = (key, rest = {}) => (
    <input
      style={mkInputStyle(hl(key))}
      value={form[key] || ''}
      onChange={e => set(key, e.target.value)}
      {...rest}
    />
  );

  return (
    <div style={{ padding: '32px', maxWidth: '860px', margin: '0 auto' }}>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(90deg, #a78bfa, #c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Career Ops — Configuración
        </h1>
        <p style={{ margin: '8px 0 0', color: 'rgba(255,255,255,0.4)', fontSize: '0.88rem' }}>
          Define tu perfil para que la IA evalúe las ofertas en función de tus objetivos.
        </p>
      </div>

      <CVUploadZone onExtracted={onExtracted} />

      <SECTION title="Datos de candidato">
        <ROW>
          <Field label="Nombre completo" highlight={hl('full_name')}>{inp('full_name')}</Field>
          <Field label="Email" highlight={hl('email')}>{inp('email')}</Field>
        </ROW>
        <ROW>
          <Field label="Teléfono" highlight={hl('phone')}>{inp('phone')}</Field>
          <Field label="Ubicación actual" highlight={hl('location')}>{inp('location', { placeholder: 'Ciudad, País' })}</Field>
        </ROW>
        <ROW>
          <Field label="LinkedIn URL" highlight={hl('linkedin')}>{inp('linkedin')}</Field>
          <Field label="Portfolio / Web" highlight={hl('portfolio_url')}>{inp('portfolio_url')}</Field>
        </ROW>
        <Field label="GitHub" highlight={hl('github')}>{inp('github')}</Field>
      </SECTION>

      <SECTION title="Roles objetivo">
        <Field label="Roles primarios" highlight={hl('primary_roles')}>
          <TagInput value={form.primary_roles} onChange={v => set('primary_roles', v)} placeholder="Ej: Head of AI, Senior Engineer…" highlight={hl('primary_roles')} />
        </Field>
        <Field label="Must-haves (requisitos innegociables)" highlight={hl('must_haves')}>
          <TagInput value={form.must_haves} onChange={v => set('must_haves', v)} placeholder="Ej: Remote, AI-focused…" highlight={hl('must_haves')} />
        </Field>
        <Field label="Deal-breakers (razones para descartar)" highlight={hl('deal_breakers')}>
          <TagInput value={form.deal_breakers} onChange={v => set('deal_breakers', v)} placeholder="Ej: Sin equity, sin remote…" highlight={hl('deal_breakers')} />
        </Field>
      </SECTION>

      <SECTION title="Búsqueda de ofertas">
        <Field label="Países donde buscar" highlight={hl('preferred_countries')}>
          <CountrySelector
            value={form.preferred_countries}
            onChange={v => set('preferred_countries', v)}
            highlight={hl('preferred_countries')}
          />
        </Field>
        <ScanPreview countries={form.preferred_countries || []} roles={form.primary_roles || []} />
        <p style={{ margin: '12px 0 0', fontSize: '0.72rem', color: 'rgba(255,255,255,0.28)', lineHeight: 1.6 }}>
          Con países LatAm seleccionados el escáner combina <strong style={{ color: 'rgba(255,255,255,0.5)' }}>plataformas locales</strong> (Computrabajo, Bumeran…) más{' '}
          <strong style={{ color: 'rgba(255,255,255,0.5)' }}>empresas LATAM tech</strong> (Rappi, Mercado Libre, Globant…) filtrando solo ofertas remotas o abiertas a LATAM.
          Los resultados de EE.UU./Europa quedan excluidos.
        </p>
      </SECTION>

      <SECTION title="Narrativa profesional">
        <Field label="Headline (una línea)" highlight={hl('headline')}>
          {inp('headline', { placeholder: 'Ej: AI engineer especializado en agentes y LLMs con 8 años de experiencia' })}
        </Field>
        <Field label="Propuesta de valor / Exit story" highlight={hl('exit_story')}>
          <textarea
            style={{ ...mkInputStyle(hl('exit_story')), minHeight: '90px', resize: 'vertical', fontFamily: 'inherit' }}
            placeholder="¿Qué valor único aportas? ¿Por qué ahora?"
            value={form.exit_story || ''}
            onChange={e => set('exit_story', e.target.value)}
          />
        </Field>
        <Field label="Superpoderes / fortalezas clave" highlight={hl('superpowers')}>
          <TagInput value={form.superpowers} onChange={v => set('superpowers', v)} placeholder="Ej: LLM fine-tuning, System design…" highlight={hl('superpowers')} />
        </Field>
      </SECTION>

      <SECTION title="Compensación">
        {/* Period + currency row */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', marginBottom: '16px', flexWrap: 'wrap' }}>
          <Field label="Período" style={{ margin: 0 }}>
            <div style={{ display: 'flex', borderRadius: '10px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)' }}>
              {['monthly', 'annual'].map(p => (
                <button
                  key={p}
                  type="button"
                  onClick={() => set('salary_period', p)}
                  style={{
                    flex: 1, padding: '10px 18px', border: 'none', cursor: 'pointer',
                    fontSize: '0.85rem', fontWeight: 700, transition: 'all 0.15s',
                    background: form.salary_period === p ? 'rgba(109,40,217,0.55)' : 'rgba(255,255,255,0.04)',
                    color: form.salary_period === p ? '#c4b5fd' : 'rgba(255,255,255,0.4)',
                  }}
                >
                  {p === 'monthly' ? 'Mensual' : 'Anual'}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Moneda" highlight={hl('currency')} style={{ margin: 0 }}>
            <select style={{ ...mkInputStyle(hl('currency')), width: '110px' }} value={form.currency || 'PEN'} onChange={e => set('currency', e.target.value)}>
              {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
        </div>

        {/* Salary range */}
        <Field label={`Rango objetivo (${form.salary_period === 'monthly' ? 'mensual' : 'anual'}) — ${form.currency || 'PEN'}`}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '10px', alignItems: 'center' }}>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', fontSize: '0.8rem', color: 'rgba(255,255,255,0.35)', pointerEvents: 'none' }}>
                {form.currency || 'PEN'}
              </span>
              <input
                type="number"
                min="0"
                value={form.target_min || ''}
                onChange={e => set('target_min', Number(e.target.value) || 0)}
                placeholder="Mínimo"
                style={{ ...mkInputStyle(false), paddingLeft: form.currency?.length > 2 ? '52px' : '44px' }}
              />
            </div>
            <span style={{ color: 'rgba(255,255,255,0.3)', fontWeight: 700, fontSize: '1.1rem', textAlign: 'center' }}>—</span>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', fontSize: '0.8rem', color: 'rgba(255,255,255,0.35)', pointerEvents: 'none' }}>
                {form.currency || 'PEN'}
              </span>
              <input
                type="number"
                min="0"
                value={form.target_max || ''}
                onChange={e => set('target_max', Number(e.target.value) || 0)}
                placeholder="Máximo"
                style={{ ...mkInputStyle(false), paddingLeft: form.currency?.length > 2 ? '52px' : '44px' }}
              />
            </div>
          </div>
          {/* Live preview */}
          {(form.target_min > 0 || form.target_max > 0) && (
            <p style={{ margin: '8px 0 0', fontSize: '0.78rem', color: '#a78bfa' }}>
              Objetivo: {form.currency} {(form.target_min || 0).toLocaleString()}
              {form.target_max > 0 ? ` – ${form.currency} ${form.target_max.toLocaleString()}` : '+'}{' '}
              / {form.salary_period === 'monthly' ? 'mes' : 'año'}
            </p>
          )}
        </Field>

        <Field label="Flexibilidad de ubicación" highlight={hl('location_flexibility')}>
          {inp('location_flexibility', { placeholder: 'Ej: Full remote, híbrido Lima, presencial CDMX' })}
        </Field>
      </SECTION>

      <SECTION title="Ubicación y visa">
        <ROW>
          <Field label="País de residencia" highlight={hl('country')}>{inp('country')}</Field>
          <Field label="Ciudad" highlight={hl('city')}>{inp('city')}</Field>
        </ROW>
        <ROW>
          <Field label="Zona horaria" highlight={hl('timezone')}>
            {inp('timezone', { placeholder: 'Ej: UTC-3, CET' })}
          </Field>
          <Field label="Estado de visa / autorización" highlight={hl('visa_status')}>
            {inp('visa_status', { placeholder: 'Ej: Ciudadano EU, Visa H1B activa' })}
          </Field>
        </ROW>

      </SECTION>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', alignItems: 'center' }}>
        {highlighted.size > 0 && (
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#86efac' }}>
            {highlighted.size} campo{highlighted.size !== 1 ? 's' : ''} completado{highlighted.size !== 1 ? 's' : ''} por IA — revisa antes de guardar
          </p>
        )}
        <button
          onClick={save}
          disabled={saveStatus === 'saving'}
          style={{
            background: saveStatus === 'saved'
              ? 'rgba(34,197,94,0.25)'
              : 'linear-gradient(135deg, #6D28D9, #4C1D95)',
            border: saveStatus === 'saved' ? '1px solid rgba(34,197,94,0.4)' : 'none',
            color: saveStatus === 'saved' ? '#86efac' : '#e9d5ff',
            borderRadius: '12px', padding: '12px 32px',
            fontSize: '0.9rem', fontWeight: 700,
            cursor: saveStatus === 'saving' ? 'not-allowed' : 'pointer',
            boxShadow: saveStatus === 'saved' ? 'none' : '0 4px 20px rgba(109,40,217,0.4)',
            transition: 'all 0.2s',
          }}
        >
          {saveStatus === 'saving' ? 'Guardando…' : saveStatus === 'saved' ? '✓ Guardado' : 'Guardar perfil'}
        </button>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
