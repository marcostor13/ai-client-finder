import { useState } from 'react';
import { Activity, Link2, FolderOpen } from 'lucide-react';
import ChatWindow from '../components/agent/ChatWindow';
import ModelStatus from '../components/agent/ModelStatus';
import Connections from '../components/agent/Connections';
import FileLibrary from '../components/agent/FileLibrary';
import '../agent.css';

export default function AgentHub() {
  const [rightPanel, setRightPanel] = useState('status'); // 'status' | 'connections' | 'files' | null
  const [statusCollapsed, setStatusCollapsed] = useState(false);

  function togglePanel(panel) {
    setRightPanel(p => p === panel ? null : panel);
  }

  return (
    <div className="agent-hub">
      {/* ── Main chat area ─────────────────────────────────────────────── */}
      <div className="agent-main">
        <ChatWindow />
      </div>

      {/* ── Right panel toggle buttons ─────────────────────────────────── */}
      <div className="agent-right-controls">
        <button
          className={`right-ctrl-btn ${rightPanel === 'status' ? 'active' : ''}`}
          onClick={() => togglePanel('status')}
          title="Estado de modelos"
        >
          <Activity size={16} />
        </button>
        <button
          className={`right-ctrl-btn ${rightPanel === 'files' ? 'active' : ''}`}
          onClick={() => togglePanel('files')}
          title="Biblioteca RAG"
        >
          <FolderOpen size={16} />
        </button>
        <button
          className={`right-ctrl-btn ${rightPanel === 'connections' ? 'active' : ''}`}
          onClick={() => togglePanel('connections')}
          title="Conexiones"
        >
          <Link2 size={16} />
        </button>
      </div>

      {/* ── Right panel ─────────────────────────────────────────────────── */}
      {rightPanel && (
        <div className="agent-right">
          {rightPanel === 'status' && (
            <ModelStatus
              collapsed={statusCollapsed}
              onToggle={() => setStatusCollapsed(c => !c)}
            />
          )}
          {rightPanel === 'files' && <FileLibrary />}
          {rightPanel === 'connections' && <Connections />}
        </div>
      )}
    </div>
  );
}
