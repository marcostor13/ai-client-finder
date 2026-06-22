/**
 * Spinner — reutilizable en toda la app.
 *
 * Props:
 *   size     number   px del contenedor  (default 24)
 *   color    string   color del arco     (default var(--accent))
 *   variant  'arc' | 'dots' | 'ring'    (default 'arc')
 *   fullPage boolean  centra en toda la pantalla con texto opcional
 *   label    string   texto bajo el spinner (solo fullPage)
 */
export default function Spinner({
  size = 24,
  color = 'var(--accent)',
  variant = 'arc',
  fullPage = false,
  label = 'Cargando…',
}) {
  const inner = variant === 'dots'
    ? <DotsSpinner size={size} color={color} />
    : variant === 'ring'
    ? <RingSpinner size={size} color={color} />
    : <ArcSpinner size={size} color={color} />;

  if (!fullPage) return inner;

  return (
    <div style={{
      position: 'fixed', inset: 0,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: '20px',
      background: 'radial-gradient(circle at 50% 50%, #1E1B4B 0%, #0F172A 100%)',
      animation: 'page-loader-in 0.3s ease forwards',
      zIndex: 9998,
    }}>
      {/* Glow ring behind spinner */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          position: 'absolute',
          width: size * 2.2,
          height: size * 2.2,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${color}22 0%, transparent 70%)`,
          animation: 'spinner-pulse 2s ease-in-out infinite',
        }} />
        <ArcSpinner size={size} color={color} />
      </div>

      {label && (
        <p style={{
          margin: 0,
          fontSize: '0.9rem',
          color: 'rgba(241,245,249,0.5)',
          letterSpacing: '0.05em',
          fontWeight: 400,
        }}>
          {label}
        </p>
      )}
    </div>
  );
}

// ── Variants ───────────────────────────────────────────────────────────────────

function ArcSpinner({ size, color }) {
  const thickness = Math.max(2, size * 0.1);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      style={{ animation: 'spin 0.9s linear infinite', display: 'block', flexShrink: 0 }}
    >
      {/* Track */}
      <circle cx="12" cy="12" r="10" stroke={color} strokeOpacity="0.15" strokeWidth={thickness} />
      {/* Arc */}
      <circle
        cx="12" cy="12" r="10"
        stroke={color}
        strokeWidth={thickness}
        strokeLinecap="round"
        strokeDasharray="40 23"
        strokeDashoffset="0"
      />
    </svg>
  );
}

function RingSpinner({ size, color }) {
  const thickness = Math.max(2, size * 0.1);
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      border: `${thickness}px solid ${color}22`,
      borderTopColor: color,
      animation: 'spin 0.8s linear infinite',
      flexShrink: 0,
    }} />
  );
}

function DotsSpinner({ size, color }) {
  const dot = Math.max(4, size * 0.22);
  const delays = ['0s', '0.16s', '0.32s'];
  return (
    <div style={{ display: 'flex', gap: dot * 0.7, alignItems: 'center', flexShrink: 0 }}>
      {delays.map((d, i) => (
        <div
          key={i}
          style={{
            width: dot, height: dot, borderRadius: '50%',
            background: color,
            animation: `spinner-pulse 0.9s ease-in-out ${d} infinite`,
          }}
        />
      ))}
    </div>
  );
}
