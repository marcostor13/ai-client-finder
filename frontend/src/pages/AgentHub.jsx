import { useState, useEffect } from 'react';
import { Activity, Link2, FolderOpen, LayoutGrid, X } from 'lucide-react';
import ChatWindow from '../components/agent/ChatWindow';
import ModelStatus from '../components/agent/ModelStatus';
import Connections from '../components/agent/Connections';
import FileLibrary from '../components/agent/FileLibrary';
import '../agent.css';

const MOBILE_BP = 768;
const PANELS = {
  status: { label: 'Estado de modelos', icon: Activity },
  files: { label: 'Biblioteca de archivos', icon: FolderOpen },
  connections: { label: 'Conexiones', icon: Link2 },
};

function useIsMobile() {
  const [m, setM] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= MOBILE_BP : false
  );
  useEffect(() => {
    const onResize = () => setM(window.innerWidth <= MOBILE_BP);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return m;
}

export default function AgentHub() {
  const isMobile = useIsMobile();
  // Desktop opens the status panel by default; mobile starts as a clean full chat.
  const [rightPanel, setRightPanel] = useState(() =>
    (typeof window !== 'undefined' && window.innerWidth <= MOBILE_BP) ? null : 'status'
  );
  const [statusCollapsed, setStatusCollapsed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // Entering mobile: collapse to the full-screen chat (no side-by-side split).
  useEffect(() => { if (isMobile) { setRightPanel(null); setMenuOpen(false); } }, [isMobile]);

  function togglePanel(panel) {
    setRightPanel(p => (p === panel ? null : panel));
  }
  function openPanel(panel) {
    setRightPanel(panel);
    setMenuOpen(false);
  }

  function renderPanel(panel, { collapsible } = {}) {
    if (panel === 'status') {
      return (
        <ModelStatus
          collapsed={collapsible ? statusCollapsed : false}
          onToggle={collapsible ? () => setStatusCollapsed(c => !c) : undefined}
        />
      );
    }
    if (panel === 'files') return <FileLibrary />;
    if (panel === 'connections') return <Connections />;
    return null;
  }

  // ── Mobile: full-screen chat + FAB + full-screen sheet ──────────────────────
  if (isMobile) {
    return (
      <div className="agent-hub">
        <div className="agent-main"><ChatWindow /></div>

        {/* Floating panel launcher */}
        {!rightPanel && (
          <>
            {menuOpen && (
              <div className="agent-fab-backdrop" onClick={() => setMenuOpen(false)} />
            )}
            {menuOpen && (
              <div className="agent-fab-menu">
                {Object.entries(PANELS).map(([key, { label, icon: Icon }]) => (
                  <button key={key} onClick={() => openPanel(key)}>
                    <Icon size={16} /> {label}
                  </button>
                ))}
              </div>
            )}
            <button
              className="agent-fab"
              onClick={() => setMenuOpen(o => !o)}
              aria-label="Paneles"
            >
              {menuOpen ? <X size={20} /> : <LayoutGrid size={20} />}
            </button>
          </>
        )}

        {/* Selected panel as a full-screen sheet */}
        {rightPanel && (
          <div className="agent-sheet">
            <div className="agent-sheet-head">
              <span>{PANELS[rightPanel]?.label}</span>
              <button onClick={() => setRightPanel(null)} aria-label="Cerrar">
                <X size={20} />
              </button>
            </div>
            <div className="agent-sheet-body">{renderPanel(rightPanel)}</div>
          </div>
        )}
      </div>
    );
  }

  // ── Desktop: chat + control strip + side panel ──────────────────────────────
  return (
    <div className="agent-hub">
      <div className="agent-main"><ChatWindow /></div>

      <div className="agent-right-controls">
        {Object.entries(PANELS).map(([key, { label, icon: Icon }]) => (
          <button
            key={key}
            className={`right-ctrl-btn ${rightPanel === key ? 'active' : ''}`}
            onClick={() => togglePanel(key)}
            title={label}
          >
            <Icon size={16} />
          </button>
        ))}
      </div>

      {rightPanel && (
        <div className="agent-right">{renderPanel(rightPanel, { collapsible: true })}</div>
      )}
    </div>
  );
}
