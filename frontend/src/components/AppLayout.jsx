import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Sparkles, Search, Inbox, Send, Settings,
  LogOut, User, ChevronRight, ChevronLeft, Briefcase, Video,
  Zap, BarChart2, Settings2, Radar, LayoutGrid, Building2, Bot,
} from 'lucide-react';
import PipelineRunner from './outbound/PipelineRunner';

const W_EXPANDED = 224;
const W_COLLAPSED = 68;

const NAV_GROUPS = [
  {
    label: 'Agente IA',
    items: [
      { path: '/agent', icon: Bot, label: 'Agent Hub' },
    ],
  },
  {
    label: 'Clientes',
    items: [
      { path: '/',                    icon: Search,    label: 'Búsqueda clientes'  },
      { path: '/company-intel',       icon: Building2, label: 'Inteligencia empresas' },
      { path: '/freelance',           icon: Briefcase, label: 'Proyectos freelance' },
      { path: '/video',              icon: Video,     label: 'Editor de Video'    },
      { path: '/outbound/approvals',  icon: Inbox,     label: 'Cola de aprobación' },
      { path: '/outbound/sent',       icon: Send,      label: 'Emails enviados'    },
      { path: '/outbound/icp-config', icon: Settings,  label: 'ICP Config'         },
    ],
  },
  {
    label: 'Career Ops',
    items: [
      { path: '/career-ops/config',    icon: Settings2,  label: 'CO Configuración' },
      { path: '/career-ops/scan',      icon: Radar,      label: 'Scanner'          },
      { path: '/career-ops/offers',    icon: LayoutGrid, label: 'Ofertas'          },
      { path: '/career-ops/pipeline',  icon: Zap,        label: 'Evaluar oferta'   },
      { path: '/career-ops/reports',   icon: BarChart2,  label: 'Reportes'         },
    ],
  },
];

function NavItem({ path, icon: Icon, label, expanded, active, onClick }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={!expanded ? label : undefined}
      style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        padding: '10px 14px',
        margin: '1px 6px',
        borderRadius: '10px',
        cursor: 'pointer',
        position: 'relative',
        background: active
          ? 'rgba(109,40,217,0.28)'
          : hovered ? 'rgba(255,255,255,0.07)' : 'transparent',
        borderLeft: active ? '3px solid #7C3AED' : '3px solid transparent',
        transition: 'background 0.15s ease, border-color 0.15s ease',
        overflow: 'hidden',
      }}
    >
      <Icon
        size={18}
        style={{
          flexShrink: 0,
          color: active ? '#a78bfa' : hovered ? 'rgba(255,255,255,0.75)' : 'rgba(255,255,255,0.38)',
          transition: 'color 0.15s ease',
        }}
      />
      <span
        style={{
          fontSize: '0.84rem',
          fontWeight: active ? 700 : 400,
          color: active ? '#e9d5ff' : hovered ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.42)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          opacity: expanded ? 1 : 0,
          maxWidth: expanded ? '160px' : 0,
          transition: 'opacity 0.22s ease, max-width 0.22s ease, color 0.15s ease',
        }}
      >
        {label}
      </span>

      {/* Active glow dot */}
      {active && (
        <span style={{
          position: 'absolute', right: '12px',
          width: '6px', height: '6px', borderRadius: '50%',
          background: '#7C3AED',
          boxShadow: '0 0 8px #7C3AED',
          opacity: expanded ? 1 : 0,
          transition: 'opacity 0.2s',
        }} />
      )}
    </div>
  );
}

export default function AppLayout({ children }) {
  const [expanded, setExpanded] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const sidebarW = expanded ? W_EXPANDED : W_COLLAPSED;

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-w', `${sidebarW}px`);
  }, [sidebarW]);

  const isActive = (path) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>

      {/* ── Fixed left sidebar ─────────────────────────────────────────── */}
      <aside style={{
        position: 'fixed', left: 0, top: 0, height: '100vh',
        width: sidebarW,
        background: 'linear-gradient(180deg, #080818 0%, #0c0824 60%, #080818 100%)',
        borderRight: '1px solid rgba(255,255,255,0.07)',
        boxShadow: '4px 0 24px rgba(0,0,0,0.35)',
        display: 'flex', flexDirection: 'column',
        transition: `width 0.28s cubic-bezier(0.4, 0, 0.2, 1)`,
        overflow: 'hidden',
        zIndex: 200,
        userSelect: 'none',
      }}>

        {/* Logo */}
        <div style={{
          height: '64px', flexShrink: 0,
          display: 'flex', alignItems: 'center',
          padding: '0 16px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          justifyContent: 'space-between',
          gap: '10px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, overflow: 'hidden' }}>
            <div style={{
              width: '36px', height: '36px', flexShrink: 0,
              borderRadius: '11px',
              background: 'linear-gradient(135deg, #6D28D9, #4C1D95)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(109,40,217,0.45)',
            }}>
              <Sparkles size={18} style={{ color: '#e9d5ff' }} />
            </div>
            <span style={{
              fontSize: '0.9rem', fontWeight: 800,
              background: 'linear-gradient(90deg, #a78bfa, #c4b5fd)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              whiteSpace: 'nowrap',
              opacity: expanded ? 1 : 0,
              maxWidth: expanded ? '140px' : 0,
              overflow: 'hidden',
              transition: 'opacity 0.22s ease, max-width 0.22s ease',
            }}>
              AI Client Finder
            </span>
          </div>

          {/* Toggle button */}
          <button
            onClick={() => setExpanded(v => !v)}
            style={{
              flexShrink: 0,
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              width: '28px', height: '28px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', color: 'rgba(255,255,255,0.45)',
              transition: 'background 0.15s, color 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(109,40,217,0.3)'; e.currentTarget.style.color = '#a78bfa'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'rgba(255,255,255,0.45)'; }}
          >
            {expanded ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
          </button>
        </div>

        {/* Nav groups */}
        <nav style={{ flex: 1, padding: '8px 0', overflowY: 'auto', overflowX: 'hidden' }}>
          {NAV_GROUPS.map(({ label, items }) => (
            <div key={label}>
              <div style={{
                padding: '14px 14px 6px',
                overflow: 'hidden',
                opacity: expanded ? 1 : 0,
                maxHeight: expanded ? '32px' : '0px',
                transition: 'opacity 0.2s ease, max-height 0.22s ease',
              }}>
                <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.1em', color: 'rgba(255,255,255,0.2)', textTransform: 'uppercase' }}>
                  {label}
                </span>
              </div>
              {items.map(({ path, icon, label: itemLabel }) => (
                <NavItem
                  key={path}
                  path={path}
                  icon={icon}
                  label={itemLabel}
                  expanded={expanded}
                  active={isActive(path)}
                  onClick={() => navigate(path)}
                />
              ))}
              <div style={{ height: '8px' }} />
            </div>
          ))}
        </nav>

        {/* Pipeline Runner */}
        <div style={{
          padding: '10px 8px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', justifyContent: expanded ? 'stretch' : 'center',
        }}>
          <PipelineRunner collapsed={!expanded} />
        </div>

        {/* User + Logout */}
        <div style={{
          padding: '12px 8px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', alignItems: 'center',
          gap: '10px',
          justifyContent: expanded ? 'flex-start' : 'center',
        }}>
          <div style={{
            width: '36px', height: '36px', flexShrink: 0,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #6D28D9, #4C1D95)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <User size={16} style={{ color: '#e9d5ff' }} />
          </div>
          <div style={{
            flex: 1, minWidth: 0, overflow: 'hidden',
            opacity: expanded ? 1 : 0,
            maxWidth: expanded ? '120px' : 0,
            transition: 'opacity 0.22s ease, max-width 0.22s ease',
          }}>
            <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'rgba(255,255,255,0.75)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', margin: 0 }}>
              {user?.full_name}
            </p>
            <p style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.3)', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {user?.email}
            </p>
          </div>
          {expanded && (
            <button
              onClick={logout}
              title="Cerrar sesión"
              style={{
                flexShrink: 0,
                background: 'none', border: 'none',
                color: 'rgba(255,255,255,0.3)', cursor: 'pointer',
                display: 'flex', padding: '4px', borderRadius: '6px',
                transition: 'color 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#f87171'}
              onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.3)'}
            >
              <LogOut size={15} />
            </button>
          )}
        </div>
      </aside>

      {/* ── Content area ───────────────────────────────────────────────── */}
      <div style={{
        marginLeft: sidebarW,
        flex: 1,
        minHeight: '100vh',
        transition: `margin-left 0.28s cubic-bezier(0.4, 0, 0.2, 1)`,
        minWidth: 0,
      }}>
        {children}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
