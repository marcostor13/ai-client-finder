import { useState, useEffect, useCallback } from 'react';
import { Star, Plus, Trash2, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../../api';

const EMPTY = { name: '', why: '', content: '' };

export default function CoachReferentes() {
  const [referentes, setReferentes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(EMPTY);
  const [adding, setAdding] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/agent/coach/referentes');
      setReferentes(data.referentes || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setAdding(true);
    try {
      await api.post('/agent/coach/referentes', form);
      setForm(EMPTY);
      await load();
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id) => {
    setDeleting(id);
    try {
      await api.delete(`/agent/coach/referentes/${id}`);
      setReferentes(r => r.filter(x => x._id !== id));
    } finally {
      setDeleting(null);
    }
  };

  const toggleExpand = (id) => setExpanded(e => e === id ? null : id);

  if (loading) return <div className="coach-empty">Cargando referentes…</div>;

  return (
    <div>
      {/* Add form */}
      <div className="coach-card">
        <h3><Plus size={17} /> Agregar persona inspiradora</h3>
        <p style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.42)', marginTop: -8, marginBottom: 16 }}>
          Cada 2 horas el coach tomará uno de estos referentes y te dará un consejo práctico
          conectado a tus objetivos actuales, basado en su filosofía y enseñanzas.
        </p>
        <form onSubmit={handleAdd} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input
              className="sched-time"
              style={{ flex: '1 1 220px', height: 40, padding: '0 14px', fontSize: '0.9rem' }}
              type="text"
              placeholder="Nombre (ej. Alex Hormozi, James Clear, Naval Ravikant…)"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              required
              maxLength={100}
            />
            <button
              className="cbtn cbtn-primary"
              type="submit"
              disabled={adding || !form.name.trim()}
              style={{ whiteSpace: 'nowrap' }}
            >
              <Plus size={15} /> {adding ? 'Guardando…' : 'Agregar'}
            </button>
          </div>
          <textarea
            className="sched-time"
            style={{ resize: 'vertical', minHeight: 68, padding: '10px 14px', fontSize: '0.85rem', lineHeight: 1.5 }}
            placeholder="¿Por qué te inspira? (opcional)"
            value={form.why}
            onChange={e => setForm(f => ({ ...f, why: e.target.value }))}
            maxLength={400}
          />
          <textarea
            className="sched-time"
            style={{ resize: 'vertical', minHeight: 90, padding: '10px 14px', fontSize: '0.85rem', lineHeight: 1.5 }}
            placeholder="Filosofía, enseñanzas, frases clave, principios… (opcional pero mejora los consejos)"
            value={form.content}
            onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
            maxLength={1000}
          />
        </form>
      </div>

      {/* List */}
      <div className="coach-card" style={{ marginTop: 18 }}>
        <h3>
          <Star size={17} /> Mis referentes ({referentes.length})
        </h3>
        {referentes.length === 0 ? (
          <div className="coach-empty" style={{ padding: '28px 0' }}>
            <Sparkles size={32} style={{ color: 'rgba(167,139,250,0.3)', marginBottom: 10 }} />
            <p>Aún no has agregado referentes.</p>
            <p style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.35)', marginTop: 6 }}>
              Agrega personas que admires — el coach usará su sabiduría para darte consejos cada 2 horas.
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {referentes.map(r => (
              <div key={r._id} className="sched-row" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 0, padding: '12px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div className="tl-dot" style={{ flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontWeight: 700, fontSize: '0.95rem', margin: 0, color: '#c4b5fd' }}>
                      {r.name}
                    </p>
                    {r.why && (
                      <p style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.5)', margin: '2px 0 0' }}>
                        {r.why}
                      </p>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                    {r.content && (
                      <button
                        className="cbtn cbtn-ghost"
                        style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                        onClick={() => toggleExpand(r._id)}
                        title={expanded === r._id ? 'Contraer' : 'Ver filosofía'}
                      >
                        {expanded === r._id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                    )}
                    <button
                      className="cbtn cbtn-ghost"
                      style={{ padding: '4px 8px', color: '#f87171' }}
                      onClick={() => handleDelete(r._id)}
                      disabled={deleting === r._id}
                      title="Eliminar"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                {expanded === r._id && r.content && (
                  <div style={{
                    marginTop: 10,
                    padding: '10px 14px',
                    background: 'rgba(167,139,250,0.07)',
                    borderRadius: 8,
                    borderLeft: '3px solid rgba(167,139,250,0.4)',
                    fontSize: '0.82rem',
                    color: 'rgba(255,255,255,0.65)',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                  }}>
                    {r.content}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info pill */}
      {referentes.length > 0 && (
        <div style={{ marginTop: 16, padding: '12px 16px', background: 'rgba(167,139,250,0.07)', borderRadius: 12, border: '1px solid rgba(167,139,250,0.15)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Sparkles size={16} style={{ color: '#a78bfa', flexShrink: 0 }} />
          <p style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.55)', margin: 0 }}>
            El coach rota entre tus {referentes.length} referente{referentes.length !== 1 ? 's' : ''} y te envía un consejo práctico
            cada 2 horas (de 8am a 10pm), conectado directamente a tus objetivos del plan.
            Configura el minuto exacto en la pestaña <strong style={{ color: '#a78bfa' }}>Frecuencia</strong>.
          </p>
        </div>
      )}
    </div>
  );
}
