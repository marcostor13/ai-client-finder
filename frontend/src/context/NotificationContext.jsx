import { createContext, useCallback, useContext, useRef, useState } from 'react';

const NotificationContext = createContext(null);

let _uid = 0;

export function NotificationProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const [dialog, setDialog] = useState(null); // { message, title, resolve }
  const timers = useRef({});

  // ── Toasts ──────────────────────────────────────────────────────────────────

  const dismiss = useCallback((id) => {
    setToasts(t => t.map(n => n.id === id ? { ...n, leaving: true } : n));
    setTimeout(() => setToasts(t => t.filter(n => n.id !== id)), 320);
  }, []);

  const notify = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++_uid;
    setToasts(t => [...t, { id, message, type, leaving: false }]);
    if (duration > 0) {
      timers.current[id] = setTimeout(() => dismiss(id), duration);
    }
    return id;
  }, [dismiss]);

  const dismiss_all = useCallback(() => {
    setToasts(t => t.map(n => ({ ...n, leaving: true })));
    setTimeout(() => setToasts([]), 320);
  }, []);

  // ── Confirm dialog ──────────────────────────────────────────────────────────

  const confirm = useCallback((message, title = '¿Estás seguro?') => {
    return new Promise((resolve) => {
      setDialog({ message, title, resolve });
    });
  }, []);

  const _resolveDialog = (result) => {
    if (dialog) {
      dialog.resolve(result);
      setDialog(null);
    }
  };

  return (
    <NotificationContext.Provider value={{ notify, dismiss, dismiss_all, confirm }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
      {dialog && (
        <ConfirmDialog
          title={dialog.title}
          message={dialog.message}
          onConfirm={() => _resolveDialog(true)}
          onCancel={() => _resolveDialog(false)}
        />
      )}
    </NotificationContext.Provider>
  );
}

export function useNotify() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotify must be used inside NotificationProvider');
  return ctx.notify;
}

export function useConfirm() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useConfirm must be used inside NotificationProvider');
  return ctx.confirm;
}

export function useNotifications() {
  return useContext(NotificationContext);
}

// ── Toast config ───────────────────────────────────────────────────────────────

const TYPES = {
  success: {
    icon: '✓',
    accent: '#22c55e',
    bg: 'rgba(22,163,74,0.12)',
    border: 'rgba(34,197,94,0.25)',
  },
  error: {
    icon: '✕',
    accent: '#f87171',
    bg: 'rgba(220,38,38,0.12)',
    border: 'rgba(239,68,68,0.28)',
  },
  warning: {
    icon: '⚠',
    accent: '#fbbf24',
    bg: 'rgba(217,119,6,0.12)',
    border: 'rgba(251,191,36,0.25)',
  },
  info: {
    icon: 'ℹ',
    accent: '#a78bfa',
    bg: 'rgba(109,40,217,0.12)',
    border: 'rgba(167,139,250,0.25)',
  },
};

// ── ToastContainer ─────────────────────────────────────────────────────────────

function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;

  return (
    <>
      <style>{`
        @keyframes toast-in {
          from { opacity: 0; transform: translateX(110%); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes toast-out {
          from { opacity: 1; transform: translateX(0); max-height: 80px; margin-bottom: 10px; }
          to   { opacity: 0; transform: translateX(110%); max-height: 0; margin-bottom: 0; }
        }
        .toast-item {
          animation: toast-in 0.28s cubic-bezier(0.34,1.56,0.64,1) forwards;
        }
        .toast-item.leaving {
          animation: toast-out 0.28s ease-in forwards;
        }
      `}</style>
      <div style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        maxWidth: '380px',
        width: 'calc(100vw - 48px)',
        pointerEvents: 'none',
      }}>
        {toasts.map(toast => {
          const t = TYPES[toast.type] || TYPES.info;
          return (
            <div
              key={toast.id}
              className={`toast-item${toast.leaving ? ' leaving' : ''}`}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '14px 16px',
                borderRadius: '12px',
                background: `${t.bg}`,
                border: `1px solid ${t.border}`,
                backdropFilter: 'blur(16px)',
                WebkitBackdropFilter: 'blur(16px)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.35)',
                pointerEvents: 'auto',
                cursor: 'default',
              }}
            >
              <div style={{
                width: 24, height: 24, borderRadius: '50%',
                background: `${t.accent}22`,
                border: `1.5px solid ${t.accent}55`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.7rem', color: t.accent, flexShrink: 0, fontWeight: 700,
              }}>
                {t.icon}
              </div>

              <p style={{
                flex: 1, margin: 0,
                fontSize: '0.83rem', lineHeight: 1.45,
                color: '#f1f5f9',
              }}>
                {toast.message}
              </p>

              <button
                onClick={() => onDismiss(toast.id)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'rgba(255,255,255,0.3)', padding: '0 2px',
                  fontSize: '0.9rem', lineHeight: 1, flexShrink: 0,
                  marginTop: '1px',
                }}
                onMouseEnter={e => e.currentTarget.style.color = 'rgba(255,255,255,0.8)'}
                onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.3)'}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </>
  );
}

// ── ConfirmDialog ──────────────────────────────────────────────────────────────

function ConfirmDialog({ title, message, onConfirm, onCancel }) {
  return (
    <>
      <style>{`
        @keyframes confirm-backdrop-in {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes confirm-panel-in {
          from { opacity: 0; transform: scale(0.92) translateY(12px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
        .confirm-backdrop {
          animation: confirm-backdrop-in 0.18s ease forwards;
        }
        .confirm-panel {
          animation: confirm-panel-in 0.22s cubic-bezier(0.34,1.56,0.64,1) forwards;
        }
      `}</style>
      <div
        className="confirm-backdrop"
        onClick={onCancel}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.6)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          zIndex: 10000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '24px',
        }}
      >
        <div
          className="confirm-panel"
          onClick={e => e.stopPropagation()}
          style={{
            background: 'linear-gradient(135deg, rgba(30,20,60,0.98) 0%, rgba(20,15,45,0.98) 100%)',
            border: '1px solid rgba(109,40,217,0.3)',
            borderRadius: '18px',
            padding: '28px 28px 24px',
            maxWidth: '420px',
            width: '100%',
            boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)',
          }}
        >
          {/* Icon + title */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
            <div style={{
              width: 38, height: 38, borderRadius: '50%',
              background: 'rgba(251,191,36,0.12)',
              border: '1.5px solid rgba(251,191,36,0.35)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1rem', flexShrink: 0,
            }}>
              ⚠
            </div>
            <h3 style={{
              margin: 0, fontSize: '1rem', fontWeight: 600,
              color: '#f1f5f9', letterSpacing: '-0.01em',
            }}>
              {title}
            </h3>
          </div>

          {/* Message */}
          <p style={{
            margin: '0 0 24px',
            fontSize: '0.875rem', lineHeight: 1.55,
            color: 'rgba(241,245,249,0.7)',
          }}>
            {message}
          </p>

          {/* Buttons */}
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
            <button
              onClick={onCancel}
              style={{
                padding: '9px 20px', borderRadius: '10px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(241,245,249,0.7)',
                fontSize: '0.875rem', cursor: 'pointer', fontWeight: 500,
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)'; e.currentTarget.style.color = '#f1f5f9'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'rgba(241,245,249,0.7)'; }}
            >
              Cancelar
            </button>
            <button
              onClick={onConfirm}
              style={{
                padding: '9px 20px', borderRadius: '10px',
                background: 'linear-gradient(135deg, #dc2626, #b91c1c)',
                border: '1px solid rgba(220,38,38,0.4)',
                color: '#fff',
                fontSize: '0.875rem', cursor: 'pointer', fontWeight: 600,
                transition: 'all 0.15s',
                boxShadow: '0 4px 12px rgba(220,38,38,0.3)',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 6px 16px rgba(220,38,38,0.45)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(220,38,38,0.3)'; }}
            >
              Eliminar
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
