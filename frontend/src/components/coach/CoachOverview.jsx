import { useState } from 'react';
import {
  CheckCircle2, ListTodo, Loader2, BookMarked, Activity,
  CalendarClock, Send, Sparkles,
} from 'lucide-react';
import api from '../../api';

const HORIZON_CLASS = { today: 'today', short: 'short', mid: 'mid', long: 'long' };

const CHECKIN_LABELS = {
  morning: '☀️ Mañana', midday: '🎯 Mediodía', evening: '🌙 Noche',
  money: '💰 Cita del dinero', weekly: '📅 Revisión semanal', enrich: '💡 Enriquecer',
  hourly: '⚡ Pulso cada hora', referentes: '🌟 Consejo referente',
};

function fmtDateTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-PE', {
      weekday: 'short', day: 'numeric', month: 'short',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function fmtAgo(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 3600) return `hace ${Math.round(diff / 60)} min`;
    if (diff < 86400) return `hace ${Math.round(diff / 3600)} h`;
    return d.toLocaleDateString('es-PE', { day: 'numeric', month: 'short' });
  } catch { return ''; }
}

function ringStyle(pct) {
  return {
    background: `conic-gradient(#a78bfa ${pct * 3.6}deg, rgba(255,255,255,0.08) 0deg)`,
  };
}

export default function CoachOverview({ metrics, tgConnected, onRefresh }) {
  const [triggering, setTriggering] = useState('');

  if (!metrics) return <div className="coach-empty">Sin datos todavía.</div>;

  const t = metrics.totals;
  const trigger = async (kind) => {
    setTriggering(kind);
    try {
      await api.post('/agent/coach/trigger', { kind });
    } catch (e) {
      alert(e?.response?.data?.detail || 'No se pudo enviar. Escribe primero al bot de Telegram.');
    } finally {
      setTriggering('');
    }
  };

  return (
    <div>
      {/* Stat cards */}
      <div className="stat-grid">
        <div className="stat-card">
          <CheckCircle2 size={30} className="stat-ico" style={{ color: '#4ade80' }} />
          <p className="stat-value" style={{ color: '#4ade80' }}>{t.done}</p>
          <p className="stat-label">Completadas</p>
        </div>
        <div className="stat-card">
          <ListTodo size={30} className="stat-ico" style={{ color: '#fca5a5' }} />
          <p className="stat-value" style={{ color: '#fca5a5' }}>{t.pending}</p>
          <p className="stat-label">Pendientes</p>
        </div>
        <div className="stat-card">
          <Loader2 size={30} className="stat-ico" style={{ color: '#fcd34d' }} />
          <p className="stat-value" style={{ color: '#fcd34d' }}>{t.in_progress}</p>
          <p className="stat-label">En progreso</p>
        </div>
        <div className="stat-card">
          <BookMarked size={30} className="stat-ico" style={{ color: '#93c5fd' }} />
          <p className="stat-value" style={{ color: '#93c5fd' }}>{metrics.knowledge_count}</p>
          <p className="stat-label">Notas en memoria</p>
        </div>
      </div>

      <div className="coach-grid-2">
        {/* Completion + per-horizon */}
        <div className="coach-card">
          <h3><Activity size={17} /> Avance del plan</h3>
          <div className="ring-wrap">
            <div className="ring" style={ringStyle(t.completion_rate)}>
              <div className="ring-val">
                <div className="ring-num">{t.completion_rate}%</div>
                <div className="ring-cap">cumplido</div>
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              {metrics.by_horizon.filter(h => h.total > 0).map((h) => {
                const pct = h.total ? Math.round((h.done / h.total) * 100) : 0;
                return (
                  <div className="progress-row" key={h.label}>
                    <div className="progress-top">
                      <span className="p-label">{h.label}</span>
                      <span className="p-count">{h.done}/{h.total}</span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Next check-ins */}
        <div className="coach-card">
          <h3><CalendarClock size={17} /> Próximos mensajes del coach</h3>
          {tgConnected ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(metrics.next_runs || {})
                .filter(([, v]) => v)
                .sort((a, b) => new Date(a[1]) - new Date(b[1]))
                .map(([kind, iso]) => (
                  <div key={kind} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.75)' }}>
                      {CHECKIN_LABELS[kind] || kind}
                    </span>
                    <span style={{ fontSize: '0.78rem', color: '#a78bfa', fontWeight: 600 }}>
                      {fmtDateTime(iso)}
                    </span>
                  </div>
                ))}
              {Object.values(metrics.next_runs || {}).every(v => !v) && (
                <p className="coach-empty" style={{ padding: 20 }}>
                  No hay check-ins programados. Configúralos en «Frecuencia del coach».
                </p>
              )}
            </div>
          ) : (
            <p className="coach-empty" style={{ padding: 20 }}>
              Escríbele al bot de Telegram una vez para que el coach capture tu chat y
              empiece a enviarte mensajes proactivos.
            </p>
          )}
        </div>
      </div>

      {/* Recent activity */}
      <div className="coach-card" style={{ marginTop: 18 }}>
        <h3><CheckCircle2 size={17} /> Actividad reciente</h3>
        {metrics.recent_done?.length ? (
          <div className="timeline">
            {metrics.recent_done.map((g, i) => (
              <div className="tl-item" key={i}>
                <div className="tl-dot" />
                <div className="tl-body" style={{ flex: 1 }}>
                  <p className="tl-title">{g.title}</p>
                  <p className="tl-time">
                    <span className={`goal-h ${HORIZON_CLASS[g.horizon] || 'today'}`}
                          style={{ marginRight: 8 }}>{g.horizon}</span>
                    {fmtAgo(g.done_at)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="coach-empty" style={{ padding: 24 }}>
            Aún no completas tareas. Marca tu primera en «Metas y avances» y empieza la racha. 🔥
          </p>
        )}
      </div>

      {/* Test triggers */}
      <div className="coach-card" style={{ marginTop: 18 }}>
        <h3><Send size={17} /> Enviar un mensaje de prueba a Telegram</h3>
        <p style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)', marginTop: -8, marginBottom: 16 }}>
          Dispara cualquier check-in ahora mismo para ver cómo te llega al chat.
        </p>
        <div className="trigger-grid">
          {Object.entries(CHECKIN_LABELS).map(([kind, label]) => (
            <button key={kind} className="trigger-btn"
              disabled={!tgConnected || triggering === kind}
              onClick={() => trigger(kind)}>
              {triggering === kind ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
              {label}
            </button>
          ))}
        </div>
        {!tgConnected && (
          <p style={{ fontSize: '0.75rem', color: '#fbbf24', marginTop: 12 }}>
            Vincula Telegram (escríbele al bot) para habilitar el envío.
          </p>
        )}
      </div>

      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
