import { useState, useEffect } from 'react';
import { Activity, ChevronRight, ChevronLeft, RefreshCw } from 'lucide-react';
import api from '../../api';

const POOL_LABELS = { text: 'Texto', image: 'Imagen', audio_stt: 'Audio STT', tts: 'TTS' };
const STATUS_COLOR = { active: '#22c55e', quota_exhausted: '#f59e0b', error: '#ef4444', unknown: '#6b7280' };
const STATUS_LABEL = { active: 'Activo', quota_exhausted: 'Cuota agotada', error: 'Error', unknown: '?' };

export default function ModelStatus({ collapsed, onToggle }) {
  const [pools, setPools] = useState({});
  const [asOf, setAsOf] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 60_000);
    return () => clearInterval(id);
  }, []);

  async function fetchStatus() {
    setLoading(true);
    try {
      const { data } = await api.get('/agent/models/status');
      setPools(data.pools || {});
      setAsOf(data.as_of ? new Date(data.as_of).toLocaleTimeString() : '');
    } catch {}
    setLoading(false);
  }

  return (
    <div className={`model-status-panel ${collapsed ? 'collapsed' : ''}`}>
      <div className="status-header" onClick={onToggle}>
        <Activity size={15} style={{ color: '#a78bfa' }} />
        {!collapsed && <span>Estado de modelos</span>}
        {collapsed ? <ChevronLeft size={13} /> : <ChevronRight size={13} />}
      </div>

      {!collapsed && (
        <div className="status-body">
          <div className="status-refresh">
            <span style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.3)' }}>
              Actualizado: {asOf || '—'}
            </span>
            <button className="btn-ghost-xs" onClick={fetchStatus} disabled={loading}>
              <RefreshCw size={11} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            </button>
          </div>
          {Object.entries(pools).map(([pool, models]) => (
            <div key={pool} className="status-pool">
              <div className="status-pool-label">{POOL_LABELS[pool] || pool}</div>
              {models.map(m => (
                <div key={m.model_id} className="status-model-row">
                  <span
                    className="status-dot"
                    style={{ background: STATUS_COLOR[m.status] || '#6b7280' }}
                    title={STATUS_LABEL[m.status]}
                  />
                  <span className="status-model-name">{m.display_name}</span>
                  <span className="status-quota">
                    {m.daily_limit ? `${m.requests_today}/${m.daily_limit}` : '∞'}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
