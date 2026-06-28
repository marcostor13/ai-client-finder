import { useState, useEffect, useCallback } from 'react';
import { Plus, Check, Trash2, Target } from 'lucide-react';
import api from '../../api';

const HORIZONS = [
  { key: 'today', label: '🔴 Hoy / urgente' },
  { key: 'short', label: '🟡 Corto plazo (0-3 meses)' },
  { key: 'mid', label: '🟢 Mediano plazo (3-6 meses)' },
  { key: 'long', label: '🔵 Largo plazo (6-18 meses)' },
];

export default function CoachGoals({ onChange }) {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newTitle, setNewTitle] = useState('');
  const [newHorizon, setNewHorizon] = useState('today');
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get('/agent/coach/goals');
    setGoals(data.goals || []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const notify = () => { onChange && onChange(); };

  const add = async (e) => {
    e?.preventDefault();
    if (!newTitle.trim()) return;
    setAdding(true);
    try {
      await api.post('/agent/coach/goals', { title: newTitle.trim(), horizon: newHorizon });
      setNewTitle('');
      await load();
      notify();
    } finally {
      setAdding(false);
    }
  };

  const toggle = async (g) => {
    const next = g.status === 'done' ? 'pending' : 'done';
    setGoals(gs => gs.map(x => x._id === g._id ? { ...x, status: next } : x));
    try {
      await api.patch(`/agent/coach/goals/${g._id}`, { status: next });
      notify();
    } catch { load(); }
  };

  const remove = async (g) => {
    setGoals(gs => gs.filter(x => x._id !== g._id));
    try {
      await api.delete(`/agent/coach/goals/${g._id}`);
      notify();
    } catch { load(); }
  };

  if (loading) return <div className="coach-empty">Cargando metas…</div>;

  const pending = goals.filter(g => g.status !== 'done').length;

  return (
    <div className="coach-card">
      <h3>
        <Target size={17} /> Tus metas del plan
        <span style={{ marginLeft: 'auto', fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)', fontWeight: 500 }}>
          {pending} pendientes · {goals.length} en total
        </span>
      </h3>

      {/* Add new */}
      <form onSubmit={add} style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        <input
          className="coach-input"
          placeholder="Nueva meta o tarea…"
          value={newTitle}
          onChange={e => setNewTitle(e.target.value)}
          style={{ minWidth: 200 }}
        />
        <select
          className="coach-input"
          value={newHorizon}
          onChange={e => setNewHorizon(e.target.value)}
          style={{ flex: '0 0 auto', width: 200, cursor: 'pointer' }}
        >
          {HORIZONS.map(h => <option key={h.key} value={h.key}>{h.label}</option>)}
        </select>
        <button className="cbtn cbtn-primary" type="submit" disabled={adding || !newTitle.trim()}>
          <Plus size={16} /> Agregar
        </button>
      </form>

      {/* Grouped list */}
      {goals.length === 0 ? (
        <p className="coach-empty">Sin metas todavía. Agrega la primera arriba.</p>
      ) : (
        HORIZONS.map(h => {
          const items = goals.filter(g => g.horizon === h.key);
          if (!items.length) return null;
          return (
            <div key={h.key}>
              <div className="goal-group-h">{h.label}</div>
              <div className="goal-list">
                {items.map(g => (
                  <div key={g._id} className={`goal-item ${g.status === 'done' ? 'done' : ''}`}>
                    <button
                      className={`goal-check ${g.status === 'done' ? 'checked' : ''}`}
                      onClick={() => toggle(g)}
                      title={g.status === 'done' ? 'Marcar pendiente' : 'Marcar completada'}
                    >
                      {g.status === 'done' && <Check size={14} />}
                    </button>
                    <span className="goal-title">{g.title}</span>
                    <button className="goal-del" onClick={() => remove(g)} title="Eliminar">
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
