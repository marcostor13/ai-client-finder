import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, Play, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import api from '../../api';

const LEVEL = {
  success: { color: '#4ade80', Icon: CheckCircle },
  error:   { color: '#f87171', Icon: AlertTriangle },
  warn:    { color: '#fbbf24', Icon: AlertTriangle },
  info:    { color: '#94a3b8', Icon: Info },
};

const KINDS = [
  ['morning', 'Mañana'], ['midday', 'Mediodía'], ['evening', 'Noche'],
  ['hourly', 'Pulso horario'], ['money', 'Dinero'], ['weekly', 'Semanal'], ['enrich', 'Enriquecer'],
];

function fmt(ts) {
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
}

export default function CoachLogs() {
  const [data, setData] = useState(null);
  const [kind, setKind] = useState('morning');
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState('');
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/agent/coach/logs');
      setData(res.data);
    } catch { /* coach off */ }
  }, []);

  useEffect(() => {
    load();
    pollRef.current = setInterval(load, 5000);
    return () => clearInterval(pollRef.current);
  }, [load]);

  const test = async () => {
    setTesting(true);
    setMsg('');
    try {
      await api.post('/agent/coach/trigger', { kind });
      setMsg('Disparado. Revisa Telegram y el log abajo.');
    } catch (e) {
      setMsg(e?.response?.data?.detail || 'No se pudo disparar (¿escribiste al bot?).');
    } finally {
      setTesting(false);
      setTimeout(load, 800);
    }
  };

  const logs = data?.logs || [];
  const nextRuns = data?.next_runs || {};
  const tg = data?.telegram_connected;

  return (
    <div className="coach-card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Status + test */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: '0.82rem', color: tg ? '#4ade80' : '#f87171', fontWeight: 600 }}>
          {tg ? '✓ Telegram conectado' : '✗ Sin chat de Telegram — escríbele al bot una vez (con el coach activo)'}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select value={kind} onChange={e => setKind(e.target.value)}
            style={{ padding: '7px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.12)', color: 'var(--text-main)', fontSize: '0.8rem' }}>
            {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <button onClick={test} disabled={testing}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 9,
              border: 'none', cursor: 'pointer', background: 'linear-gradient(135deg,#6D28D9,#4C1D95)',
              color: '#fff', fontWeight: 600, fontSize: '0.8rem' }}>
            <Play size={14} /> {testing ? 'Probando…' : 'Probar ahora'}
          </button>
          <button onClick={load} title="Refrescar"
            style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, width: 34, height: 34, cursor: 'pointer', color: '#a78bfa' }}>
            <RefreshCw size={14} />
          </button>
        </div>
      </div>
      {msg && <div style={{ fontSize: '0.78rem', color: '#a78bfa' }}>{msg}</div>}

      {/* Logs */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 420, overflowY: 'auto' }}>
        {logs.length === 0 && (
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', padding: '12px 0' }}>
            Aún no hay actividad registrada. Usa "Probar ahora" o espera un check-in programado.
          </div>
        )}
        {logs.map((l) => {
          const { color, Icon } = LEVEL[l.level] || LEVEL.info;
          return (
            <div key={l._id} style={{ display: 'flex', gap: 10, alignItems: 'flex-start',
              padding: '9px 11px', borderRadius: 9, background: 'rgba(255,255,255,0.03)',
              borderLeft: `3px solid ${color}` }}>
              <Icon size={15} style={{ color, flexShrink: 0, marginTop: 1 }} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-main)' }}>{l.event}</div>
                {l.detail && (
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{l.detail}</div>
                )}
                <div style={{ fontSize: '0.66rem', color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>{fmt(l.ts)}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Next runs */}
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 12 }}>
        <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8 }}>
          Próximas ejecuciones programadas
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {KINDS.map(([k, l]) => (
            <div key={k} style={{ fontSize: '0.7rem', color: 'var(--text-muted)',
              background: 'rgba(255,255,255,0.04)', padding: '5px 9px', borderRadius: 7 }}>
              {l}: <span style={{ color: nextRuns[k] ? '#a78bfa' : 'rgba(255,255,255,0.25)' }}>
                {nextRuns[k] ? fmt(nextRuns[k]) : '—'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
