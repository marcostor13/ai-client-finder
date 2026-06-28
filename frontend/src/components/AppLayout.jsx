import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Sparkles, Search, Inbox, Send, Settings,
  LogOut, User, ChevronRight, ChevronLeft, Briefcase, Video,
  Zap, BarChart2, Settings2, Radar, LayoutGrid, Building2, Bot, Trophy,
  Menu, X,
} from 'lucide-react';
import PipelineRunner from './outbound/PipelineRunner';

const W_EXPANDED = 224;
const W_COLLAPSED = 68;
const MOBILE_BP = 768;
const TOPBAR_H = 56;

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= MOBILE_BP : false
  );
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= MOBILE_BP);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return isMobile;
}

const NAV_GROUPS = [
  {
    label: 'Agente IA',
    items: [
      { path: '/agent', icon: Bot, label: 'Agent Hub' },
      { path: '/coach', icon: Trophy, label: 'Coach Personal' },
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
  const [mobileOpen, setMobileOpen] = useState(false);
  const isMobile = useIsMobile();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // On mobile the sidebar is an off-canvas drawer (always shows labels).
  const expandedEff = isMobile ? true : expanded;
  const sidebarW = isMobile ? W_EXPANDED : (expanded ? W_EXPANDED : W_COLLAPSED);
  const reservedW = isMobile ? 0 : sidebarW;

  useEffect(() => {
    document.documentElement.style.setProperty('--sidebar-w', `${reservedW}px`);
  }, [reservedW]);

  // Close the drawer whenever the route changes.
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const isActive = (path) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  const go = (path) => { navigate(path); if (isMobile) setMobileOpen(false); };

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>

      {/* ── Mobile top bar (hamburger + logo) ──────────────────────────── */}
      {isMobile && (
        <header style={{
          position: 'fixed', top: 0, left: 0, right: 0, height: TOPBAR_H,
          display: 'flex', alignItems: 'center', gap: '12px', padding: '0 14px',
          background: 'linear-gradient(90deg, #0c0824, #080818)',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          zIndex: 180,
        }}>
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Abrir menú"
            style={{
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '9px', width: '38px', height: '38px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', color: '#a78bfa', flexShrink: 0,
            }}
          >
            <Menu size={18} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
            <div style={{
              width: '30px', height: '30px', borderRadius: '9px',
              background: 'linear-gradient(135deg, #6D28D9, #4C1D95)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Sparkles size={15} style={{ color: '#e9d5ff' }} />
            </div>
            <span style={{
              fontSize: '0.9rem', fontWeight: 800,
              background: 'linear-gradient(90deg, #a78bfa, #c4b5fd)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>AI Client Finder</span>
          </div>
        </header>
      )}

      {/* ── Backdrop when the mobile drawer is open ────────────────────── */}
      {isMobile && mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
            zIndex: 240, backdropFilter: 'blur(2px)',
          }}
        />
      )}

      {/* ── Left sidebar (fixed on desktop, off-canvas drawer on mobile) ── */}
      <aside style={{
        position: 'fixed', left: 0, top: 0, height: '100vh',
        width: sidebarW,
        background: 'linear-gradient(180deg, #080818 0%, #0c0824 60%, #080818 100%)',
        borderRight: '1px solid rgba(255,255,255,0.07)',
        boxShadow: '4px 0 24px rgba(0,0,0,0.35)',
        display: 'flex', flexDirection: 'column',
        transition: isMobile
          ? 'transform 0.28s cubic-bezier(0.4, 0, 0.2, 1)'
          : 'width 0.28s cubic-bezier(0.4, 0, 0.2, 1)',
        transform: isMobile && !mobileOpen ? 'translateX(-100%)' : 'translateX(0)',
        overflow: 'hidden',
        zIndex: 250,
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
              opacity: expandedEff ? 1 : 0,
              maxWidth: expandedEff ? '140px' : 0,
              overflow: 'hidden',
              transition: 'opacity 0.22s ease, max-width 0.22s ease',
            }}>
              AI Client Finder
            </span>
          </div>

          {/* Toggle (collapse on desktop · close drawer on mobile) */}
          <button
            onClick={() => isMobile ? setMobileOpen(false) : setExpanded(v => !v)}
            aria-label={isMobile ? 'Cerrar menú' : 'Contraer menú'}
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
            {isMobile ? <X size={15} /> : (expanded ? <ChevronLeft size={14} /> : <ChevronRight size={14} />)}
          </button>
        </div>

        {/* Nav groups */}
        <nav style={{ flex: 1, padding: '8px 0', overflowY: 'auto', overflowX: 'hidden' }}>
          {NAV_GROUPS.map(({ label, items }) => (
            <div key={label}>
              <div style={{
                padding: '14px 14px 6px',
                overflow: 'hidden',
                opacity: expandedEff ? 1 : 0,
                maxHeight: expandedEff ? '32px' : '0px',
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
                  expanded={expandedEff}
                  active={isActive(path)}
                  onClick={() => go(path)}
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
          display: 'flex', justifyContent: expandedEff ? 'stretch' : 'center',
        }}>
          <PipelineRunner collapsed={!expandedEff} />
        </div>

        {/* User + Logout */}
        <div style={{
          padding: '12px 8px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex', alignItems: 'center',
          gap: '10px',
          justifyContent: expandedEff ? 'flex-start' : 'center',
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
            opacity: expandedEff ? 1 : 0,
            maxWidth: expandedEff ? '120px' : 0,
            transition: 'opacity 0.22s ease, max-width 0.22s ease',
          }}>
            <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'rgba(255,255,255,0.75)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', margin: 0 }}>
              {user?.full_name}
            </p>
            <p style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.3)', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {user?.email}
            </p>
          </div>
          {expandedEff && (
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
        marginLeft: reservedW,
        paddingTop: isMobile ? TOPBAR_H : 0,
        flex: 1,
        minHeight: '100vh',
        transition: `margin-left 0.28s cubic-bezier(0.4, 0, 0.2, 1)`,
        minWidth: 0,
        width: '100%',
      }}>
        {children}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
