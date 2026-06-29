import { useState, useEffect, useCallback } from 'react';
import { Clock, Save, Check } from 'lucide-react';
import api from '../../api';

// Orden y descripción de cada check-in del cron.
const CHECKINS = [
  { key: 'morning', name: '☀️ Arranque de la mañana', desc: 'Plan del día, hábito clave de 90 min y tus tareas de hoy. Diario.' },
  { key: 'midday', name: '🎯 Empuje de mediodía', desc: 'Acción de adquisición + "¿hiciste tu bloque profundo?". Diario.' },
  { key: 'evening', name: '🌙 Reporte de la noche', desc: 'Te pregunta por cada tarea pendiente y te da feedback. Diario.' },
  { key: 'money', name: '💰 Cita con el dinero', desc: 'Cobranzas, facturar y provisionar impuestos. Cada viernes.' },
  { key: 'weekly', name: '📅 Revisión semanal', desc: 'Las 4 preguntas de cierre de semana. Cada domingo.' },
  { key: 'enrich', name: '💡 Enriquecer al agente', desc: 'Propone investigar algo útil y pide permiso para guardarlo. Cada miércoles.' },
  { key: 'hourly', name: '⚡ Pulso cada hora', desc: 'Analiza todo tu panorama y te da una sugerencia, idea, consejo o reto. Cada hora, de 8am a 10pm. El minuto que elijas marca cuándo dentro de cada hora.' },
];

function fmtNext(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString('es-PE', {
      weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch { return null; }
}

export default function CoachSchedule({ tgConnected }) {
  const [schedule, setSchedule] = useState(null);
  const [nextRuns, setNextRuns] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    const { data } = await api.get('/agent/coach/schedule');
    setSchedule(data.schedule);
    setNextRuns(data.next_runs || {});
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const setTime = (key, value) => {
    setSchedule(s => ({ ...s, [key]: value }));
    setSaved(false);
  };

  const toggle = (key) => {
    setSchedule(s => ({ ...s, [key]: s[key] ? '' : defaultTime(key) }));
    setSaved(false);
  };

  const defaultTime = (key) => ({
    morning: '07:30', midday: '13:00', evening: '20:30',
    money: '17:00', weekly: '19:00', enrich: '11:00', hourly: '00:00',
  }[key] || '09:00');

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.patch('/agent/coach/schedule', { schedule });
      setSchedule(data.schedule);
      setNextRuns(data.next_runs || {});
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="coach-empty">Cargando frecuencia…</div>;

  return (
    <div className="coach-card">
      <h3><Clock size={17} /> Frecuencia de los mensajes del coach</h3>
      <p style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.42)', marginTop: -8, marginBottom: 10 }}>
        Define a qué hora (zona horaria de Lima 🇵🇪) te escribe el coach por Telegram en cada
        momento. Apaga el interruptor para desactivar ese mensaje.
      </p>
      {!tgConnected && (
        <p className="coach-pill warn" style={{ marginBottom: 16 }}>
          Vincula Telegram para que los mensajes se envíen.
        </p>
      )}

      <div>
        {CHECKINS.map(c => {
          const on = !!schedule[c.key];
          const next = fmtNext(nextRuns[c.key]);
          return (
            <div className="sched-row" key={c.key}>
              <button
                className={`switch ${on ? 'on' : ''}`}
                onClick={() => toggle(c.key)}
                title={on ? 'Desactivar' : 'Activar'}
              />
              <div className="sched-info">
                <p className="s-name">{c.name}</p>
                <p className="s-desc">{c.desc}</p>
                {on && next && <p className="s-next">Próximo: {next}</p>}
              </div>
              <input
                type="time"
                className="sched-time"
                value={schedule[c.key] || ''}
                disabled={!on}
                onChange={e => setTime(c.key, e.target.value)}
              />
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20, gap: 12, alignItems: 'center' }}>
        {saved && (
          <span className="coach-pill on"><Check size={13} /> Guardado</span>
        )}
        <button className="cbtn cbtn-primary" onClick={save} disabled={saving}>
          <Save size={15} /> {saving ? 'Guardando…' : 'Guardar frecuencia'}
        </button>
      </div>
    </div>
  );
}
