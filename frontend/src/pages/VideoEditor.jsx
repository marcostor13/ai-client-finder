import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Upload, Video, Scissors, Captions, Sliders, Play, Download,
  PlayCircle, Camera, CheckCircle, AlertTriangle, Loader2, X,
  ChevronRight, ChevronLeft, Globe, Link, Trash2, RefreshCw,
  Zap, Music, Clock, FileVideo, Send, Eye, Settings,
} from 'lucide-react';
import Spinner from '../components/Spinner';
import api from '../api';
import { useNotify, useConfirm } from '../context/NotificationContext';

// ── Constants ──────────────────────────────────────────────────────────────────

const PLATFORM_SPECS = {
  tiktok:         { label: 'TikTok',          ratio: '9:16', maxSec: null,  icon: '🎵', color: '#69C9D0' },
  reels:          { label: 'Instagram Reels',  ratio: '9:16', maxSec: 90,   icon: '📸', color: '#E1306C' },
  stories:        { label: 'Instagram Stories',ratio: '9:16', maxSec: 60,   icon: '🟣', color: '#833AB4' },
  youtube:        { label: 'YouTube',          ratio: '16:9', maxSec: null,  icon: '▶️', color: '#FF0000' },
  shorts:         { label: 'YouTube Shorts',   ratio: '9:16', maxSec: 60,   icon: '⚡', color: '#FF0000' },
  instagram_feed: { label: 'Instagram Feed',   ratio: '1:1',  maxSec: 60,   icon: '🖼️', color: '#E1306C' },
};

const SUBTITLE_STYLES = [
  {
    id: 'tiktok',
    label: 'TikTok Bold',
    desc: 'Palabra por palabra · Impact 130pt · borde 9px · pop elástico viral',
    preview: { font: 'Impact', size: 36, color: '#fff', outline: '5px black' },
  },
  {
    id: 'bold_yellow',
    label: 'Bold Yellow',
    desc: 'Ventana 3 palabras · Impact 108pt · activa en amarillo (CapCut)',
    preview: { font: 'Impact', size: 32, color: '#FFE000', outline: '5px black' },
  },
  {
    id: 'cinematic',
    label: 'Cinematic',
    desc: 'Palabra por palabra · Impact 124pt · MAYÚSCULAS · borde violeta luminoso',
    preview: { font: 'Impact', size: 34, color: '#fff', outline: '5px #6D28D9' },
  },
  {
    id: 'minimal',
    label: 'Minimal',
    desc: 'Grupos de 3 palabras · Arial Black 84pt · fade + sombra suave',
    preview: { font: 'Arial Black', size: 26, color: '#fff', outline: '2px black' },
  },
];

const STEPS = ['upload', 'configure', 'processing', 'preview', 'publish'];

const STEP_LABELS = {
  upload: 'Subir video',
  configure: 'Configurar',
  processing: 'Procesando',
  preview: 'Preview',
  publish: 'Publicar',
};

const PROCESSING_STEPS = {
  queued:            { label: 'En cola…',                pct: 2  },
  downloading:       { label: 'Descargando archivo…',    pct: 8  },
  silence_detection: { label: 'Detectando silencios…',   pct: 15 },
  silence_removal:   { label: 'Cortando silencios…',     pct: 25 },
  transcription:     { label: 'Transcribiendo audio…',   pct: 45 },
  subtitles:         { label: 'Generando subtítulos…',   pct: 60 },
  images:            { label: 'Mezclando imágenes…',     pct: 63 },
  formatting:        { label: 'Formateando plataformas…',pct: 75 },
  done:              { label: '¡Listo!',                  pct: 100},
};

function fmtSec(s) {
  if (!s) return '—';
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

function fmtBytes(b) {
  if (!b) return '—';
  if (b > 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024).toFixed(0)} KB`;
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = (Date.now() - d) / 1000;
  if (diff < 60)     return 'Hace un momento';
  if (diff < 3600)   return `Hace ${Math.floor(diff / 60)}m`;
  if (diff < 86400)  return `Hace ${Math.floor(diff / 3600)}h`;
  if (diff < 604800) return `Hace ${Math.floor(diff / 86400)}d`;
  return d.toLocaleDateString('es-PE', { day: 'numeric', month: 'short' });
}

// ── Step indicator ─────────────────────────────────────────────────────────────

function StepBar({ current }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: '36px', justifyContent: 'center' }}>
      {STEPS.map((s, i) => {
        const idx = STEPS.indexOf(current);
        const done = i < idx;
        const active = i === idx;
        return (
          <div key={s} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px',
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: done ? '#22c55e' : active ? 'var(--primary)' : 'rgba(255,255,255,0.08)',
                border: `2px solid ${done ? '#22c55e' : active ? 'var(--primary)' : 'rgba(255,255,255,0.15)'}`,
                fontSize: '0.75rem', fontWeight: 700, color: done || active ? '#fff' : 'var(--text-muted)',
                transition: 'all 0.3s',
              }}>
                {done ? <CheckCircle size={14} /> : i + 1}
              </div>
              <span style={{
                fontSize: '0.62rem', color: active ? 'var(--text-main)' : 'var(--text-muted)',
                whiteSpace: 'nowrap', fontWeight: active ? 700 : 400,
              }}>
                {STEP_LABELS[s]}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                width: 48, height: 2, margin: '0 4px 18px',
                background: done ? '#22c55e' : 'rgba(255,255,255,0.08)',
                transition: 'background 0.3s',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Step 1: Upload ─────────────────────────────────────────────────────────────

function UploadStep({ onFileSelected }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleFile = (file) => {
    if (!file || !file.type.startsWith('video/')) return;
    onFileSelected(file);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '24px' }}>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
        onClick={() => inputRef.current?.click()}
        style={{
          width: '100%', maxWidth: '520px', minHeight: '220px',
          border: `2px dashed ${dragging ? '#a78bfa' : 'rgba(109,40,217,0.35)'}`,
          borderRadius: '20px', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: '16px',
          cursor: 'pointer', transition: 'all 0.2s',
          background: dragging ? 'rgba(109,40,217,0.08)' : 'rgba(255,255,255,0.03)',
        }}
      >
        <div style={{
          width: 64, height: 64, borderRadius: '16px',
          background: 'linear-gradient(135deg,rgba(109,40,217,0.3),rgba(76,29,149,0.3))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Upload size={28} style={{ color: '#a78bfa' }} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '4px' }}>
            Arrastra tu video aquí
          </p>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            o haz clic para seleccionar — MP4, MOV, AVI, WEBM · máx 500 MB
          </p>
        </div>
        <input
          ref={inputRef} type="file" accept="video/*" hidden
          onChange={e => handleFile(e.target.files[0])}
        />
      </div>

      {/* Format info */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center' }}>
        {Object.entries(PLATFORM_SPECS).map(([key, spec]) => (
          <div key={key} style={{
            padding: '6px 14px', borderRadius: '999px', fontSize: '0.72rem',
            background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)',
            display: 'flex', alignItems: 'center', gap: '5px',
          }}>
            <span>{spec.icon}</span> {spec.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Step 2: Configure ──────────────────────────────────────────────────────────

function ConfigureStep({ file, settings, onChange, onProcess, uploading, uploadProgress }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', maxWidth: '600px', width: '100%' }}>

      {/* Selected file info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', background: 'rgba(255,255,255,0.04)', borderRadius: '12px', padding: '14px 16px' }}>
        <FileVideo size={22} style={{ color: '#a78bfa', flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontWeight: 600, fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{fmtBytes(file.size)}</p>
        </div>
        <CheckCircle size={16} style={{ color: '#22c55e' }} />
      </div>

      {/* Silence settings */}
      <div className="glass" style={{ padding: '20px', borderRadius: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px' }}>
          <Scissors size={16} style={{ color: '#a78bfa' }} />
          <h3 style={{ fontSize: '0.92rem', margin: 0 }}>Eliminar silencios</h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Umbral de silencio</label>
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#a78bfa' }}>{settings.silence_threshold_db} dB</span>
            </div>
            <input type="range" min="-60" max="-20" step="1"
              value={settings.silence_threshold_db}
              onChange={e => onChange('silence_threshold_db', Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--primary)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              <span>-60 dB (más agresivo)</span><span>-20 dB (menos)</span>
            </div>
          </div>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Duración mínima a cortar</label>
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#a78bfa' }}>{settings.silence_min_duration}s</span>
            </div>
            <input type="range" min="0.2" max="3.0" step="0.1"
              value={settings.silence_min_duration}
              onChange={e => onChange('silence_min_duration', Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--primary)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              <span>0.2s (más cortes)</span><span>3.0s (menos cortes)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Subtitle settings */}
      <div className="glass" style={{ padding: '20px', borderRadius: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Captions size={16} style={{ color: '#a78bfa' }} />
            <h3 style={{ fontSize: '0.92rem', margin: 0 }}>Subtítulos animados</h3>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Activar</span>
            <input type="checkbox" checked={settings.subtitles_enabled}
              onChange={e => onChange('subtitles_enabled', e.target.checked)}
              style={{ accentColor: 'var(--primary)', width: 16, height: 16 }}
            />
          </label>
        </div>

        {settings.subtitles_enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {SUBTITLE_STYLES.map(style => (
              <div
                key={style.id}
                onClick={() => onChange('subtitle_style', style.id)}
                style={{
                  padding: '12px 14px', borderRadius: '10px', cursor: 'pointer',
                  border: settings.subtitle_style === style.id
                    ? '1px solid rgba(109,40,217,0.6)'
                    : '1px solid rgba(255,255,255,0.08)',
                  background: settings.subtitle_style === style.id
                    ? 'rgba(109,40,217,0.12)'
                    : 'rgba(255,255,255,0.03)',
                  display: 'flex', alignItems: 'center', gap: '14px',
                  transition: 'all 0.15s',
                }}
              >
                {/* Preview */}
                <div style={{
                  width: 80, height: 40, background: '#111', borderRadius: '6px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, overflow: 'hidden',
                }}>
                  <span style={{
                    fontFamily: style.preview.font, fontSize: style.preview.size / 2,
                    color: style.preview.color,
                    WebkitTextStroke: style.preview.outline,
                    textShadow: style.id === 'cinematic'
                      ? '0 0 8px #6D28D9, 2px 2px 4px #6D28D9'
                      : '1px 1px 3px rgba(0,0,0,0.8)',
                    textTransform: style.id === 'cinematic' ? 'uppercase' : 'none',
                    letterSpacing: style.id === 'cinematic' ? '0.05em' : 'normal',
                  }}>
                    {style.id === 'bold_yellow'
                      ? <><span style={{ color: '#C0C0C0', fontSize: '0.8em' }}>un </span>HOLA<span style={{ color: '#C0C0C0', fontSize: '0.8em' }}> más</span></>
                      : 'HOLA'
                    }
                  </span>
                </div>
                <div>
                  <p style={{ fontSize: '0.85rem', fontWeight: 600, margin: 0 }}>{style.label}</p>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0 }}>{style.desc}</p>
                </div>
                {settings.subtitle_style === style.id && (
                  <CheckCircle size={15} style={{ color: '#a78bfa', marginLeft: 'auto' }} />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Images toggle */}
      <div className="glass" style={{
        padding: '20px', borderRadius: '14px',
        border: settings.images_enabled ? '1px solid rgba(236,72,153,0.35)' : undefined,
        background: settings.images_enabled ? 'rgba(236,72,153,0.06)' : undefined,
        transition: 'all 0.2s',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Camera icon mosaic */}
            <div style={{
              width: 36, height: 36, borderRadius: '10px', flexShrink: 0,
              background: settings.images_enabled
                ? 'linear-gradient(135deg,#ec4899,#8b5cf6)'
                : 'rgba(255,255,255,0.08)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.2s',
              fontSize: '1.1rem',
            }}>
              🖼️
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <h3 style={{ fontSize: '0.92rem', margin: 0 }}>Imágenes con Ken Burns</h3>
                <span style={{
                  fontSize: '0.6rem', fontWeight: 700, padding: '2px 7px',
                  borderRadius: '999px', letterSpacing: '0.06em',
                  background: 'linear-gradient(135deg,#ec4899,#8b5cf6)',
                  color: '#fff',
                }}>NUEVO</span>
              </div>
              <p style={{ margin: '3px 0 0', fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                El 50% del video se reemplaza por imágenes relevantes con zoom y movimiento de cámara suave.
              </p>
            </div>
          </div>

          {/* Toggle switch */}
          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', flexShrink: 0, marginTop: '2px' }}>
            <div style={{ position: 'relative', width: 44, height: 24 }}>
              <input
                type="checkbox"
                checked={settings.images_enabled}
                onChange={e => onChange('images_enabled', e.target.checked)}
                style={{ opacity: 0, width: 0, height: 0, position: 'absolute' }}
              />
              <div style={{
                position: 'absolute', inset: 0, borderRadius: '999px',
                background: settings.images_enabled
                  ? 'linear-gradient(135deg,#ec4899,#8b5cf6)'
                  : 'rgba(255,255,255,0.12)',
                transition: 'all 0.2s',
              }} />
              <div style={{
                position: 'absolute', top: 3, left: settings.images_enabled ? 23 : 3,
                width: 18, height: 18, borderRadius: '50%',
                background: '#fff',
                boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
                transition: 'left 0.2s',
              }} />
            </div>
          </label>
        </div>

        {settings.images_enabled && (
          <div style={{
            marginTop: '14px', padding: '12px',
            borderRadius: '10px', background: 'rgba(236,72,153,0.08)',
            border: '1px solid rgba(236,72,153,0.15)',
            display: 'flex', gap: '10px', alignItems: 'flex-start',
          }}>
            <span style={{ fontSize: '0.85rem', flexShrink: 0 }}>ℹ️</span>
            <div style={{ fontSize: '0.72rem', color: 'rgba(241,245,249,0.65)', lineHeight: 1.5 }}>
              Genera imágenes con <strong style={{ color: '#f9a8d4' }}>DALL-E 3</strong> a partir del transcript.
              Requiere <strong style={{ color: '#f9a8d4' }}>OPENAI_API_KEY</strong> en el <code>.env</code>.
              Cada imagen cuesta ~$0.04 (máx. 8 únicas por video).
            </div>
          </div>
        )}
      </div>

      {/* Platforms */}
      <div className="glass" style={{ padding: '20px', borderRadius: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Globe size={16} style={{ color: '#a78bfa' }} />
          <h3 style={{ fontSize: '0.92rem', margin: 0 }}>Plataformas a generar</h3>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {Object.entries(PLATFORM_SPECS).map(([key, spec]) => {
            const active = settings.platforms.includes(key);
            return (
              <button
                key={key}
                onClick={() => {
                  const cur = settings.platforms;
                  onChange('platforms',
                    active ? cur.filter(p => p !== key) : [...cur, key]
                  );
                }}
                style={{
                  padding: '6px 14px', borderRadius: '999px', border: 'none', cursor: 'pointer',
                  background: active ? 'rgba(109,40,217,0.25)' : 'rgba(255,255,255,0.06)',
                  color: active ? '#c4b5fd' : 'var(--text-muted)',
                  fontSize: '0.75rem', fontWeight: active ? 700 : 400,
                  outline: active ? '1px solid rgba(109,40,217,0.5)' : '1px solid transparent',
                  transition: 'all 0.15s',
                }}
              >
                {spec.icon} {spec.label} <span style={{ fontSize: '0.65rem', opacity: 0.7 }}>({spec.ratio})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Upload progress */}
      {uploading && (
        <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '12px', padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.82rem' }}>Subiendo a S3…</span>
            <span style={{ fontSize: '0.82rem', color: '#a78bfa', fontWeight: 700 }}>{uploadProgress}%</span>
          </div>
          <div style={{ height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: '99px', overflow: 'hidden' }}>
            <div style={{ width: `${uploadProgress}%`, height: '100%', background: 'var(--primary)', borderRadius: '99px', transition: 'width 0.3s' }} />
          </div>
        </div>
      )}

      {/* Process button */}
      <button
        onClick={onProcess}
        disabled={uploading || settings.platforms.length === 0}
        style={{
          padding: '15px', borderRadius: '13px', border: 'none',
          background: uploading ? 'rgba(109,40,217,0.4)' : 'linear-gradient(135deg,#6D28D9,#4C1D95)',
          color: '#fff', fontWeight: 700, fontSize: '1rem', cursor: uploading ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
          boxShadow: '0 4px 20px rgba(109,40,217,0.35)',
        }}
      >
        {uploading
          ? <><Spinner size={18} color="#fff" /> Subiendo…</>
          : <><Zap size={18} /> Procesar video</>}
      </button>
    </div>
  );
}

// ── Step 3: Processing ─────────────────────────────────────────────────────────

function ProcessingStep({ job }) {
  const step = job?.current_step || 'queued';
  const pct = job?.progress || 0;
  const stepInfo = PROCESSING_STEPS[step] || { label: step, pct };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '32px', maxWidth: '480px', width: '100%' }}>

      {/* Animated orb */}
      <div style={{ position: 'relative' }}>
        <div style={{
          position: 'absolute', inset: -20,
          background: 'radial-gradient(circle,rgba(109,40,217,0.25) 0%,transparent 70%)',
          animation: 'pulse-glow 2.5s infinite ease-in-out',
        }} />
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: 'linear-gradient(135deg,rgba(109,40,217,0.3),rgba(76,29,149,0.4))',
          border: '2px solid rgba(109,40,217,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative',
        }}>
          {pct === 100
            ? <CheckCircle size={32} style={{ color: '#22c55e' }} />
            : <Spinner size={32} color="#a78bfa" />}
        </div>
      </div>

      {/* Step label */}
      <div style={{ textAlign: 'center' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '8px' }}>
          {pct === 100 ? '¡Procesamiento completado!' : stepInfo.label}
        </h3>
        {job?.silence_count > 0 && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {job.silence_count} silencios detectados · duración final: {fmtSec(job.trimmed_duration)}
          </p>
        )}
      </div>

      {/* Progress bar */}
      <div style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Progreso</span>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#a78bfa' }}>{pct}%</span>
        </div>
        <div style={{ height: 8, background: 'rgba(255,255,255,0.08)', borderRadius: '99px', overflow: 'hidden' }}>
          <div style={{
            width: `${pct}%`, height: '100%', borderRadius: '99px',
            background: pct === 100
              ? 'linear-gradient(90deg,#22c55e,#4ade80)'
              : 'linear-gradient(90deg,#6D28D9,#a78bfa)',
            transition: 'width 0.5s ease',
          }} />
        </div>
      </div>

      {/* Steps checklist */}
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {Object.entries(PROCESSING_STEPS).map(([key, info]) => {
          const done = pct >= info.pct;
          const active = step === key && pct < 100;
          return (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '10px', opacity: done || active ? 1 : 0.35 }}>
              <div style={{
                width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: done ? 'rgba(34,197,94,0.2)' : active ? 'rgba(109,40,217,0.2)' : 'rgba(255,255,255,0.05)',
              }}>
                {done
                  ? <CheckCircle size={12} style={{ color: '#4ade80' }} />
                  : active
                    ? <Spinner size={12} color="#a78bfa" />
                    : <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'rgba(255,255,255,0.2)' }} />}
              </div>
              <span style={{ fontSize: '0.78rem', color: done ? '#4ade80' : active ? '#c4b5fd' : 'var(--text-muted)' }}>
                {info.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Step 4: Preview ────────────────────────────────────────────────────────────

function PreviewStep({ job, onRefreshUrls }) {
  const [activeFormat, setActiveFormat] = useState(() =>
    Object.keys(job?.processed_versions || {})[0] || 'tiktok'
  );
  const versions = job?.processed_versions || {};

  const current = versions[activeFormat];
  const spec = PLATFORM_SPECS[activeFormat];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', width: '100%', maxWidth: '800px' }}>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        {[
          { icon: Scissors, label: 'Silencios cortados', val: job?.silence_count || 0 },
          { icon: Clock, label: 'Duración final', val: fmtSec(job?.trimmed_duration) },
          { icon: Captions, label: 'Palabras', val: job?.word_count || (job?.transcript?.length || 0) },
          { icon: FileVideo, label: 'Formatos', val: Object.keys(versions).length },
        ].map(({ icon: Icon, label, val }) => (
          <div key={label} style={{
            flex: '1 1 140px', background: 'rgba(255,255,255,0.04)', borderRadius: '12px',
            padding: '14px', display: 'flex', flexDirection: 'column', gap: '4px',
          }}>
            <Icon size={14} style={{ color: '#a78bfa' }} />
            <p style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>{val}</p>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0 }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Format selector */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {Object.entries(versions).map(([key]) => {
          const sp = PLATFORM_SPECS[key];
          if (!sp) return null;
          return (
            <button key={key} onClick={() => setActiveFormat(key)}
              style={{
                padding: '7px 16px', borderRadius: '999px', border: 'none', cursor: 'pointer',
                background: activeFormat === key ? 'rgba(109,40,217,0.3)' : 'rgba(255,255,255,0.06)',
                color: activeFormat === key ? '#c4b5fd' : 'var(--text-muted)',
                fontSize: '0.78rem', fontWeight: activeFormat === key ? 700 : 400,
                outline: activeFormat === key ? '1px solid rgba(109,40,217,0.5)' : 'none',
              }}>
              {sp.icon} {sp.label}
            </button>
          );
        })}
        <button onClick={onRefreshUrls}
          style={{ padding: '7px 14px', borderRadius: '999px', border: '1px solid rgba(255,255,255,0.1)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <RefreshCw size={12} /> Renovar URLs
        </button>
      </div>

      {/* Video player */}
      {current?.presigned_url && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{
            display: 'flex', justifyContent: 'center',
            background: '#000', borderRadius: '16px', overflow: 'hidden',
          }}>
            <video
              key={current.presigned_url}
              controls
              style={{
                maxHeight: '440px',
                maxWidth: '100%',
                aspectRatio: spec?.ratio === '9:16' ? '9/16' : spec?.ratio === '1:1' ? '1/1' : '16/9',
              }}
              src={current.presigned_url}
            />
          </div>

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <a
              href={current.presigned_url}
              download={`${activeFormat}.mp4`}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '10px 20px', borderRadius: '10px',
                background: 'linear-gradient(135deg,#6D28D9,#4C1D95)',
                color: '#fff', textDecoration: 'none', fontWeight: 700, fontSize: '0.85rem',
              }}
            >
              <Download size={15} /> Descargar {spec?.label}
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Step 5: Publish ────────────────────────────────────────────────────────────

function PublishStep({ job, socialAccounts, onRefreshAccounts }) {
  const notify = useNotify();
  const [form, setForm] = useState({
    title: '', description: '', tags: '', privacy: 'public',
  });
  const [publishing, setPublishing] = useState({});
  const [results, setResults] = useState({});
  const [connectModal, setConnectModal] = useState(null); // 'instagram' | 'tiktok'
  const [tokenInput, setTokenInput] = useState('');
  const [connecting, setConnecting] = useState(false);

  const versions = job?.processed_versions || {};

  const PUBLISH_OPTIONS = [
    {
      platform: 'youtube',
      label: 'YouTube',
      formats: ['youtube', 'shorts'].filter(f => f in versions),
      icon: <PlayCircle size={20} style={{ color: '#FF0000' }} />,
      color: '#FF0000',
      connected: socialAccounts?.youtube?.connected,
      connectUrl: '/video/social/youtube/connect',
      needsOAuth: true,
    },
    {
      platform: 'instagram',
      label: 'Instagram',
      formats: ['reels', 'stories', 'instagram_feed'].filter(f => f in versions),
      icon: <Camera size={20} style={{ color: '#E1306C' }} />,
      color: '#E1306C',
      connected: socialAccounts?.instagram?.connected,
      needsOAuth: false,
    },
    {
      platform: 'tiktok',
      label: 'TikTok',
      formats: ['tiktok'].filter(f => f in versions),
      icon: <span style={{ fontSize: '1.1rem', lineHeight: 1 }}>🎵</span>,
      color: '#69C9D0',
      connected: socialAccounts?.tiktok?.connected,
      needsOAuth: false,
    },
  ];

  const handlePublish = async (platform, format) => {
    setPublishing(p => ({ ...p, [`${platform}_${format}`]: true }));
    try {
      await api.post(`/video/jobs/${job._id}/publish`, {
        platform,
        format,
        title: form.title || job.original_filename || 'My Video',
        description: form.description,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
        privacy: form.privacy,
      });
      setResults(r => ({ ...r, [`${platform}_${format}`]: 'success' }));
    } catch (err) {
      setResults(r => ({ ...r, [`${platform}_${format}`]: 'error' }));
    } finally {
      setPublishing(p => ({ ...p, [`${platform}_${format}`]: false }));
    }
  };

  const handleConnectToken = async (platform) => {
    setConnecting(true);
    try {
      await api.post('/video/social/connect', { platform, access_token: tokenInput });
      setConnectModal(null);
      setTokenInput('');
      onRefreshAccounts();
      notify(`${platform.charAt(0).toUpperCase() + platform.slice(1)} conectado correctamente`, 'success');
    } catch (e) {
      notify('Token inválido o permisos insuficientes', 'error');
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', width: '100%', maxWidth: '680px' }}>

      {/* Title / description */}
      <div className="glass" style={{ padding: '20px', borderRadius: '14px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <h3 style={{ fontSize: '0.9rem', margin: 0, display: 'flex', alignItems: 'center', gap: '7px' }}>
          <Settings size={15} style={{ color: '#a78bfa' }} /> Información del video
        </h3>
        <input
          type="text" placeholder="Título del video" value={form.title}
          onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
          className="input-field" style={{ padding: '10px 14px', borderRadius: '9px', fontSize: '0.88rem' }}
        />
        <textarea
          placeholder="Descripción (opcional)" value={form.description} rows={3}
          onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          style={{
            width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: '9px',
            background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
            color: 'var(--text-main)', fontSize: '0.85rem', fontFamily: 'inherit',
            resize: 'vertical', outline: 'none',
          }}
        />
        <input
          type="text" placeholder="Tags separados por coma (YouTube)" value={form.tags}
          onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
          className="input-field" style={{ padding: '10px 14px', borderRadius: '9px', fontSize: '0.85rem' }}
        />
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Privacidad:</label>
          {['public', 'unlisted', 'private'].map(p => (
            <button key={p} onClick={() => setForm(f => ({ ...f, privacy: p }))}
              style={{
                padding: '4px 12px', borderRadius: '999px', border: 'none', cursor: 'pointer', fontSize: '0.75rem',
                background: form.privacy === p ? 'rgba(109,40,217,0.3)' : 'rgba(255,255,255,0.06)',
                color: form.privacy === p ? '#c4b5fd' : 'var(--text-muted)',
                outline: form.privacy === p ? '1px solid rgba(109,40,217,0.4)' : 'none',
              }}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Platform cards */}
      {PUBLISH_OPTIONS.map(opt => (
        <div key={opt.platform} className="glass" style={{ padding: '20px', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {opt.icon}
              <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>{opt.label}</span>
            </div>
            {opt.connected
              ? <span style={{ fontSize: '0.68rem', background: 'rgba(34,197,94,0.15)', color: '#4ade80', padding: '3px 10px', borderRadius: '999px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <CheckCircle size={10} /> Conectado{socialAccounts?.[opt.platform]?.username ? ` · ${socialAccounts[opt.platform].username}` : ''}
                </span>
              : opt.needsOAuth
                ? <button
                    onClick={async () => {
                      try {
                        const { data } = await api.get('/video/social/youtube/auth-url');
                        window.location.href = data.url;
                      } catch (e) {
                        notify('Error al iniciar OAuth de YouTube. Verifica YOUTUBE_CLIENT_ID en el .env', 'error');
                      }
                    }}
                    style={{ fontSize: '0.75rem', padding: '5px 14px', borderRadius: '999px', background: 'rgba(255,0,0,0.15)', color: '#f87171', border: '1px solid rgba(255,0,0,0.2)', cursor: 'pointer' }}>
                    Conectar YouTube
                  </button>
                : <button onClick={() => setConnectModal(opt.platform)}
                    style={{ fontSize: '0.75rem', padding: '5px 14px', borderRadius: '999px', background: `rgba(${opt.color === '#E1306C' ? '225,48,108' : '105,201,208'},0.15)`, color: opt.color, border: `1px solid ${opt.color}33`, cursor: 'pointer' }}>
                    Conectar {opt.label}
                  </button>}
          </div>

          {opt.connected && opt.formats.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {opt.formats.map(fmt => {
                const key = `${opt.platform}_${fmt}`;
                const sp = PLATFORM_SPECS[fmt];
                const done = results[key] === 'success';
                const err = results[key] === 'error';
                return (
                  <div key={fmt} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', borderRadius: '9px', background: 'rgba(255,255,255,0.04)',
                  }}>
                    <div>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{sp?.icon} {sp?.label}</span>
                      {sp?.maxSec && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: '8px' }}>máx {sp.maxSec}s</span>}
                    </div>
                    {done
                      ? <span style={{ fontSize: '0.72rem', color: '#4ade80', display: 'flex', alignItems: 'center', gap: '4px' }}><CheckCircle size={12} /> Publicado</span>
                      : err
                        ? <span style={{ fontSize: '0.72rem', color: '#f87171', display: 'flex', alignItems: 'center', gap: '4px' }}><AlertTriangle size={12} /> Error</span>
                        : <button
                            onClick={() => handlePublish(opt.platform, fmt)}
                            disabled={publishing[key]}
                            style={{
                              padding: '6px 16px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontSize: '0.78rem',
                              background: `${opt.color}22`, color: opt.color, fontWeight: 700,
                              display: 'flex', alignItems: 'center', gap: '6px',
                              border: `1px solid ${opt.color}33`,
                            }}>
                            {publishing[key]
                              ? <Spinner size={12} color="#fff" />
                              : <Send size={12} />}
                            {publishing[key] ? 'Publicando…' : 'Publicar'}
                          </button>}
                  </div>
                );
              })}
            </div>
          ) : !opt.connected ? (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              Conecta tu cuenta para publicar en {opt.label}.
            </p>
          ) : (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              No hay formatos disponibles para esta plataforma.
            </p>
          )}
        </div>
      ))}

      {/* Token connect modal */}
      {connectModal && (
        <div onClick={e => { if (e.target === e.currentTarget) setConnectModal(null); }}
          style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div className="glass" style={{ width: '100%', maxWidth: '440px', padding: '28px', borderRadius: '18px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1rem' }}>Conectar {connectModal === 'instagram' ? 'Instagram' : 'TikTok'}</h3>
              <button onClick={() => setConnectModal(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}><X size={16} /></button>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '10px', padding: '12px', fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
              {connectModal === 'instagram'
                ? '1. Ve a developers.facebook.com → Tu app → Instagram → Generar un token de acceso con permiso instagram_content_publish\n2. Pégalo aquí.'
                : '1. Ve a developers.tiktok.com → Tu app → Genera un access token con scope video.upload\n2. Pégalo aquí.'}
            </div>
            <input type="text" value={tokenInput} onChange={e => setTokenInput(e.target.value)}
              placeholder="Pega tu access token aquí"
              className="input-field" style={{ padding: '10px 14px', borderRadius: '9px', fontSize: '0.85rem' }}
            />
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={() => handleConnectToken(connectModal)} disabled={connecting || !tokenInput}
                style={{ flex: 1, padding: '11px', borderRadius: '10px', border: 'none', background: 'var(--primary)', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: '0.88rem' }}>
                {connecting ? <Spinner size={15} color="#fff" /> : 'Guardar y conectar'}
              </button>
              <button onClick={() => setConnectModal(null)} style={{ padding: '11px 16px', borderRadius: '10px', background: 'rgba(255,255,255,0.06)', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── History sidebar ────────────────────────────────────────────────────────────

function HistorySidebar({ jobs, activeJobId, onLoad, onDelete, onNew }) {
  const [expandedId, setExpandedId] = useState(null);

  const toggle = (id) => setExpandedId(v => v === id ? null : id);

  return (
    <div style={{
      width: '264px', flexShrink: 0,
      background: 'rgba(0,0,0,0.28)',
      borderRight: '1px solid rgba(255,255,255,0.07)',
      display: 'flex', flexDirection: 'column',
      minHeight: '100vh', position: 'sticky', top: 0, alignSelf: 'flex-start', maxHeight: '100vh',
    }}>
      {/* Header */}
      <div style={{ padding: '20px 14px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Mis Videos
          </span>
          {jobs.length > 0 && (
            <span style={{ fontSize: '0.63rem', background: 'rgba(109,40,217,0.25)', color: '#a78bfa', padding: '2px 8px', borderRadius: '999px' }}>
              {jobs.length}
            </span>
          )}
        </div>
        <button onClick={onNew} style={{
          width: '100%', padding: '8px', borderRadius: '8px',
          background: 'linear-gradient(135deg,#6D28D9,#4C1D95)',
          border: 'none', color: '#fff', fontWeight: 700, fontSize: '0.77rem',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
        }}
          onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
          onMouseLeave={e => e.currentTarget.style.opacity = '1'}
        >
          <Upload size={13} /> Nuevo video
        </button>
      </div>

      {/* Scrollable list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 8px 24px' }}>
        {jobs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 12px' }}>
            <FileVideo size={28} style={{ color: 'rgba(255,255,255,0.1)', marginBottom: '8px' }} />
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
              Aún no hay videos procesados.
            </p>
          </div>
        ) : jobs.map(j => {
          const isActive   = j._id === activeJobId;
          const isExpanded = expandedId === j._id || isActive;
          const versions   = j.processed_versions || {};
          const fmtKeys    = Object.keys(versions).filter(k => versions[k]?.presigned_url);

          return (
            <div key={j._id} style={{ marginBottom: '3px' }}>
              {/* Job card */}
              <div
                onClick={() => { onLoad(j); toggle(j._id); }}
                style={{
                  padding: '9px 10px 8px',
                  borderRadius: '9px',
                  background: isActive ? 'rgba(109,40,217,0.18)' : 'transparent',
                  border: `1px solid ${isActive ? 'rgba(109,40,217,0.38)' : 'transparent'}`,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '5px' }}>
                  <FileVideo size={13} style={{ color: '#a78bfa', flexShrink: 0, marginTop: '2px' }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: '0.77rem', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {j.original_filename || 'Sin nombre'}
                    </p>
                    <p style={{ fontSize: '0.63rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>
                      {fmtDate(j.created_at)}{j.trimmed_duration ? ` · ${fmtSec(j.trimmed_duration)}` : ''}
                    </p>
                  </div>
                  <button
                    onClick={e => { e.stopPropagation(); onDelete(j._id, e); }}
                    style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: '5px', cursor: 'pointer', padding: '3px 5px', color: 'rgba(248,113,113,0.5)', display: 'flex', flexShrink: 0 }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#f87171'; e.currentTarget.style.background = 'rgba(239,68,68,0.2)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = 'rgba(248,113,113,0.5)'; e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
                    title="Eliminar video"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: '0.58rem', padding: '2px 7px', borderRadius: '999px',
                    background: j.status === 'ready' ? 'rgba(34,197,94,0.15)' : j.status === 'error' ? 'rgba(239,68,68,0.15)' : 'rgba(234,179,8,0.12)',
                    color: j.status === 'ready' ? '#4ade80' : j.status === 'error' ? '#f87171' : '#eab308',
                  }}>
                    {j.status === 'ready' ? '✓ Listo' : j.status === 'error' ? '✗ Error' : '⏳ Procesando'}
                  </span>
                  {fmtKeys.length > 0 && (
                    <span style={{ fontSize: '0.58rem', color: '#a78bfa' }}>{fmtKeys.length} formatos</span>
                  )}
                </div>
              </div>

              {/* Download links — shown when active */}
              {isExpanded && fmtKeys.length > 0 && (
                <div style={{ padding: '4px 6px 6px 6px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  {fmtKeys.map(fmt => {
                    const sp = PLATFORM_SPECS[fmt];
                    const v  = versions[fmt];
                    if (!sp) return null;
                    const baseName = (j.original_filename || 'video').replace(/\.[^.]+$/, '');
                    return (
                      <a
                        key={fmt}
                        href={v.presigned_url}
                        download={`${baseName}_${fmt}.mp4`}
                        onClick={e => e.stopPropagation()}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                          padding: '5px 10px', borderRadius: '7px',
                          background: 'rgba(109,40,217,0.1)',
                          border: '1px solid rgba(109,40,217,0.18)',
                          color: '#c4b5fd', textDecoration: 'none', fontSize: '0.68rem',
                          transition: 'background 0.12s',
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(109,40,217,0.24)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'rgba(109,40,217,0.1)'}
                      >
                        <span>{sp.icon} {sp.label}</span>
                        <Download size={10} />
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main VideoEditor ───────────────────────────────────────────────────────────

export default function VideoEditor() {
  const notify = useNotify();
  const confirm = useConfirm();
  const [step, setStep] = useState('upload');
  const [selectedFile, setSelectedFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [socialAccounts, setSocialAccounts] = useState({});
  const [pastJobs, setPastJobs] = useState([]);
  const pollRef = useRef(null);

  const [config, setConfig] = useState({
    silence_threshold_db: -40,
    silence_min_duration: 0.5,
    subtitle_style: 'tiktok',
    subtitles_enabled: true,
    images_enabled: false,
    platforms: ['tiktok', 'reels', 'youtube', 'shorts'],
  });

  const fetchSocial = useCallback(async () => {
    try {
      const res = await api.get('/video/social/status');
      setSocialAccounts(res.data.accounts || {});
    } catch {}
  }, []);

  const fetchPastJobs = useCallback(async () => {
    try {
      const res = await api.get('/video/jobs');
      setPastJobs(res.data.jobs || []);
    } catch {}
  }, []);

  useEffect(() => {
    fetchSocial();
    fetchPastJobs();
    // Check URL param for OAuth callback
    const params = new URLSearchParams(window.location.search);
    if (params.get('connected') === 'youtube') {
      fetchSocial();
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [fetchSocial, fetchPastJobs]);

  // Poll job status during processing
  useEffect(() => {
    if (step !== 'processing' || !jobId) return;
    const poll = async () => {
      try {
        const res = await api.get(`/video/jobs/${jobId}`);
        const j = res.data.job;
        setJob(j);
        if (j.status === 'ready') {
          clearInterval(pollRef.current);
          setStep('preview');
          fetchPastJobs();
        } else if (j.status === 'error') {
          clearInterval(pollRef.current);
        }
      } catch {}
    };
    pollRef.current = setInterval(poll, 2500);
    poll();
    return () => clearInterval(pollRef.current);
  }, [step, jobId, fetchPastJobs]);

  const handleFileSelected = (file) => {
    setSelectedFile(file);
    setStep('configure');
  };

  const handleProcess = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadProgress(10);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('silence_threshold_db', config.silence_threshold_db);
      formData.append('silence_min_duration', config.silence_min_duration);
      formData.append('subtitle_style', config.subtitle_style);
      formData.append('subtitles_enabled', config.subtitles_enabled);
      formData.append('images_enabled', config.images_enabled);
      formData.append('platforms', config.platforms.join(','));

      setUploadProgress(40);
      const res = await api.post('/video/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (ev) => {
          const pct = Math.round((ev.loaded / ev.total) * 80) + 10;
          setUploadProgress(Math.min(pct, 90));
        },
      });
      setUploadProgress(100);
      setJobId(res.data.job_id);
      setStep('processing');
      notify('Video subido — procesando en segundo plano', 'success');
    } catch (err) {
      notify('Error al subir el video: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleRefreshUrls = async () => {
    if (!jobId) return;
    try {
      const res = await api.get(`/video/jobs/${jobId}/refresh-urls`);
      setJob(j => ({ ...j, processed_versions: res.data.processed_versions }));
    } catch {}
  };

  const handleLoadJob = (j) => {
    setJob(j);
    setJobId(j._id);
    if (j.status === 'ready') setStep('preview');
    else if (j.status === 'processing') setStep('processing');
    else setStep('upload');
  };

  const handleDeleteJob = async (jid, e) => {
    if (e) e.stopPropagation();
    const name = pastJobs.find(j => j._id === jid)?.original_filename || 'este video';
    const ok = await confirm(
      `¿Eliminar "${name}" y todos sus formatos procesados? Esta acción no se puede deshacer.`,
      'Eliminar video'
    );
    if (!ok) return;
    try {
      await api.delete(`/video/jobs/${jid}`);
      setPastJobs(p => p.filter(j => j._id !== jid));
      if (jobId === jid) { setJobId(null); setJob(null); setStep('upload'); }
      notify('Video eliminado', 'success');
    } catch {
      notify('Error al eliminar el video. Intenta de nuevo.', 'error');
    }
  };

  const handleNew = () => {
    clearInterval(pollRef.current);
    setJobId(null);
    setJob(null);
    setSelectedFile(null);
    setStep('upload');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex' }}>
      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes pulse-glow { 0%,100%{opacity:.4;transform:scale(1)} 50%{opacity:.9;transform:scale(1.1)} }
      `}</style>

      {/* Persistent history sidebar */}
      <HistorySidebar
        jobs={pastJobs}
        activeJobId={jobId}
        onLoad={handleLoadJob}
        onDelete={handleDeleteJob}
        onNew={handleNew}
      />

      {/* Main content */}
      <div style={{ flex: 1, padding: '28px', boxSizing: 'border-box', overflowY: 'auto' }}>
      <div style={{ maxWidth: '860px', margin: '0 auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
              <div style={{ padding: '10px', borderRadius: '14px', background: 'linear-gradient(135deg,rgba(109,40,217,0.35),rgba(76,29,149,0.35))', display: 'flex' }}>
                <Video size={22} style={{ color: '#a78bfa' }} />
              </div>
              <h1 style={{ fontSize: '1.8rem', margin: 0 }}>
                Editor de <span style={{ background: 'linear-gradient(90deg,#a78bfa,#c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Video</span>
              </h1>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', margin: 0 }}>
              Elimina silencios automáticamente · Subtítulos animados con IA · Publica en TikTok, Instagram y YouTube
            </p>
          </div>
          {jobId && (
            <button
              onClick={() => handleDeleteJob(jobId)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '8px 14px', borderRadius: '9px', cursor: 'pointer',
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
                color: '#f87171', fontSize: '0.78rem', fontWeight: 600,
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.2)'}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(239,68,68,0.1)'}
              title="Eliminar este video"
            >
              <Trash2 size={13} /> Eliminar video
            </button>
          )}
        </div>

        {/* Step bar */}
        <StepBar current={step} />

        {/* Error state */}
        {job?.status === 'error' && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '12px', padding: '16px', marginBottom: '24px', display: 'flex', gap: '10px' }}>
            <AlertTriangle size={16} style={{ color: '#f87171', flexShrink: 0, marginTop: '1px' }} />
            <div>
              <p style={{ fontWeight: 700, marginBottom: '4px', color: '#f87171' }}>Error en el procesamiento</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>{job.error}</p>
            </div>
          </div>
        )}

        {/* Step content */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {step === 'upload' && <UploadStep onFileSelected={handleFileSelected} />}
          {step === 'configure' && (
            <ConfigureStep
              file={selectedFile}
              settings={config}
              onChange={(k, v) => setConfig(c => ({ ...c, [k]: v }))}
              onProcess={handleProcess}
              uploading={uploading}
              uploadProgress={uploadProgress}
            />
          )}
          {step === 'processing' && <ProcessingStep job={job} />}
          {step === 'preview' && job && (
            <>
              <PreviewStep job={job} onRefreshUrls={handleRefreshUrls} />
              <button
                onClick={() => setStep('publish')}
                style={{ marginTop: '20px', padding: '13px 32px', borderRadius: '12px', border: 'none', background: 'linear-gradient(135deg,#6D28D9,#4C1D95)', color: '#fff', fontWeight: 700, fontSize: '0.95rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Send size={16} /> Publicar en redes sociales
              </button>
            </>
          )}
          {step === 'publish' && job && (
            <>
              <button
                onClick={() => setStep('preview')}
                style={{ alignSelf: 'flex-start', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.82rem' }}>
                <ChevronLeft size={14} /> Volver al preview
              </button>
              <PublishStep
                job={job}
                socialAccounts={socialAccounts}
                onRefreshAccounts={fetchSocial}
              />
            </>
          )}

          {/* Navigation buttons (configure → upload) */}
          {step === 'configure' && (
            <button
              onClick={() => setStep('upload')}
              style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.82rem' }}>
              <ChevronLeft size={14} /> Cambiar video
            </button>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
