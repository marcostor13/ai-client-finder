import { useState, useEffect, useCallback, useRef } from 'react';
import Spinner from '../components/Spinner';
import {
  Search, Globe, Loader2, ChevronDown, ChevronUp,
  Zap, Lightbulb, Send, ExternalLink, History, Trash2,
  Plus, Clock, ChevronLeft, ChevronRight, X, Briefcase,
  DollarSign, AlertTriangle, CheckCircle, Star, MapPin,
  Users, BarChart2, Shield, FileText, Copy, Check,
} from 'lucide-react';
import api from '../api';

// ── Utilities ──────────────────────────────────────────────────────────────

const scoreColor = s =>
  !s && s !== 0 ? '#6b7280' : s >= 70 ? '#22c55e' : s >= 40 ? '#eab308' : '#ef4444';

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'ahora';
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d`;
  return new Date(iso).toLocaleDateString('es-PE', { day: '2-digit', month: 'short' });
}

const PLATFORM_COLORS = {
  'Upwork':           { bg: 'rgba(20,173,91,0.18)',   color: '#14AD5B' },
  'Freelancer':       { bg: 'rgba(39,130,220,0.18)',  color: '#2782DC' },
  'Toptal':           { bg: 'rgba(200,200,220,0.12)', color: '#b0b8cc' },
  'Guru':             { bg: 'rgba(230,121,30,0.18)',  color: '#E6791E' },
  'PeoplePerHour':    { bg: 'rgba(0,188,212,0.18)',   color: '#00BCD4' },
  'Fiverr':           { bg: 'rgba(16,181,46,0.18)',   color: '#10B52E' },
  'Remotive':         { bg: 'rgba(109,40,217,0.18)',  color: '#a78bfa' },
  'We Work Remotely': { bg: 'rgba(109,40,217,0.18)',  color: '#a78bfa' },
  'Remote.co':        { bg: 'rgba(109,40,217,0.18)',  color: '#a78bfa' },
  'Wellfound':        { bg: 'rgba(250,173,20,0.18)',  color: '#FAB014' },
  'AngelList':        { bg: 'rgba(250,173,20,0.18)',  color: '#FAB014' },
  'Lemon.io':         { bg: 'rgba(255,215,0,0.18)',   color: '#DAA520' },
  'Arc.dev':          { bg: 'rgba(150,30,220,0.18)',  color: '#c060f0' },
  'Contra':           { bg: 'rgba(255,80,80,0.18)',   color: '#FF5050' },
  'Topcoder':         { bg: 'rgba(60,150,255,0.18)',  color: '#3C96FF' },
  'FlexJobs':         { bg: 'rgba(40,200,140,0.18)',  color: '#28C88C' },
  'Freelance':        { bg: 'rgba(109,40,217,0.15)',  color: '#a78bfa' },
};

function platformStyle(platform) {
  return PLATFORM_COLORS[platform] || PLATFORM_COLORS['Freelance'];
}

// ── Project Detail Panel ───────────────────────────────────────────────────

function ProjectDetailPanel({ data }) {
  return (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', marginTop: '18px', paddingTop: '18px', display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Match Score */}
      {typeof data.match_score === 'number' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BarChart2 size={14} style={{ color: 'var(--primary-glow)', flexShrink: 0 }} />
          <div style={{ flex: 1, height: '5px', background: 'rgba(255,255,255,0.1)', borderRadius: '99px', overflow: 'hidden' }}>
            <div style={{ width: `${data.match_score}%`, height: '100%', background: scoreColor(data.match_score), borderRadius: '99px', transition: 'width 0.6s ease' }} />
          </div>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: scoreColor(data.match_score), minWidth: 32 }}>
            {data.match_score}
          </span>
        </div>
      )}

      {data.match_summary && (
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.6, background: 'rgba(255,255,255,0.04)', padding: '10px 12px', borderRadius: '8px', margin: 0 }}>
          {data.match_summary}
        </p>
      )}

      {/* Budget + Duration */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {data.budget_display && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(34,197,94,0.1)', padding: '4px 10px', borderRadius: '8px' }}>
            <DollarSign size={12} style={{ color: '#4ade80' }} />
            <span style={{ fontSize: '0.8rem', color: '#4ade80', fontWeight: 600 }}>{data.budget_display}</span>
            {data.budget_type && data.budget_type !== 'unknown' && (
              <span style={{ fontSize: '0.68rem', color: 'rgba(74,222,128,0.7)' }}>
                {data.budget_type === 'hourly' ? '/ hora' : 'fijo'}
              </span>
            )}
          </div>
        )}
        {data.duration && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', background: 'rgba(255,255,255,0.06)', padding: '4px 10px', borderRadius: '8px' }}>
            <Clock size={12} style={{ color: 'var(--text-muted)' }} />
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{data.duration}</span>
          </div>
        )}
        {data.experience_level && (
          <div style={{ padding: '4px 10px', borderRadius: '8px', background: 'rgba(109,40,217,0.15)', fontSize: '0.75rem', color: '#a78bfa', textTransform: 'capitalize' }}>
            {data.experience_level}
          </div>
        )}
      </div>

      {/* Description */}
      {data.description_summary && (
        <p style={{ fontSize: '0.82rem', color: 'var(--text-main)', lineHeight: 1.65, margin: 0 }}>
          {data.description_summary}
        </p>
      )}

      {/* Skills */}
      {(data.skills_required || []).length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '7px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Zap size={11} /> Stack requerido
          </p>
          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
            {data.skills_required.map((skill, i) => (
              <span key={i} style={{ fontSize: '0.7rem', background: 'rgba(109,40,217,0.2)', color: '#a78bfa', padding: '3px 9px', borderRadius: '5px' }}>
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Client info */}
      {(data.client_location || data.client_rating || data.client_spent || data.proposals_count) && (
        <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '10px', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '7px' }}>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0, display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Users size={11} /> Cliente
          </p>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {data.client_location && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <MapPin size={11} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: '0.78rem', color: 'var(--text-main)' }}>{data.client_location}</span>
              </div>
            )}
            {data.client_rating && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Star size={11} style={{ color: '#eab308' }} />
                <span style={{ fontSize: '0.78rem', color: '#eab308', fontWeight: 600 }}>{data.client_rating}</span>
              </div>
            )}
            {data.client_spent && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <DollarSign size={11} style={{ color: '#4ade80' }} />
                <span style={{ fontSize: '0.78rem', color: 'var(--text-main)' }}>{data.client_spent} gastado</span>
              </div>
            )}
            {data.proposals_count && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Shield size={11} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{data.proposals_count} propuestas</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Green flags */}
      {(data.green_flags || []).length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', color: '#4ade80', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <CheckCircle size={11} /> Señales positivas
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {data.green_flags.map((flag, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '7px' }}>
                <CheckCircle size={11} style={{ color: '#4ade80', flexShrink: 0, marginTop: '2px' }} />
                <span style={{ fontSize: '0.78rem', color: 'var(--text-main)', lineHeight: 1.5 }}>{flag}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Red flags */}
      {(data.red_flags || []).length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', color: '#f87171', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <AlertTriangle size={11} /> Puntos de atención
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {data.red_flags.map((flag, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '7px' }}>
                <AlertTriangle size={11} style={{ color: '#f87171', flexShrink: 0, marginTop: '2px' }} />
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>{flag}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pitch suggestion */}
      {data.pitch_suggestion && (
        <div style={{ background: 'linear-gradient(135deg,rgba(0,188,212,0.08),rgba(109,40,217,0.12))', borderRadius: '10px', padding: '14px', border: '1px solid rgba(0,188,212,0.2)' }}>
          <p style={{ fontSize: '0.7rem', color: '#67e8f9', marginBottom: '7px', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Send size={10} /> Apertura de propuesta sugerida
          </p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-main)', lineHeight: 1.7, fontStyle: 'italic', margin: 0 }}>
            {data.pitch_suggestion}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Application Modal ─────────────────────────────────────────────────────

function ApplicationModal({ project, searchPrompt, sessionId, onClose, onSaved }) {
  const [phase, setPhase] = useState('generating'); // generating | editing | saving | done
  const [proposalText, setProposalText] = useState('');
  const [copied, setCopied] = useState(false);
  const [ownerName, setOwnerName] = useState('');
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.post('/projects/generate-proposal', {
          title: project.title,
          platform: project.platform,
          url: project.url,
          description: project.description || '',
          skills_required: project.skills_required || project.skills || [],
          budget_display: project.budget_display || project.budget || '',
          budget_type: project.budget_type || '',
          session_id: sessionId || '',
        });
        setProposalText(res.data.proposal_text);
        setOwnerName(res.data.owner_name || '');
        setPhase('editing');
      } catch (e) {
        setError('No se pudo generar la propuesta. Intenta de nuevo.');
        setPhase('editing');
      }
    })();
  }, []);

  const wordCount = proposalText.trim().split(/\s+/).filter(Boolean).length;

  const handleCopyAndOpen = async () => {
    setPhase('saving');
    try {
      await navigator.clipboard.writeText(proposalText);
      setCopied(true);
      await api.post('/projects/applications', {
        project_title: project.title,
        platform: project.platform,
        project_url: project.url,
        session_id: sessionId || '',
        proposal_text: proposalText,
        status: 'applied',
      });
      window.open(project.url, '_blank', 'noopener,noreferrer');
      onSaved(project.url, 'applied');
      setPhase('done');
    } catch {
      setPhase('editing');
    }
  };

  const handleSaveDraft = async () => {
    setPhase('saving');
    try {
      await api.post('/projects/applications', {
        project_title: project.title,
        platform: project.platform,
        project_url: project.url,
        session_id: sessionId || '',
        proposal_text: proposalText,
        status: 'draft',
      });
      onSaved(project.url, 'draft');
      onClose();
    } catch {
      setPhase('editing');
    }
  };

  const pStyle = platformStyle(project.platform);

  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div className="glass" style={{
        width: '100%', maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto',
        padding: '28px', borderRadius: '18px',
        border: '1px solid rgba(0,188,212,0.2)',
        boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
        display: 'flex', flexDirection: 'column', gap: '20px',
      }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <div style={{ padding: '6px', borderRadius: '9px', background: 'linear-gradient(135deg,rgba(8,145,178,0.3),rgba(109,40,217,0.3))', display: 'flex' }}>
                <FileText size={16} style={{ color: '#67e8f9' }} />
              </div>
              <h2 style={{ fontSize: '1rem', margin: 0 }}>Propuesta de aplicación</h2>
            </div>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {project.title.length > 50 ? project.title.slice(0, 50) + '…' : project.title}
              </span>
              <span style={{ fontSize: '0.65rem', padding: '2px 8px', borderRadius: '999px', background: pStyle.bg, color: pStyle.color }}>
                {project.platform}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px', borderRadius: '8px', display: 'flex', flexShrink: 0 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Generating state */}
        {phase === 'generating' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', padding: '32px 0' }}>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', inset: -10, background: 'rgba(8,145,178,0.2)', filter: 'blur(18px)', borderRadius: '50%', animation: 'pulse-cyan 2s infinite' }} />
              <Loader2 size={36} style={{ color: '#0891b2', animation: 'spin 1.5s linear infinite', position: 'relative' }} />
            </div>
            <div style={{ textAlign: 'center' }}>
              <p style={{ fontWeight: 600, marginBottom: '4px' }}>Generando propuesta…</p>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                El agente está redactando una propuesta personalizada para esta oferta
              </p>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '10px', padding: '12px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <AlertTriangle size={15} style={{ color: '#f87171', flexShrink: 0, marginTop: '1px' }} />
            <p style={{ fontSize: '0.82rem', color: '#f87171', margin: 0 }}>{error}</p>
          </div>
        )}

        {/* Editing state */}
        {(phase === 'editing' || phase === 'saving') && !error && (
          <>
            {/* Instructions */}
            <div style={{ background: 'rgba(0,188,212,0.06)', border: '1px solid rgba(0,188,212,0.12)', borderRadius: '10px', padding: '11px 14px', display: 'flex', gap: '9px', alignItems: 'flex-start' }}>
              <CheckCircle size={14} style={{ color: '#67e8f9', flexShrink: 0, marginTop: '1px' }} />
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.55 }}>
                Revisa y edita la propuesta. Al hacer clic en <strong style={{ color: '#67e8f9' }}>Copiar y abrir</strong>, se copiará al portapapeles y se abrirá la página del proyecto para que la pegues directamente.
              </p>
            </div>

            {/* Textarea */}
            <div style={{ position: 'relative' }}>
              <textarea
                ref={textareaRef}
                value={proposalText}
                onChange={e => setProposalText(e.target.value)}
                rows={12}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(0,188,212,0.18)',
                  borderRadius: '12px', padding: '14px 16px', color: 'var(--text-main)',
                  fontSize: '0.85rem', lineHeight: 1.7, fontFamily: 'inherit',
                  resize: 'vertical', outline: 'none',
                  transition: 'border-color 0.15s',
                }}
                onFocus={e => e.target.style.borderColor = 'rgba(0,188,212,0.45)'}
                onBlur={e => e.target.style.borderColor = 'rgba(0,188,212,0.18)'}
                disabled={phase === 'saving'}
              />
              {/* Word count */}
              <div style={{
                position: 'absolute', bottom: '10px', right: '12px',
                fontSize: '0.68rem', color: wordCount > 230 ? '#f87171' : 'var(--text-muted)',
                background: 'rgba(10,10,20,0.85)', padding: '2px 7px', borderRadius: '5px',
              }}>
                {wordCount} palabras {wordCount > 230 && '⚠ muy largo'}
              </div>
            </div>

            {/* Owner name hint */}
            {ownerName && (
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '-8px 0 0 2px' }}>
                Firmado como: <strong style={{ color: 'var(--text-main)' }}>{ownerName}</strong> — configurable en ICP Config
              </p>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button
                onClick={handleCopyAndOpen}
                disabled={phase === 'saving' || !proposalText.trim()}
                style={{
                  flex: 2, minWidth: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                  padding: '12px 20px', borderRadius: '11px', border: 'none',
                  background: phase === 'saving'
                    ? 'rgba(8,145,178,0.4)'
                    : 'linear-gradient(135deg, #0891b2, #6D28D9)',
                  color: '#fff', fontWeight: 700, cursor: phase === 'saving' ? 'not-allowed' : 'pointer',
                  fontSize: '0.88rem',
                }}
              >
                {phase === 'saving'
                  ? <Loader2 size={15} style={{ animation: 'spin 1.2s linear infinite' }} />
                  : copied ? <Check size={15} /> : <Copy size={15} />}
                {phase === 'saving' ? 'Guardando…' : `Copiar y abrir ${project.platform}`}
              </button>

              <button
                onClick={handleSaveDraft}
                disabled={phase === 'saving' || !proposalText.trim()}
                style={{
                  flex: 1, minWidth: '140px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                  padding: '12px 16px', borderRadius: '11px',
                  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
                  color: 'var(--text-muted)', cursor: phase === 'saving' ? 'not-allowed' : 'pointer',
                  fontSize: '0.82rem',
                }}
              >
                <FileText size={14} /> Guardar borrador
              </button>

              <button
                onClick={onClose}
                disabled={phase === 'saving'}
                style={{
                  padding: '12px 16px', borderRadius: '11px',
                  background: 'transparent', border: '1px solid rgba(255,255,255,0.08)',
                  color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.82rem',
                }}
              >
                Cancelar
              </button>
            </div>
          </>
        )}

        {/* Done state */}
        {phase === 'done' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', padding: '24px 0', textAlign: 'center' }}>
            <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: 'rgba(34,197,94,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(34,197,94,0.3)' }}>
              <CheckCircle size={28} style={{ color: '#4ade80' }} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.05rem', marginBottom: '6px' }}>¡Aplicación registrada!</h3>
              <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                La propuesta fue copiada al portapapeles y la página del proyecto se abrió en una nueva pestaña. Pégala en el formulario de {project.platform}.
              </p>
            </div>
            <button
              onClick={onClose}
              style={{ padding: '10px 28px', borderRadius: '10px', background: 'linear-gradient(135deg,#0891b2,#6D28D9)', border: 'none', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: '0.88rem' }}
            >
              Cerrar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Project Card ───────────────────────────────────────────────────────────

function ProjectCard({ project, searchPrompt, sessionId, preloadedDetail, applicationStatus, onApply }) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(preloadedDetail || null);
  const [error, setError] = useState(null);

  const pStyle = platformStyle(project.platform);

  const handleAnalyze = async () => {
    if (detail) { setExpanded(v => !v); return; }
    setExpanded(true);
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/projects/analyze', {
        title: project.title,
        platform: project.platform,
        url: project.url,
        budget: project.budget || '',
        budget_type: project.budget_type || '',
        description: project.description || '',
        search_prompt: searchPrompt,
        session_id: sessionId || '',
      });
      setDetail(res.data.result);
    } catch {
      setError('Error al analizar. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  // Merge detail data into project for proposal generation
  const enrichedProject = detail ? { ...project, ...detail } : project;

  const appliedStyle = applicationStatus === 'applied'
    ? { bg: 'rgba(34,197,94,0.15)', color: '#4ade80', label: 'Aplicado' }
    : applicationStatus === 'draft'
    ? { bg: 'rgba(234,179,8,0.12)', color: '#eab308', label: 'Borrador' }
    : null;

  return (
    <div className="glass" style={{ padding: '20px', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', marginBottom: '10px' }}>
        <div style={{ minWidth: 0 }}>
          <h3 style={{ fontSize: '0.92rem', lineHeight: 1.4, marginBottom: '6px' }}>{project.title}</h3>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{
              fontSize: '0.65rem', fontWeight: 700, padding: '2px 9px', borderRadius: '999px',
              background: pStyle.bg, color: pStyle.color, letterSpacing: '0.02em',
            }}>
              {project.platform}
            </span>
            {project.budget_type && project.budget_type !== 'unknown' && (
              <span style={{
                fontSize: '0.62rem', padding: '2px 8px', borderRadius: '999px',
                background: project.budget_type === 'hourly' ? 'rgba(234,179,8,0.15)' : 'rgba(34,197,94,0.12)',
                color: project.budget_type === 'hourly' ? '#eab308' : '#4ade80',
              }}>
                {project.budget_type === 'hourly' ? 'Por hora' : 'Precio fijo'}
              </span>
            )}
            {detail && !appliedStyle && (
              <span style={{ fontSize: '0.62rem', background: 'rgba(8,145,178,0.15)', color: '#67e8f9', padding: '2px 8px', borderRadius: '999px' }}>
                Analizado
              </span>
            )}
            {appliedStyle && (
              <span style={{ fontSize: '0.62rem', background: appliedStyle.bg, color: appliedStyle.color, padding: '2px 8px', borderRadius: '999px', display: 'flex', alignItems: 'center', gap: '3px' }}>
                <CheckCircle size={9} /> {appliedStyle.label}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Budget display */}
      {project.budget && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '8px' }}>
          <DollarSign size={12} style={{ color: '#4ade80', flexShrink: 0 }} />
          <span style={{ fontSize: '0.82rem', color: '#4ade80', fontWeight: 600 }}>{project.budget}</span>
        </div>
      )}

      {/* Description */}
      {project.description && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.55, marginBottom: '10px', flexGrow: 1 }}>
          {project.description}
        </p>
      )}

      {/* Skills preview */}
      {(project.skills || []).length > 0 && (
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '10px' }}>
          {project.skills.slice(0, 4).map((s, i) => (
            <span key={i} style={{ fontSize: '0.65rem', background: 'rgba(109,40,217,0.18)', color: '#a78bfa', padding: '2px 7px', borderRadius: '4px' }}>
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Expanded states */}
      {expanded && loading && (
        <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'center', padding: '16px 0' }}>
          <Loader2 size={20} style={{ color: 'var(--primary)', animation: 'spin 1.2s linear infinite' }} />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Analizando proyecto…</span>
        </div>
      )}
      {expanded && !loading && error && (
        <p style={{ marginTop: '12px', fontSize: '0.8rem', color: '#f87171' }}>{error}</p>
      )}
      {expanded && !loading && detail && <ProjectDetailPanel data={detail} />}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '7px', marginTop: '14px' }}>
        {project.url && (
          <a href={project.url} target="_blank" rel="noopener noreferrer"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '9px 12px', borderRadius: '9px', background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-muted)', textDecoration: 'none' }}>
            <ExternalLink size={13} />
          </a>
        )}
        <button onClick={handleAnalyze}
          style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '9px', borderRadius: '9px', background: 'rgba(8,145,178,0.15)', border: '1px solid rgba(8,145,178,0.2)', color: '#67e8f9', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
          {loading
            ? <Loader2 size={13} style={{ animation: 'spin 1.2s linear infinite' }} />
            : detail ? (expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />) : <Lightbulb size={13} />}
          {loading ? 'Analizando…' : detail ? (expanded ? 'Ocultar' : 'Ver análisis') : 'Analizar'}
        </button>
        <button
          onClick={() => onApply(enrichedProject)}
          style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
            padding: '9px', borderRadius: '9px', border: 'none',
            background: appliedStyle
              ? 'rgba(34,197,94,0.12)'
              : 'linear-gradient(135deg, #0891b2, #6D28D9)',
            color: appliedStyle ? '#4ade80' : '#fff',
            cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700,
          }}
        >
          {appliedStyle ? <CheckCircle size={13} /> : <Send size={13} />}
          {appliedStyle ? appliedStyle.label : 'Aplicar'}
        </button>
      </div>
    </div>
  );
}

// ── History Sidebar ────────────────────────────────────────────────────────

function ProjectHistorySidebar({ open, onToggle, activeSessionId, onSelectSession, onNewSearch }) {
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
      const res = await api.get(`/projects/sessions?${params}`);
      setSessions(res.data.sessions || []);
      setTotal(res.data.total || 0);
    } catch { /* silent */ } finally {
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
      await api.delete(`/projects/sessions/${sid}`);
      setSessions(s => s.filter(x => x._id !== sid));
      setTotal(t => t - 1);
      if (activeSessionId === sid) onNewSearch();
    } catch { /* silent */ }
  };

  const sidebarW = open ? 280 : 60;

  return (
    <div style={{
      width: sidebarW, minWidth: sidebarW, height: '100vh', position: 'sticky', top: 0,
      background: 'rgba(10,10,20,0.96)', backdropFilter: 'blur(20px)',
      borderRight: '1px solid rgba(0,188,212,0.1)',
      display: 'flex', flexDirection: 'column', transition: 'width 0.25s ease', overflow: 'hidden',
      flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{ padding: open ? '20px 16px 12px' : '20px 12px 12px', display: 'flex', alignItems: 'center', justifyContent: open ? 'space-between' : 'center', borderBottom: '1px solid rgba(0,188,212,0.08)' }}>
        {open && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={16} style={{ color: '#67e8f9' }} />
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Historial</span>
            {total > 0 && (
              <span style={{ fontSize: '0.65rem', background: 'rgba(0,188,212,0.2)', color: '#67e8f9', padding: '1px 7px', borderRadius: '999px' }}>{total}</span>
            )}
          </div>
        )}
        <button onClick={onToggle} style={{ background: 'rgba(0,188,212,0.08)', border: 'none', color: '#67e8f9', cursor: 'pointer', padding: '6px', borderRadius: '8px', display: 'flex' }}>
          {open ? <ChevronLeft size={16} /> : <History size={16} />}
        </button>
      </div>

      {open && (
        <>
          {/* New search button */}
          <div style={{ padding: '12px 14px 8px' }}>
            <button onClick={onNewSearch}
              style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '8px', padding: '9px 12px', borderRadius: '10px', background: 'linear-gradient(135deg, #0891b2, #6D28D9)', border: 'none', color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600, justifyContent: 'center' }}>
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
                style={{ width: '100%', background: 'rgba(0,188,212,0.05)', border: '1px solid rgba(0,188,212,0.12)', borderRadius: '8px', padding: '7px 10px 7px 30px', color: 'var(--text-main)', fontSize: '0.78rem', outline: 'none', boxSizing: 'border-box' }}
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
                <Loader2 size={18} style={{ color: '#0891b2', animation: 'spin 1.2s linear infinite' }} />
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
                  background: activeSessionId === s._id ? 'rgba(8,145,178,0.15)' : 'rgba(255,255,255,0.03)',
                  border: activeSessionId === s._id ? '1px solid rgba(8,145,178,0.35)' : '1px solid transparent',
                  transition: 'all 0.15s',
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
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>{s.result_count} proyectos</span>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {total > 20 && (
            <div style={{ padding: '10px 14px', borderTop: '1px solid rgba(0,188,212,0.08)', display: 'flex', justifyContent: 'center', gap: '8px' }}>
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

// ── Filter chips ───────────────────────────────────────────────────────────

function FilterChip({ label, active, onClick, color }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '5px 14px', borderRadius: '999px', border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: active ? 700 : 400,
        background: active ? (color || 'rgba(8,145,178,0.3)') : 'rgba(255,255,255,0.06)',
        color: active ? (color ? '#fff' : '#67e8f9') : 'var(--text-muted)',
        transition: 'all 0.15s',
        outline: active ? `1px solid ${color || 'rgba(8,145,178,0.5)'}` : '1px solid transparent',
      }}
    >
      {label}
    </button>
  );
}

// ── FreelanceSearch Page ───────────────────────────────────────────────────

export default function FreelanceSearch() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [prompt, setPrompt] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [sessionId, setSessionId] = useState('');
  const [lastPrompt, setLastPrompt] = useState('');
  const [activeSessionId, setActiveSessionId] = useState('');
  const [loadingSession, setLoadingSession] = useState(false);
  const [preloadedAnalyses, setPreloadedAnalyses] = useState({});

  // Filters
  const [platformFilter, setPlatformFilter] = useState('Todos');
  const [budgetFilter, setBudgetFilter] = useState('Todos');

  // Application tracking: url → 'applied' | 'draft'
  const [appliedMap, setAppliedMap] = useState({});

  // Modal
  const [modalProject, setModalProject] = useState(null);

  // Load existing applications on mount
  useEffect(() => {
    api.get('/projects/applications')
      .then(res => {
        const map = {};
        (res.data.applications || []).forEach(a => {
          if (a.project_url) map[a.project_url] = a.status;
        });
        setAppliedMap(map);
      })
      .catch(() => {});
  }, []);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setIsSearching(true);
    setResults([]);
    setSessionId('');
    setActiveSessionId('');
    setPreloadedAnalyses({});
    setLastPrompt(prompt.trim());
    setPlatformFilter('Todos');
    setBudgetFilter('Todos');
    try {
      const res = await api.post('/projects/search', { prompt: prompt.trim() });
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
      const res = await api.get(`/projects/sessions/${sid}`);
      const session = res.data.session || {};
      const analyzed = res.data.analyzed_projects || [];
      setResults(session.results || []);
      setLastPrompt(session.prompt || '');
      setPrompt(session.prompt || '');
      const map = {};
      analyzed.forEach(p => { if (p.url) map[p.url] = p; });
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
    setPlatformFilter('Todos');
    setBudgetFilter('Todos');
  };

  const handleApplicationSaved = (projectUrl, status) => {
    setAppliedMap(prev => ({ ...prev, [projectUrl]: status }));
  };

  // Derived filter data
  const platforms = ['Todos', ...Array.from(new Set(results.map(r => r.platform))).sort()];
  const filteredResults = results.filter(r => {
    const matchPlatform = platformFilter === 'Todos' || r.platform === platformFilter;
    const matchBudget = budgetFilter === 'Todos'
      || (budgetFilter === 'fixed' && r.budget_type === 'fixed')
      || (budgetFilter === 'hourly' && r.budget_type === 'hourly');
    return matchPlatform && matchBudget;
  });

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes pulse-cyan { 0%,100%{opacity:.4;transform:scale(1)} 50%{opacity:.9;transform:scale(1.12)} }
      `}</style>

      {/* Application modal */}
      {modalProject && (
        <ApplicationModal
          project={modalProject}
          searchPrompt={lastPrompt}
          sessionId={sessionId}
          onClose={() => setModalProject(null)}
          onSaved={handleApplicationSaved}
        />
      )}

      <ProjectHistorySidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(v => !v)}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSearch={handleNewSearch}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh', overflow: 'auto' }}>
        <main style={{ flex: 1, padding: '28px', maxWidth: '1100px', width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>

          {/* Hero */}
          <section className="glass" style={{ padding: '36px 40px', textAlign: 'center', marginBottom: '32px', borderColor: 'rgba(0,188,212,0.15)', position: 'relative', overflow: 'hidden' }}>
            {/* Subtle cyan glow behind */}
            <div style={{ position: 'absolute', top: '-40px', right: '-40px', width: '220px', height: '220px', background: 'radial-gradient(circle, rgba(8,145,178,0.12) 0%, transparent 70%)', pointerEvents: 'none' }} />

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', marginBottom: '14px' }}>
              <div style={{ padding: '10px', borderRadius: '14px', background: 'linear-gradient(135deg, rgba(8,145,178,0.3), rgba(109,40,217,0.3))', display: 'flex' }}>
                <Briefcase size={22} style={{ color: '#67e8f9' }} />
              </div>
              <h1 style={{ fontSize: '1.9rem', margin: 0 }}>
                Proyectos <span style={{ background: 'linear-gradient(90deg,#67e8f9,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Freelance</span>
              </h1>
            </div>

            <p style={{ color: 'var(--text-muted)', marginBottom: '28px', maxWidth: '580px', margin: '0 auto 28px', fontSize: '0.9rem', lineHeight: 1.6 }}>
              Describe el tipo de proyecto o stack que buscas. El agente escanea Upwork, Freelancer, Toptal, Guru y más plataformas a nivel mundial.
            </p>

            <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px', maxWidth: '680px', margin: '0 auto' }}>
              <input
                type="text"
                className="input-field"
                style={{ flex: 1, padding: '14px 20px', fontSize: '0.95rem', borderRadius: '12px', borderColor: 'rgba(0,188,212,0.2)' }}
                placeholder="Ej: Desarrollo de dashboard React con Node.js backend…"
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
              />
              <button
                type="submit"
                style={{ padding: '14px 28px', borderRadius: '12px', border: 'none', background: 'linear-gradient(135deg, #0891b2, #6D28D9)', color: '#fff', fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem' }}
                disabled={isSearching}
              >
                {isSearching
                  ? <Loader2 size={17} style={{ animation: 'spin 1.2s linear infinite' }} />
                  : <><Search size={16} /> Buscar</>}
              </button>
            </form>
          </section>

          {/* Loading session */}
          {loadingSession && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
              <Loader2 size={28} style={{ color: '#0891b2', animation: 'spin 1.2s linear infinite' }} />
            </div>
          )}

          {/* Searching state */}
          {isSearching && (
            <div className="glass" style={{ padding: '36px', textAlign: 'center', maxWidth: '380px', margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', borderColor: 'rgba(0,188,212,0.15)' }}>
              <div style={{ position: 'relative' }}>
                <div style={{ position: 'absolute', inset: -12, background: 'rgba(8,145,178,0.25)', filter: 'blur(20px)', borderRadius: '50%', animation: 'pulse-cyan 2s infinite ease-in-out' }} />
                <Spinner size={40} color="#0891b2" />
              </div>
              <div>
                <h3 style={{ marginBottom: '6px', fontSize: '1rem' }}>Buscando proyectos…</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', lineHeight: 1.5 }}>
                  Escaneando Upwork, Freelancer, Toptal, Guru y más. Haz clic en <strong>"Analizar proyecto"</strong> para ver detalles y score de compatibilidad.
                </p>
              </div>
            </div>
          )}

          {/* Results */}
          {!isSearching && !loadingSession && results.length > 0 && (
            <>
              {/* Filters + count */}
              <div style={{ marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
                    <strong style={{ color: 'var(--text-main)' }}>{filteredResults.length}</strong>
                    {filteredResults.length !== results.length && ` de ${results.length}`} proyectos
                    {lastPrompt && <span> para <em>"{lastPrompt}"</em></span>}
                    {activeSessionId && (
                      <span style={{ marginLeft: '8px', fontSize: '0.65rem', background: 'rgba(8,145,178,0.15)', color: '#67e8f9', padding: '2px 8px', borderRadius: '999px' }}>guardado</span>
                    )}
                  </p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                    Clic en <strong style={{ color: '#67e8f9' }}>Analizar proyecto</strong> para ver score y propuesta
                  </p>
                </div>

                {/* Platform chips */}
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginRight: '2px' }}>Plataforma:</span>
                  {platforms.map(p => (
                    <FilterChip
                      key={p}
                      label={p}
                      active={platformFilter === p}
                      onClick={() => setPlatformFilter(p)}
                    />
                  ))}
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: '10px', marginRight: '2px' }}>Tipo:</span>
                  {[
                    { id: 'Todos', label: 'Todos' },
                    { id: 'fixed', label: 'Precio fijo' },
                    { id: 'hourly', label: 'Por hora' },
                  ].map(opt => (
                    <FilterChip
                      key={opt.id}
                      label={opt.label}
                      active={budgetFilter === opt.id}
                      onClick={() => setBudgetFilter(opt.id)}
                    />
                  ))}
                </div>
              </div>

              {filteredResults.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
                  {filteredResults.map(project => (
                    <ProjectCard
                      key={project.id || project.url}
                      project={project}
                      searchPrompt={lastPrompt}
                      sessionId={sessionId}
                      preloadedDetail={preloadedAnalyses[project.url] || null}
                      applicationStatus={appliedMap[project.url] || null}
                      onApply={setModalProject}
                    />
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                  <p style={{ fontSize: '0.9rem' }}>Sin proyectos con los filtros seleccionados</p>
                </div>
              )}
            </>
          )}

          {/* Empty state */}
          {!isSearching && !loadingSession && results.length === 0 && (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
              <Briefcase size={40} style={{ opacity: 0.2, marginBottom: '16px', color: '#67e8f9' }} />
              <p style={{ fontSize: '0.9rem', marginBottom: '8px' }}>Describe el tipo de proyecto o tecnología que buscas</p>
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap', marginTop: '16px' }}>
                {['React dashboard', 'Python scraping', 'Mobile app Flutter', 'E-commerce Shopify'].map(ex => (
                  <button
                    key={ex}
                    onClick={() => setPrompt(ex)}
                    style={{ padding: '5px 14px', borderRadius: '999px', background: 'rgba(0,188,212,0.08)', border: '1px solid rgba(0,188,212,0.15)', color: '#67e8f9', cursor: 'pointer', fontSize: '0.78rem' }}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
