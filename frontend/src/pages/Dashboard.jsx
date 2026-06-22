import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Spinner from '../components/Spinner';
import {
  Search, MapPin, Globe, Mail, Loader2,
  Phone, MessageCircle, ChevronDown, ChevronUp, Shield, ShieldOff,
  Zap, BarChart2, Lightbulb, Send, BookOpen, Users, ExternalLink,
  BadgeCheck, History, Trash2, Plus, Clock, ChevronLeft, ChevronRight,
  X,
} from 'lucide-react';
import api from '../api';

// ── Utilities ──────────────────────────────────────────────────────────────

const scoreColor = s => !s && s !== 0 ? '#6b7280' : s >= 70 ? '#22c55e' : s >= 40 ? '#eab308' : '#ef4444';
const impactColor = l => ({ alto: '#22c55e', medio: '#eab308' }[(l||'').toLowerCase()] || '#94a3b8');

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'ahora';
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d`;
  return new Date(iso).toLocaleDateString('es-PE', { day: '2-digit', month: 'short' });
}

// ── Detail Panel ───────────────────────────────────────────────────────────

function DetailPanel({ data }) {
  const socials = Object.entries(data.social || {}).filter(([, v]) => v);
  return (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', marginTop: '18px', paddingTop: '18px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {typeof data.digital_presence_score === 'number' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BarChart2 size={14} style={{ color: 'var(--primary-glow)', flexShrink: 0 }} />
          <div style={{ flex: 1, height: '5px', background: 'rgba(255,255,255,0.1)', borderRadius: '99px', overflow: 'hidden' }}>
            <div style={{ width: `${data.digital_presence_score}%`, height: '100%', background: scoreColor(data.digital_presence_score), borderRadius: '99px' }} />
          </div>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: scoreColor(data.digital_presence_score), minWidth: 32 }}>{data.digital_presence_score}</span>
        </div>
      )}

      {data.digital_presence_summary && (
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.6, background: 'rgba(255,255,255,0.04)', padding: '10px 12px', borderRadius: '8px' }}>
          {data.digital_presence_summary}
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
        {(data.emails || []).map((e, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Mail size={13} style={{ color: 'var(--primary-glow)', flexShrink: 0 }} />
            <a href={`mailto:${e}`} style={{ fontSize: '0.82rem', color: 'var(--text-main)', textDecoration: 'none' }}>{e}</a>
          </div>
        ))}
        {(data.phones || []).map((p, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Phone size={13} style={{ color: 'var(--primary-glow)', flexShrink: 0 }} />
            <a href={`tel:${p}`} style={{ fontSize: '0.82rem', color: 'var(--text-main)', textDecoration: 'none' }}>{p}</a>
          </div>
        ))}
        {data.whatsapp && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageCircle size={13} style={{ color: '#25D366', flexShrink: 0 }} />
            <a href={data.whatsapp} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.82rem', color: '#25D366', textDecoration: 'none' }}>WhatsApp</a>
          </div>
        )}
        {data.maps_link && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MapPin size={13} style={{ color: 'var(--primary-glow)', flexShrink: 0 }} />
            <a href={data.maps_link} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.82rem', color: 'var(--accent)', textDecoration: 'none' }}>Ver en Google Maps</a>
          </div>
        )}
      </div>

      {socials.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {socials.map(([key, url]) => (
            <a key={key} href={url} target="_blank" rel="noopener noreferrer"
              style={{ padding: '3px 10px', borderRadius: '999px', background: 'rgba(255,255,255,0.07)', color: 'var(--accent)', fontSize: '0.7rem', textDecoration: 'none' }}>
              {key.charAt(0).toUpperCase() + key.slice(1)}
            </a>
          ))}
        </div>
      )}

      {(data.tech_stack || []).length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Zap size={11} /> Stack detectado
          </p>
          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
            {data.tech_stack.map((t, i) => (
              <span key={i} style={{ fontSize: '0.68rem', background: 'rgba(109,40,217,0.2)', color: '#a78bfa', padding: '2px 8px', borderRadius: '5px' }}>{t}</span>
            ))}
            <span style={{ fontSize: '0.68rem', display: 'inline-flex', alignItems: 'center', gap: '3px', padding: '2px 8px', borderRadius: '5px', background: data.has_ssl ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)', color: data.has_ssl ? '#4ade80' : '#f87171' }}>
              {data.has_ssl ? <Shield size={9} /> : <ShieldOff size={9} />}{data.has_ssl ? 'HTTPS' : 'Sin SSL'}
            </span>
          </div>
        </div>
      )}

      {(data.people || []).length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Users size={11} /> Personas identificadas
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {data.people.map((p, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', padding: '8px 12px' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--primary), var(--secondary))', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '0.8rem', fontWeight: 700 }}>
                  {(p.name || '?').charAt(0).toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>{p.name}</span>
                    {p.confidence === 'high' && <BadgeCheck size={11} style={{ color: '#22c55e' }} />}
                  </div>
                  {p.title && <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0 }}>{p.title}</p>}
                  {p.email_hint && <a href={`mailto:${p.email_hint}`} style={{ fontSize: '0.7rem', color: 'var(--accent)', textDecoration: 'none' }}>{p.email_hint}</a>}
                </div>
                {p.linkedin_url && (
                  <a href={p.linkedin_url} target="_blank" rel="noopener noreferrer"
                    style={{ padding: '3px 8px', borderRadius: '5px', background: 'rgba(10,102,194,0.2)', color: '#60a5fa', fontSize: '0.68rem', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <ExternalLink size={9} /> LinkedIn
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {(data.tech_recommendations || []).length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Lightbulb size={11} /> Servicios tech recomendados
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {data.tech_recommendations.map((rec, i) => (
              <div key={i} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '8px', padding: '9px 12px', borderLeft: `3px solid ${impactColor(rec.impact)}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3px' }}>
                  <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>{rec.title}</span>
                  <span style={{ fontSize: '0.62rem', color: impactColor(rec.impact), background: `${impactColor(rec.impact)}22`, padding: '1px 7px', borderRadius: '999px' }}>
                    {rec.impact}
                  </span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>{rec.why}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.pitch_summary && (
        <div style={{ background: 'linear-gradient(135deg,rgba(109,40,217,0.15),rgba(76,29,149,0.2))', borderRadius: '10px', padding: '14px', border: '1px solid rgba(109,40,217,0.3)' }}>
          <p style={{ fontSize: '0.7rem', color: 'var(--accent)', marginBottom: '7px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Send size={10} /> Apertura sugerida por IA
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-main)', lineHeight: 1.7, fontStyle: 'italic', margin: 0 }}>{data.pitch_summary}</p>
        </div>
      )}
    </div>
  );
}

// ── Client Card ────────────────────────────────────────────────────────────

function ClientCard({ client, searchPrompt, sessionId, preloadedDetail }) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(preloadedDetail || null);
  const [error, setError] = useState(null);

  const domain = (() => {
    try { return new URL(client.website).hostname.replace('www.', ''); } catch { return client.website || ''; }
  })();

  const handleAnalyze = async () => {
    if (detail) { setExpanded(v => !v); return; }
    setExpanded(true);
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/agent/analyze', {
        name: client.name,
        website: client.website || '',
        location: client.location || '',
        description: client.description || '',
        search_prompt: searchPrompt,
        session_id: sessionId || '',
      });
      setDetail(res.data.result);
    } catch (err) {
      setError('Error al analizar. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass" style={{ padding: '20px', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '10px', marginBottom: '10px' }}>
        <div style={{ minWidth: 0 }}>
          <h3 style={{ fontSize: '0.95rem', lineHeight: 1.4, marginBottom: '2px' }}>{client.name}</h3>
          {domain && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{domain}</span>}
        </div>
        {(detail || preloadedDetail) && (
          <span style={{ fontSize: '0.62rem', background: 'rgba(34,197,94,0.15)', color: '#4ade80', padding: '2px 8px', borderRadius: '999px', whiteSpace: 'nowrap', flexShrink: 0 }}>Analizado</span>
        )}
      </div>

      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '5px', flexGrow: 1 }}>
        {client.location && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <MapPin size={12} style={{ color: 'var(--primary-glow)', flexShrink: 0 }} />
            <span>{client.location}</span>
          </div>
        )}
        {client.description && <p style={{ lineHeight: 1.5, marginTop: '4px' }}>{client.description}</p>}
      </div>

      {expanded && loading && (
        <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'center', padding: '16px 0' }}>
          <Loader2 size={20} style={{ color: 'var(--primary)', animation: 'spin 1.2s linear infinite' }} />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Analizando…</span>
        </div>
      )}
      {expanded && !loading && error && (
        <p style={{ marginTop: '12px', fontSize: '0.8rem', color: '#f87171' }}>{error}</p>
      )}
      {expanded && !loading && detail && <DetailPanel data={detail} />}

      <div style={{ display: 'flex', gap: '7px', marginTop: '16px' }}>
        {client.website && (
          <a href={client.website} target="_blank" rel="noopener noreferrer"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', padding: '9px 14px', borderRadius: '9px', background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.78rem' }}>
            <Globe size={13} />
          </a>
        )}
        <button onClick={handleAnalyze}
          style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '9px', borderRadius: '9px', background: 'var(--primary)', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600 }}>
          {loading
            ? <Loader2 size={13} style={{ animation: 'spin 1.2s linear infinite' }} />
            : detail ? (expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />) : <BookOpen size={13} />}
          {loading ? 'Analizando…' : detail ? (expanded ? 'Ocultar' : 'Ver análisis') : 'Analizar empresa'}
        </button>
      </div>
    </div>
  );
}

// ── History Sidebar ────────────────────────────────────────────────────────

function HistorySidebar({ open, onToggle, activeSessionId, onSelectSession, onNewSearch }) {
  const [sessions, setSessions] = useState([]);
  const [total, setTotal] = useState(0);
  const [searchText, setSearchText] = useState('');
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const debounceRef = useRef(null);

  const fetchSessions = useCallback(async (q = '', p = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: p, limit: 20 });
      if (q) params.set('q', q);
      const res = await api.get(`/agent/sessions?${params}`);
      setSessions(res.data.sessions || []);
      setTotal(res.data.total || 0);
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const handleSearchChange = (val) => {
    setSearchText(val);
    setPage(1);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSessions(val, 1), 400);
  };

  const handleDelete = async (e, sid) => {
    e.stopPropagation();
    try {
      await api.delete(`/agent/sessions/${sid}`);
      setSessions(s => s.filter(x => x._id !== sid));
      setTotal(t => t - 1);
      if (activeSessionId === sid) onNewSearch();
    } catch { /* silent */ }
  };

  const sidebarW = open ? 280 : 60;

  return (
    <div style={{
      width: sidebarW, minWidth: sidebarW, height: '100vh', position: 'sticky', top: 0,
      background: 'rgba(15,15,25,0.95)', backdropFilter: 'blur(20px)',
      borderRight: '1px solid rgba(255,255,255,0.07)',
      display: 'flex', flexDirection: 'column', transition: 'width 0.25s ease', overflow: 'hidden',
      flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{ padding: open ? '20px 16px 12px' : '20px 12px 12px', display: 'flex', alignItems: 'center', justifyContent: open ? 'space-between' : 'center', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        {open && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={16} style={{ color: 'var(--primary-glow)' }} />
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Historial</span>
            {total > 0 && <span style={{ fontSize: '0.65rem', background: 'rgba(109,40,217,0.3)', color: '#a78bfa', padding: '1px 7px', borderRadius: '999px' }}>{total}</span>}
          </div>
        )}
        <button onClick={onToggle} style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px', borderRadius: '8px', display: 'flex' }}>
          {open ? <ChevronLeft size={16} /> : <History size={16} />}
        </button>
      </div>

      {open && (
        <>
          {/* New search button */}
          <div style={{ padding: '12px 14px 8px' }}>
            <button onClick={onNewSearch}
              style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '9px 12px', borderRadius: '10px', background: 'var(--primary)', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600, justifyContent: 'center' }}>
              <Plus size={14} /> Nueva búsqueda
            </button>
          </div>

          {/* Search bar */}
          <div style={{ padding: '0 14px 8px' }}>
            <div style={{ position: 'relative' }}>
              <Search size={13} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Buscar en historial…"
                value={searchText}
                onChange={e => handleSearchChange(e.target.value)}
                style={{ width: '100%', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '7px 10px 7px 30px', color: 'var(--text-main)', fontSize: '0.78rem', outline: 'none', boxSizing: 'border-box' }}
              />
              {searchText && (
                <button onClick={() => handleSearchChange('')} style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0, display: 'flex' }}>
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Sessions list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '0 10px' }}>
            {loading && (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '20px' }}>
                <Loader2 size={18} style={{ color: 'var(--primary)', animation: 'spin 1.2s linear infinite' }} />
              </div>
            )}
            {!loading && sessions.length === 0 && (
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', padding: '20px 10px' }}>
                {searchText ? 'Sin resultados' : 'Sin búsquedas aún'}
              </p>
            )}
            {sessions.map(s => (
              <div key={s._id}
                onClick={() => onSelectSession(s._id)}
                style={{
                  padding: '10px 12px', borderRadius: '10px', marginBottom: '4px', cursor: 'pointer',
                  background: activeSessionId === s._id ? 'rgba(109,40,217,0.2)' : 'rgba(255,255,255,0.03)',
                  border: activeSessionId === s._id ? '1px solid rgba(109,40,217,0.4)' : '1px solid transparent',
                  transition: 'all 0.15s',
                  position: 'relative',
                }}
                onMouseEnter={e => { if (activeSessionId !== s._id) e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
                onMouseLeave={e => { if (activeSessionId !== s._id) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '6px' }}>
                  <p style={{ fontSize: '0.78rem', lineHeight: 1.4, margin: 0, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                    {s.prompt}
                  </p>
                  <button
                    onClick={e => handleDelete(e, s._id)}
                    style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.2)', cursor: 'pointer', padding: '2px', flexShrink: 0, display: 'flex', borderRadius: '4px' }}
                    onMouseEnter={e => e.currentTarget.style.color = '#f87171'}
                    onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.2)'}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '5px' }}>
                  <Clock size={10} style={{ color: 'var(--text-muted)' }} />
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{timeAgo(s.created_at)}</span>
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{s.result_count} resultados</span>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {total > 20 && (
            <div style={{ padding: '10px 14px', borderTop: '1px solid rgba(255,255,255,0.07)', display: 'flex', justifyContent: 'center', gap: '8px' }}>
              <button disabled={page === 1} onClick={() => { const p = page - 1; setPage(p); fetchSessions(searchText, p); }}
                style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: page === 1 ? 'var(--text-muted)' : '#fff', cursor: page === 1 ? 'not-allowed' : 'pointer', padding: '4px 8px', borderRadius: '6px' }}>
                <ChevronLeft size={14} />
              </button>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', alignSelf: 'center' }}>{page} / {Math.ceil(total / 20)}</span>
              <button disabled={page >= Math.ceil(total / 20)} onClick={() => { const p = page + 1; setPage(p); fetchSessions(searchText, p); }}
                style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: page >= Math.ceil(total / 20) ? 'var(--text-muted)' : '#fff', cursor: page >= Math.ceil(total / 20) ? 'not-allowed' : 'pointer', padding: '4px 8px', borderRadius: '6px' }}>
                <ChevronRight size={14} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Search state
  const [prompt, setPrompt] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [sessionId, setSessionId] = useState('');
  const [lastPrompt, setLastPrompt] = useState('');

  // History state
  const [activeSessionId, setActiveSessionId] = useState('');
  const [loadingSession, setLoadingSession] = useState(false);
  const [preloadedAnalyses, setPreloadedAnalyses] = useState({}); // website → analysis

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setIsSearching(true);
    setResults([]);
    setSessionId('');
    setActiveSessionId('');
    setPreloadedAnalyses({});
    setLastPrompt(prompt.trim());
    try {
      const res = await api.post('/agent/search', { prompt: prompt.trim() });
      setResults(res.data.results || []);
      setSessionId(res.data.session_id || '');
      setActiveSessionId(res.data.session_id || '');
    } catch (err) {
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectSession = async (sid) => {
    if (sid === activeSessionId) return;
    setLoadingSession(true);
    setResults([]);
    setPreloadedAnalyses({});
    setActiveSessionId(sid);
    setSessionId(sid);
    try {
      const res = await api.get(`/agent/sessions/${sid}`);
      const session = res.data.session || {};
      const analyzed = res.data.analyzed_clients || [];

      setResults(session.results || []);
      setLastPrompt(session.prompt || '');
      setPrompt(session.prompt || '');

      // Map analyzed clients by website for fast lookup
      const map = {};
      analyzed.forEach(c => {
        if (c.website) map[c.website] = c;
        if (c.name) map[c.name] = c;
      });
      setPreloadedAnalyses(map);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSession(false);
    }
  };

  const handleNewSearch = () => {
    setActiveSessionId('');
    setSessionId('');
    setResults([]);
    setLastPrompt('');
    setPrompt('');
    setPreloadedAnalyses({});
  };

  const getPreloaded = (client) => {
    return preloadedAnalyses[client.website] || preloadedAnalyses[client.name] || null;
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes pulse-glow { 0%,100%{opacity:.5;transform:scale(1)} 50%{opacity:1;transform:scale(1.1)} }
      `}</style>

      {/* Sidebar */}
      <HistorySidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(v => !v)}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSearch={handleNewSearch}
      />

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh', overflow: 'auto' }}>

        <main style={{ flex: 1, padding: '28px', maxWidth: '1100px', width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>

          {/* Search hero */}
          <section className="glass" style={{ padding: '36px 40px', textAlign: 'center', marginBottom: '32px' }}>
            <h1 style={{ fontSize: '2rem', marginBottom: '10px' }}>
              Encuentra tu <span className="gradient-text">Cliente Ideal</span>
            </h1>
            <p style={{ color: 'var(--text-muted)', marginBottom: '28px', maxWidth: '560px', margin: '0 auto 28px', fontSize: '0.9rem' }}>
              Describe el tipo de empresa. El agente busca en la web, extrae contactos reales y analiza qué servicios tech ofrecerles.
            </p>
            <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px', maxWidth: '680px', margin: '0 auto' }}>
              <input
                type="text"
                className="input-field"
                style={{ flex: 1, padding: '14px 20px', fontSize: '0.95rem', borderRadius: '12px' }}
                placeholder="Ej: Clínicas dentales en Lima sin presencia digital…"
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
              />
              <button type="submit" className="btn-primary" style={{ padding: '14px 28px', borderRadius: '12px', whiteSpace: 'nowrap' }} disabled={isSearching}>
                {isSearching
                  ? <Loader2 size={17} style={{ animation: 'spin 1.2s linear infinite' }} />
                  : <><Search size={16} /> Buscar</>}
              </button>
            </form>
          </section>

          {/* Loading session */}
          {loadingSession && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
              <Loader2 size={28} style={{ color: 'var(--primary)', animation: 'spin 1.2s linear infinite' }} />
            </div>
          )}

          {/* Searching */}
          {isSearching && (
            <div className="glass" style={{ padding: '36px', textAlign: 'center', maxWidth: '360px', margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <div style={{ position: 'relative' }}>
                <div style={{ position: 'absolute', inset: -10, background: 'var(--primary-glow)', filter: 'blur(20px)', borderRadius: '50%', animation: 'pulse-glow 2s infinite ease-in-out' }} />
                <Spinner size={40} color="var(--accent)" />
              </div>
              <div>
                <h3 style={{ marginBottom: '6px', fontSize: '1rem' }}>Buscando empresas…</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                  Haz clic en <strong>"Analizar empresa"</strong> en cada resultado para ver contactos y recomendaciones.
                </p>
              </div>
            </div>
          )}

          {/* Results */}
          {!isSearching && !loadingSession && results.length > 0 && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
                    <strong style={{ color: 'var(--text-main)' }}>{results.length}</strong> empresas
                    {lastPrompt && <span style={{ color: 'var(--text-muted)' }}> para <em>"{lastPrompt}"</em></span>}
                  </p>
                  {activeSessionId && (
                    <span style={{ fontSize: '0.65rem', background: 'rgba(109,40,217,0.2)', color: '#a78bfa', padding: '2px 8px', borderRadius: '999px' }}>guardado</span>
                  )}
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                  Clic en <strong style={{ color: 'var(--accent)' }}>Analizar empresa</strong> para contactos + análisis tech
                </p>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
                {results.map(client => (
                  <ClientCard
                    key={client.id || client.name}
                    client={client}
                    searchPrompt={lastPrompt}
                    sessionId={sessionId}
                    preloadedDetail={getPreloaded(client)}
                  />
                ))}
              </div>
            </>
          )}

          {/* Empty state */}
          {!isSearching && !loadingSession && results.length === 0 && (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
              <History size={40} style={{ opacity: 0.3, marginBottom: '12px' }} />
              <p style={{ fontSize: '0.9rem' }}>Escribe una búsqueda o selecciona una del historial</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
