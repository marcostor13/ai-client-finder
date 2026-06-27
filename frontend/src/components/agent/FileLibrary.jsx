import { useState, useEffect } from 'react';
import { FileText, Trash2, Loader, Upload, FileX, CheckCircle, XCircle } from 'lucide-react';
import api from '../../api';

const ICON_BY_EXT = {
  pdf: '📄', docx: '📝', doc: '📝', txt: '📃', md: '📃',
  csv: '📊', json: '🗂️', py: '🐍', js: '⚙️', ts: '⚙️',
  jsx: '⚛️', tsx: '⚛️',
};

function fileIcon(filename) {
  const ext = filename.split('.').pop()?.toLowerCase();
  return ICON_BY_EXT[ext] || '📎';
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function FileLibrary() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => { fetchFiles(); }, []);

  async function fetchFiles() {
    setLoading(true);
    try {
      const { data } = await api.get('/agent/files');
      setFiles(data.files || []);
    } catch {
      setError('No se pudo cargar la biblioteca');
    }
    setLoading(false);
  }

  async function uploadFile(file) {
    setUploading(true);
    setError('');
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post('/agent/files', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setFiles(prev => [data, ...prev]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al subir el archivo');
    }
    setUploading(false);
  }

  async function deleteFile(id) {
    setDeletingId(id);
    try {
      await api.delete(`/agent/files/${id}`);
      setFiles(prev => prev.filter(f => f._id !== id));
    } catch {
      setError('Error al eliminar el archivo');
    }
    setDeletingId(null);
  }

  if (loading) {
    return (
      <div className="conn-loading">
        <Loader size={18} className="spin" />
      </div>
    );
  }

  return (
    <div className="file-library">
      <div className="file-lib-header">
        <FileText size={14} style={{ color: '#a78bfa' }} />
        <span>Biblioteca RAG</span>
        <span className="file-lib-count">{files.length} archivo{files.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Upload drop zone */}
      <label className={`file-drop-zone ${uploading ? 'uploading' : ''}`}>
        <input
          type="file"
          accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.py,.js,.ts,.jsx,.tsx,.yaml,.yml,.xml"
          style={{ display: 'none' }}
          disabled={uploading}
          onChange={e => e.target.files?.[0] && uploadFile(e.target.files[0])}
        />
        {uploading
          ? <><Loader size={16} className="spin" /> Procesando…</>
          : <><Upload size={14} /> Subir archivo</>
        }
      </label>

      {error && <div className="conn-error" style={{ padding: '0 2px' }}>{error}</div>}

      {/* File list */}
      {files.length === 0 ? (
        <div className="file-lib-empty">
          <FileX size={28} style={{ color: 'rgba(255,255,255,0.1)', marginBottom: 8 }} />
          <p>Sin archivos aún</p>
          <p style={{ fontSize: '0.68rem' }}>
            Sube PDFs, documentos o código y el agente los usará como contexto
          </p>
        </div>
      ) : (
        <div className="file-list">
          {files.map(f => (
            <div key={f._id} className="file-row">
              <span className="file-row-icon">{fileIcon(f.filename)}</span>
              <div className="file-row-info">
                <div className="file-row-name" title={f.filename}>{f.filename}</div>
                <div className="file-row-meta">
                  {formatSize(f.size)}
                  {f.has_text
                    ? <><CheckCircle size={9} style={{ color: '#22c55e' }} /> {f.chunk_count} fragmentos</>
                    : <><XCircle size={9} style={{ color: '#6b7280' }} /> sin texto</>
                  }
                </div>
              </div>
              <button
                className="btn-danger-xs"
                onClick={() => deleteFile(f._id)}
                disabled={deletingId === f._id}
                title="Eliminar"
              >
                {deletingId === f._id
                  ? <Loader size={12} className="spin" />
                  : <Trash2 size={12} />
                }
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="conn-desc" style={{ marginTop: 12 }}>
        Cada archivo se indexa automáticamente. El agente incluirá los fragmentos más relevantes como contexto en cada respuesta.
      </div>
    </div>
  );
}
