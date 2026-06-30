import { useState, useEffect, useCallback } from 'react';
import {
  Trophy, LayoutDashboard, Target, Clock, MessageCircle,
  Power, RefreshCw, Star,
} from 'lucide-react';
import api from '../api';
import CoachOverview from '../components/coach/CoachOverview';
import CoachGoals from '../components/coach/CoachGoals';
import CoachSchedule from '../components/coach/CoachSchedule';
import CoachReferentes from '../components/coach/CoachReferentes';
import Spinner from '../components/Spinner';
import '../coach.css';

const TABS = [
  { key: 'overview', label: 'Resumen', icon: LayoutDashboard },
  { key: 'goals', label: 'Metas y avances', icon: Target },
  { key: 'referentes', label: 'Referentes', icon: Star },
  { key: 'schedule', label: 'Frecuencia del coach', icon: Clock },
];

export default function CoachDashboard() {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [tab, setTab] = useState('overview');
  const [busy, setBusy] = useState(false);

  const loadStatus = useCallback(async () => {
    const { data } = await api.get('/agent/coach/status');
    setStatus(data);
    return data;
  }, []);

  const loadMetrics = useCallback(async () => {
    try {
      const { data } = await api.get('/agent/coach/metrics');
      setMetrics(data);
    } catch { /* coach off */ }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const s = await loadStatus();
        if (s.enabled) await loadMetrics();
      } finally {
        setLoading(false);
      }
    })();
  }, [loadStatus, loadMetrics]);

  const toggleCoach = async () => {
    setBusy(true);
    try {
      if (status?.enabled) {
        await api.post('/agent/coach/disable');
      } else {
        await api.post('/agent/coach/enable');
      }
      const s = await loadStatus();
      if (s.enabled) await loadMetrics();
    } finally {
      setBusy(false);
    }
  };

  const refresh = useCallback(async () => {
    await Promise.all([loadStatus(), loadMetrics()]);
  }, [loadStatus, loadMetrics]);

  if (loading) return <Spinner fullPage size={44} label="Cargando coach…" />;

  const enabled = status?.enabled;
  const tgConnected = status?.telegram_connected;

  return (
    <div className="coach-page">
      <div className="coach-head">
        <div>
          <h1><Trophy size={26} style={{ color: '#a78bfa' }} /> Coach Personal</h1>
          <p className="coach-sub">
            Tu agente enfocado 100% en tu Plan Integral y Financiero. Te acompaña por
            Telegram, te recuerda tus prioridades, mide tu avance y te mantiene en el
            camino sin perder el contexto.
          </p>
          <div style={{ display: 'flex', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
            <span className={`coach-pill ${enabled ? 'on' : 'off'}`}>
              <Power size={13} /> {enabled ? 'Coach activo' : 'Coach apagado'}
            </span>
            <span className={`coach-pill ${tgConnected ? 'on' : 'warn'}`}>
              <MessageCircle size={13} />
              {tgConnected ? 'Telegram vinculado' : 'Escribe al bot para vincular'}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {enabled && (
            <button className="cbtn cbtn-ghost" onClick={refresh} title="Refrescar">
              <RefreshCw size={15} />
            </button>
          )}
          <button
            className={`cbtn ${enabled ? 'cbtn-ghost' : 'cbtn-primary'}`}
            onClick={toggleCoach}
            disabled={busy}
          >
            <Power size={15} />
            {busy ? '…' : enabled ? 'Apagar coach' : 'Activar coach'}
          </button>
        </div>
      </div>

      {!enabled ? (
        <div className="coach-card" style={{ marginTop: 28 }}>
          <div className="coach-empty">
            <Trophy size={40} style={{ color: 'rgba(167,139,250,0.4)', marginBottom: 14 }} />
            <p style={{ fontSize: '1rem', color: 'rgba(255,255,255,0.6)', fontWeight: 600 }}>
              El coach está apagado.
            </p>
            <p>
              Actívalo para cargar tus metas del plan, recibir mensajes proactivos por
              Telegram y ver tu dashboard de avances.
            </p>
            <button className="cbtn cbtn-primary" onClick={toggleCoach} disabled={busy}
                    style={{ marginTop: 16 }}>
              <Power size={15} /> Activar coach
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="coach-tabs">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button key={key}
                className={`coach-tab ${tab === key ? 'active' : ''}`}
                onClick={() => setTab(key)}>
                <Icon size={16} /> {label}
              </button>
            ))}
          </div>

          {tab === 'overview' && (
            <CoachOverview metrics={metrics} tgConnected={tgConnected} onRefresh={refresh} />
          )}
          {tab === 'goals' && (
            <CoachGoals onChange={loadMetrics} />
          )}
          {tab === 'referentes' && (
            <CoachReferentes />
          )}
          {tab === 'schedule' && (
            <CoachSchedule tgConnected={tgConnected} />
          )}
        </>
      )}
    </div>
  );
}
