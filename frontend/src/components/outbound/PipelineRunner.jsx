import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Play, Loader2, CheckCircle, AlertCircle, X, Search, Mail, Send, Zap } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../../api';

const IDLE = 'idle';
const RUNNING = 'running';
const DONE = 'done';
const ERROR = 'error';

// Messages shown while the pipeline runs (cycles automatically)
const DISCOVER_MSGS = [
  '🔍 Leyendo tu configuración ICP activa…',
  '🌐 Buscando empresas con DuckDuckGo…',
  '🗂 Filtrando directorios y spam…',
  '✅ Validando URLs y sitios web reales…',
  '📊 Puntuando empresas con tu ICP…',
  '📬 Buscando emails de contacto (Hunter / Apollo)…',
  '💾 Guardando prospects en la base de datos…',
];

const DRAFT_MSGS = [
  '🤖 Cargando prospects listos para contactar…',
  '✍️  Analizando empresa #1 con IA…',
  '📧 Generando email hiperpersonalizado…',
  '🎯 Identificando punto de dolor principal…',
  '💡 Construyendo propuesta agresiva y atractiva…',
  '🔗 Insertando link de Calendly…',
  '🗃  Guardando borradores en la cola…',
];

function LiveMessage({ running, phase }) {
  const [msgIdx, setMsgIdx] = useState(0);
  const msgs = phase === 'discover' ? DISCOVER_MSGS : DRAFT_MSGS;

  useEffect(() => {
    if (!running) return;
    setMsgIdx(0);
    const id = setInterval(() => setMsgIdx(i => (i + 1) % msgs.length), 2200);
    return () => clearInterval(id);
  }, [running, phase]);

  if (!running) return null;
  return (
    <span style={{ fontSize: '0.78rem', color: '#a78bfa', display: 'block', minHeight: '18px', animation: 'fadeMsg 0.3s ease' }}>
      {msgs[msgIdx]}
    </span>
  );
}

function StepBlock({ icon: Icon, title, running, result, livePhase }) {
  const isActive = running;
  const ok = result && (result.status === 'ok' || result.status === 'capped' || result.status === 'skipped');
  const hasResult = Boolean(result);

  function resultText() {
    if (!result) return null;
    if (result.status === 'capped') return 'Cap diario alcanzado — sin nuevas entradas.';
    if (result.status === 'skipped') return `Omitido: ${result.reason}`;
    if (result.status === 'error') return `Error: ${result.error || result.reason}`;
    if (result.status === 'ok') {
      return Object.entries(result)
        .filter(([k]) => k !== 'status')
        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
        .join(' · ');
    }
    return null;
  }

  return (
    <div style={{
      borderRadius: '12px',
      border: `1px solid ${isActive ? 'rgba(167,139,250,0.5)' : hasResult ? (ok ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)') : 'rgba(255,255,255,0.07)'}`,
      background: isActive ? 'rgba(109,40,217,0.12)' : hasResult ? (ok ? 'rgba(34,197,94,0.05)' : 'rgba(239,68,68,0.05)') : 'rgba(255,255,255,0.03)',
      padding: '14px 16px',
      display: 'flex', gap: '14px', alignItems: 'flex-start',
      transition: 'all 0.3s',
    }}>
      <div style={{
        width: '34px', height: '34px', borderRadius: '10px', flexShrink: 0,
        background: isActive ? 'rgba(109,40,217,0.3)' : hasResult ? (ok ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)') : 'rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {isActive
          ? <Loader2 size={15} style={{ color: '#a78bfa', animation: 'spin 1s linear infinite' }} />
          : hasResult
            ? (ok ? <CheckCircle size={15} style={{ color: '#86efac' }} /> : <AlertCircle size={15} style={{ color: '#fca5a5' }} />)
            : <Icon size={15} style={{ color: 'var(--text-muted)' }} />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: '0.86rem', fontWeight: 700, color: isActive ? '#e9d5ff' : 'var(--text-main)', marginBottom: '4px' }}>
          {title}
        </p>
        {isActive
          ? <LiveMessage running={isActive} phase={livePhase} />
          : hasResult
            ? <span style={{ fontSize: '0.78rem', color: ok ? '#86efac' : '#fca5a5' }}>{resultText()}</span>
            : <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>En espera…</span>}
      </div>
    </div>
  );
}

export default function PipelineRunner({ collapsed = false }) {
  const navigate = useNavigate();
  const [phase, setPhase] = useState(IDLE);
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState(null);
  const [liveStep, setLiveStep] = useState(null); // 'discover' | 'draft'
  const startRef = useRef(null);

  async function handleRun() {
    setOpen(true);
    setPhase(RUNNING);
    setResults(null);
    setLiveStep('discover');
    startRef.current = Date.now();
    try {
      // Run pipeline — backend does discover first, then draft
      const res = await api.post('/api/outbound/jobs/run-pipeline');
      setLiveStep(null);
      setResults(res.data);
      setPhase(DONE);
    } catch (err) {
      setLiveStep(null);
      setResults({
        discover: { status: 'error', error: err.message },
        draft: { status: 'error', error: err.message },
      });
      setPhase(ERROR);
    }
  }

  // Simulate switching live step mid-run (discover ~60%, draft ~40% of time)
  useEffect(() => {
    if (phase !== RUNNING) return;
    const timer = setTimeout(() => setLiveStep('draft'), 18000); // switch after ~18s
    return () => clearTimeout(timer);
  }, [phase]);

  const drafted = results?.draft?.drafted ?? 0;
  const discovered = results?.discover?.discovered ?? 0;

  const modal = open ? (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '24px',
    }}>
      <div style={{
        background: 'linear-gradient(145deg, #12102a, #1a1535)',
        border: '1px solid rgba(167,139,250,0.35)',
        borderRadius: '20px', padding: '32px',
        width: '100%', maxWidth: '460px',
        boxShadow: '0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(167,139,250,0.1)',
      }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px', height: '38px', borderRadius: '11px',
              background: phase === DONE ? 'rgba(34,197,94,0.2)' : phase === ERROR ? 'rgba(239,68,68,0.2)' : 'rgba(109,40,217,0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {phase === RUNNING && <Zap size={18} style={{ color: '#a78bfa' }} />}
              {phase === DONE && <CheckCircle size={18} style={{ color: '#86efac' }} />}
              {phase === ERROR && <AlertCircle size={18} style={{ color: '#fca5a5' }} />}
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-main)' }}>
                {phase === RUNNING ? 'Pipeline ejecutándose…' : phase === DONE ? 'Pipeline completado' : 'Error en pipeline'}
              </h3>
              {phase === RUNNING && (
                <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                  Esto puede tardar 1–3 minutos. No cierres esta ventana.
                </p>
              )}
            </div>
          </div>
          {phase !== RUNNING && (
            <button onClick={() => { setOpen(false); setPhase(IDLE); }} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', padding: '6px', borderRadius: '8px' }}>
              <X size={16} />
            </button>
          )}
        </div>

        {/* Progress bar (running only) */}
        {phase === RUNNING && (
          <div style={{ marginBottom: '20px', background: 'rgba(255,255,255,0.06)', borderRadius: '999px', height: '4px', overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: '999px',
              background: 'linear-gradient(90deg, #6D28D9, #a78bfa)',
              animation: 'progressBar 2.5s ease-in-out infinite alternate',
              width: '60%',
            }} />
          </div>
        )}

        {/* Steps */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <StepBlock
            icon={Search}
            title="Paso 1 — Descubrir y puntuar empresas"
            running={phase === RUNNING && liveStep === 'discover'}
            result={results?.discover}
            livePhase="discover"
          />
          <StepBlock
            icon={Mail}
            title="Paso 2 — Redactar emails personalizados con IA"
            running={phase === RUNNING && liveStep === 'draft'}
            result={results?.draft}
            livePhase="draft"
          />
          {phase === DONE && (
            <StepBlock
              icon={Send}
              title="Paso 3 — Envío"
              running={false}
              result={{ status: 'skipped', reason: 'Requiere aprobación manual antes de enviar' }}
              livePhase="send"
            />
          )}
        </div>

        {/* Summary when done */}
        {phase === DONE && (
          <div style={{ marginTop: '20px', padding: '14px 16px', background: 'rgba(109,40,217,0.12)', border: '1px solid rgba(167,139,250,0.2)', borderRadius: '12px' }}>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Resumen de ejecución</p>
            <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 700 }}>
                <span style={{ color: '#60a5fa' }}>{discovered}</span>
                <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> empresas descubiertas</span>
              </span>
              <span style={{ fontSize: '0.9rem', fontWeight: 700 }}>
                <span style={{ color: '#a78bfa' }}>{drafted}</span>
                <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}> emails redactados</span>
              </span>
            </div>
          </div>
        )}

        {/* CTAs */}
        {phase === DONE && drafted > 0 && (
          <button
            onClick={() => { setOpen(false); setPhase(IDLE); navigate('/outbound/approvals'); }}
            style={{ width: '100%', marginTop: '14px', padding: '13px', background: 'linear-gradient(135deg, rgba(109,40,217,0.6), rgba(76,29,149,0.5))', border: '1px solid rgba(167,139,250,0.45)', borderRadius: '12px', color: '#e9d5ff', cursor: 'pointer', fontSize: '0.92rem', fontWeight: 700, fontFamily: 'inherit' }}
          >
            Revisar y aprobar {drafted} email{drafted !== 1 ? 's' : ''} →
          </button>
        )}
        {phase === DONE && drafted === 0 && (
          <p style={{ marginTop: '16px', fontSize: '0.81rem', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.5 }}>
            No se generaron nuevos drafts. Puede que no haya prospects enriquecidos con email aún, o que se haya alcanzado el cap diario.
          </p>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeMsg { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes progressBar { from { width: 15%; } to { width: 85%; } }
      `}</style>
    </div>
  ) : null;

  return (
    <>
      <button
        onClick={handleRun}
        disabled={phase === RUNNING}
        title={collapsed ? 'Ejecutar pipeline' : undefined}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
          width: collapsed ? '44px' : '100%',
          height: collapsed ? '44px' : 'auto',
          background: phase === RUNNING ? 'rgba(109,40,217,0.3)' : 'rgba(109,40,217,0.5)',
          border: '1px solid rgba(167,139,250,0.5)',
          borderRadius: collapsed ? '12px' : '10px',
          padding: collapsed ? '0' : '9px 14px',
          color: '#c4b5fd', cursor: phase === RUNNING ? 'not-allowed' : 'pointer',
          fontSize: '0.82rem', fontWeight: 700, fontFamily: 'inherit',
          transition: 'background 0.2s, width 0.2s',
          boxShadow: '0 2px 10px rgba(109,40,217,0.25)',
          flexShrink: 0,
        }}
      >
        {phase === RUNNING
          ? <><Loader2 size={collapsed ? 16 : 14} style={{ animation: 'spin 1s linear infinite' }} />{!collapsed && ' Ejecutando…'}</>
          : <><Play size={collapsed ? 16 : 13} />{!collapsed && ' Ejecutar pipeline'}</>}
      </button>

      {/* Render modal in document.body to avoid stacking context issues */}
      {createPortal(modal, document.body)}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}
