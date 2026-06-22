import { useState, useEffect, useCallback, useRef } from 'react';
import api from '../api';


const STATUS_STYLE = {
  idle:    { color: '#a78bfa', bg: 'rgba(167,139,250,0.1)',  dot: '#7C3AED', label: 'Inactivo'  },
  running: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',   dot: '#f59e0b', label: 'Escaneando' },
  error:   { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',    dot: '#ef4444', label: 'Error'      },
};

function StatusDot({ status }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.idle;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '8px',
      padding: '5px 14px', borderRadius: '99px',
      background: s.bg, border: `1px solid ${s.color}33`,
      fontSize: '0.82rem', fontWeight: 700, color: s.color,
    }}>
      <span style={{
        width: '8px', height: '8px', borderRadius: '50%', background: s.dot,
        boxShadow: status === 'running' ? `0 0 8px ${s.dot}` : 'none',
        animation: status === 'running' ? 'pulse 1.2s ease-in-out infinite' : 'none',
      }} />
      {s.label}
    </span>
  );
}

function StatCard({ value, label, color = '#a78bfa' }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '18px 20px' }}>
      <p style={{ margin: 0, fontSize: '1.8rem', fontWeight: 900, color }}>{value ?? '—'}</p>
      <p style={{ margin: '3px 0 0', fontSize: '0.75rem', color: 'rgba(255,255,255,0.35)', fontWeight: 600 }}>{label}</p>
    </div>
  );
}


const btn = (variant = 'primary') => ({
  padding: '10px 22px', borderRadius: '10px', fontWeight: 700,
  fontSize: '0.85rem', cursor: 'pointer', border: 'none', transition: 'all 0.18s',
  ...(variant === 'primary' && {
    background: 'linear-gradient(135deg, #6D28D9, #4C1D95)',
    color: '#e9d5ff', boxShadow: '0 3px 14px rgba(109,40,217,0.35)',
  }),
  ...(variant === 'stop' && {
    background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
    color: '#fca5a5',
  }),
  ...(variant === 'ghost' && {
    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
    color: 'rgba(255,255,255,0.6)',
  }),
});

const INTERVALS = [
  { value: 2,  label: 'Cada 2 horas' },
  { value: 4,  label: 'Cada 4 horas' },
  { value: 6,  label: 'Cada 6 horas' },
  { value: 12, label: 'Cada 12 horas' },
  { value: 24, label: 'Una vez al día' },
];

export default function CareerOpsScan() {
  const [state, setState]           = useState(null);
  const [portals, setPortals]       = useState([]);
  const [interval, setIntervalVal]  = useState(6);

  const [actionLoading, setAction]  = useState('');
  const [runningNow, setRunningNow] = useState(false);
  const pollRef = useRef(null);

  const loadState = useCallback(async () => {
    try {
      const { data } = await api.get('/career-ops/scan/state');
      setState(data.state);
      if (data.state?.interval_hours) setIntervalVal(data.state.interval_hours);
    } catch {}
  }, []);

  const loadPortals = useCallback(async () => {
    try {
      const { data } = await api.get('/career-ops/portals');
      setPortals(data.portals || []);
    } catch {}
  }, []);

  useEffect(() => {
    loadState();
    loadPortals();
  }, [loadState, loadPortals]);

  // Poll every 4s while running
  useEffect(() => {
    const isRunning = state?.status === 'running';
    if (isRunning && !pollRef.current) {
      pollRef.current = setInterval(loadState, 4000);
    } else if (!isRunning && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [state?.status, loadState]);

  const handleStart = async () => {
    setAction('start');
    try {
      await api.post('/career-ops/scan/start', { interval_hours: interval });
      await loadState();
    } catch {}
    setAction('');
  };

  const handleStop = async () => {
    setAction('stop');
    try {
      await api.post('/career-ops/scan/stop');
      await loadState();
    } catch {}
    setAction('');
  };

  const handleRunNow = async () => {
    setRunningNow(true);
    try {
      await api.post('/career-ops/scan/run-now');
      setTimeout(loadState, 1500);
    } catch {}
    setTimeout(() => setRunningNow(false), 2000);
  };

  const handleReset = async () => {
    setAction('reset');
    try {
      await api.post('/career-ops/scan/reset');
      await loadState();
    } catch {}
    setAction('');
  };


  const enabledCount = portals.filter(p => p.enabled).length;
  const isActive  = state?.active;
  const isRunning = state?.status === 'running';
  const isError   = state?.status === 'error';
  const lastSummary = state?.last_summary;

  const fmt = (iso) => iso ? new Date(iso).toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';

  return (
    <div style={{ padding: '32px', maxWidth: '960px', margin: '0 auto' }}>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800, background: 'linear-gradient(90deg, #a78bfa, #c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Career Ops — Scanner
        </h1>
        <p style={{ margin: '8px 0 0', color: 'rgba(255,255,255,0.4)', fontSize: '0.88rem' }}>
          Escaneo automático de portales de empleo (Greenhouse, Lever, Ashby) con evaluación IA.
        </p>
      </div>

      {/* ── Status panel ─────────────────────────────────────────────── */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '20px', padding: '24px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <StatusDot status={state?.status || 'idle'} />
            <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.35)' }}>
              <span>Último scan: <strong style={{ color: 'rgba(255,255,255,0.6)' }}>{fmt(state?.last_run_at)}</strong></span>
              {isActive && state?.next_run_at && (
                <span style={{ marginLeft: '16px' }}>Próximo: <strong style={{ color: 'rgba(255,255,255,0.6)' }}>{fmt(state.next_run_at)}</strong></span>
              )}
            </div>
          </div>

          {/* Controls */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <select
              value={interval}
              onChange={e => setIntervalVal(Number(e.target.value))}
              disabled={isActive}
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '8px 12px', color: '#e9d5ff', fontSize: '0.82rem', outline: 'none', width: 'auto', opacity: isActive ? 0.45 : 1, cursor: isActive ? 'not-allowed' : 'pointer' }}
            >
              {INTERVALS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>

            {!isActive ? (
              <button onClick={handleStart} disabled={actionLoading === 'start'} style={btn('primary')}>
                {actionLoading === 'start' ? 'Iniciando…' : '▶ Iniciar scanner'}
              </button>
            ) : (
              <button onClick={handleStop} disabled={actionLoading === 'stop'} style={btn('stop')}>
                {actionLoading === 'stop' ? 'Deteniendo…' : '■ Detener'}
              </button>
            )}

            <button
              onClick={handleRunNow}
              disabled={isRunning || runningNow}
              style={{ ...btn('ghost'), opacity: isRunning || runningNow ? 0.5 : 1, cursor: isRunning || runningNow ? 'not-allowed' : 'pointer' }}
            >
              {runningNow ? 'Iniciando…' : '⚡ Correr ahora'}
            </button>

            {(isRunning || isError) && (
              <button
                onClick={handleReset}
                disabled={actionLoading === 'reset'}
                title="Forzar reset si el scanner está colgado"
                style={{ ...btn('ghost'), borderColor: 'rgba(251,191,36,0.3)', color: '#fcd34d', opacity: actionLoading === 'reset' ? 0.5 : 1 }}
              >
                {actionLoading === 'reset' ? 'Reseteando…' : '↺ Resetear'}
              </button>
            )}
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
          <StatCard value={enabledCount} label="Portales activos" />
          <StatCard value={lastSummary?.found ?? '—'} label="Nuevas (último scan)" color="#60a5fa" />
          <StatCard value={lastSummary?.evaluated ?? '—'} label="Evaluadas (último scan)" color="#22c55e" />
          <StatCard value={lastSummary?.portals ?? '—'} label="Portales escaneados" color="#f59e0b" />
        </div>

        {/* Last error */}
        {state?.last_error && (
          <div style={{ marginTop: '16px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '10px', padding: '10px 14px', color: '#fca5a5', fontSize: '0.8rem' }}>
            <strong>Error último scan:</strong> {state.last_error}
          </div>
        )}

        {/* Log */}
        {lastSummary?.log?.length > 0 && (
          <div style={{ marginTop: '16px', background: 'rgba(0,0,0,0.2)', borderRadius: '10px', padding: '12px 16px', maxHeight: '140px', overflowY: 'auto' }}>
            <p style={{ margin: '0 0 8px', fontSize: '0.68rem', fontWeight: 700, color: 'rgba(255,255,255,0.2)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Log último scan</p>
            {lastSummary.log.map((line, i) => (
              <p key={i} style={{ margin: '2px 0', fontSize: '0.76rem', color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace' }}>› {line}</p>
            ))}
          </div>
        )}
      </div>

      {/* ── Portals preview ──────────────────────────────────────────── */}
      <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '20px', padding: '24px' }}>
        <div style={{ marginBottom: '18px' }}>
          <h3 style={{ margin: 0, fontSize: '0.85rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'rgba(167,139,250,0.8)' }}>
            Plataformas activas ({portals.length})
          </h3>
          <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: 'rgba(255,255,255,0.28)' }}>
            Generadas automáticamente desde tu perfil (países + roles). Configúralas en{' '}
            <a href="/career-ops/config" style={{ color: '#a78bfa', textDecoration: 'none' }}>Configuración</a>.
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', maxHeight: '260px', overflowY: 'auto' }}>
          {portals.map((p, i) => {
            const regionColor = p.region === 'peru' || p.region === 'latam'
              ? 'rgba(34,197,94,0.15)'
              : 'rgba(255,255,255,0.05)';
            const regionBorder = p.region === 'peru' || p.region === 'latam'
              ? 'rgba(34,197,94,0.25)'
              : 'rgba(255,255,255,0.1)';
            return (
              <div key={i} style={{
                background: regionColor,
                border: `1px solid ${regionBorder}`,
                borderRadius: '8px', padding: '6px 12px',
                fontSize: '0.78rem', color: 'rgba(255,255,255,0.6)',
              }}>
                <span style={{ fontWeight: 600, color: p.region === 'peru' || p.region === 'latam' ? '#86efac' : 'rgba(255,255,255,0.7)' }}>
                  {p.company}
                </span>
                <span style={{ marginLeft: '6px', opacity: 0.5, fontSize: '0.7rem' }}>
                  {p.board_type}
                </span>
              </div>
            );
          })}
        </div>

        <div style={{ marginTop: '14px', display: 'flex', gap: '20px', fontSize: '0.72rem', color: 'rgba(255,255,255,0.3)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#86efac', display: 'inline-block' }} />
            Local / LATAM
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'rgba(255,255,255,0.25)', display: 'inline-block' }} />
            Global (filtrado por ubicación)
          </span>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
