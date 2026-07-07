import { useEffect, useRef, useState } from 'react';
import { T } from '../dashboard/tokens';
import { saveQuery, listLibraryFolders } from '../../services/api';
import { ChevronDown, Folder, Plus, X } from 'lucide-react';
import type { FolderSummary } from '../../types/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  sql: string;
  defaultTitle?: string;
  connectionId?: string;
  onSaved: (created: boolean) => void;
}

const inputStyle: React.CSSProperties = {
  width: '100%', background: T.s2, border: `1px solid ${T.border}`,
  borderRadius: 8, padding: '8px 12px', color: T.text,
  fontFamily: T.fontBody, fontSize: '0.82rem', outline: 'none',
  transition: 'border-color 0.2s', boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  fontSize: '0.65rem', fontWeight: 600, letterSpacing: '1px',
  textTransform: 'uppercase', color: T.text3, fontFamily: T.fontMono,
  marginBottom: 8, display: 'block', opacity: 0.8,
};

const glassInputStyle = (isFocused: boolean): React.CSSProperties => ({
  ...inputStyle,
  background: isFocused ? T.s1 : 'rgba(255, 255, 255, 0.4)',
  borderColor: isFocused ? T.accent : T.border,
  boxShadow: isFocused ? `0 0 0 3px ${T.accent}15` : 'none',
  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
});

export function SaveQueryModal({ isOpen, onClose, sql, defaultTitle, connectionId, onSaved }: Props) {
  const [title, setTitle] = useState('');
  const [folders, setFolders] = useState<FolderSummary[]>([]);
  const [selectedFolder, setSelectedFolder] = useState('Uncategorized');
  const [newFolderMode, setNewFolderMode] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    setTitle(defaultTitle || 'Saved from Chat');
    setSelectedFolder(localStorage.getItem('lastUsedFolder') || 'Uncategorized');
    setNewFolderMode(false);
    setNewFolderName('');
    setError('');
    setIsDropdownOpen(false);
    listLibraryFolders().then(setFolders).catch(() => {});
    setTimeout(() => titleRef.current?.select(), 50);
  }, [isOpen, defaultTitle]);

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFolderChange = (value: string) => {
    if (value === '__new__') {
      setNewFolderMode(true);
      setSelectedFolder('__new__');
    } else {
      setNewFolderMode(false);
      setSelectedFolder(value);
    }
    setIsDropdownOpen(false);
  };

  const handleSave = async () => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) { setError('Query title is required.'); return; }
    if (newFolderMode && !newFolderName.trim()) { setError('Enter a name for the new folder.'); return; }

    const folderName = newFolderMode ? newFolderName.trim() : selectedFolder;
    setSaving(true);
    setError('');
    try {
      const result = await saveQuery({
        title: trimmedTitle,
        sql,
        connection_id: connectionId,
        folder_name: folderName,
      });
      onSaved(result.created || result.folder_name === folderName);
      localStorage.setItem('lastUsedFolder', folderName);
      onClose();
    } catch {
      setError('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'Enter' && !e.shiftKey) handleSave();
  };

  return (
    <div
      onKeyDown={handleKeyDown}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div 
        className="antigravity-modal-entry"
        style={{
          width: 440, 
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(24px) saturate(160%)',
          border: `1px solid rgba(255, 255, 255, 0.4)`,
          borderRadius: 24, overflow: 'visible',
          boxShadow: '0 32px 80px rgba(0,0,0,0.15), 0 0 0 1px rgba(255,255,255,0.5)',
          position: 'relative',
        }}
      >
        <style>{`
          @keyframes antigravity-float-in {
            0% { transform: translateY(20px) scale(0.98); opacity: 0; }
            100% { transform: translateY(0) scale(1); opacity: 1; }
          }
          .antigravity-modal-entry {
            animation: antigravity-float-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          }
        `}</style>
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: `1px solid ${T.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontFamily: T.fontHead, fontWeight: 700, fontSize: '0.95rem', color: T.text }}>
              Save Query to Library
            </div>
            <div style={{ fontSize: '0.68rem', color: T.text3, fontFamily: T.fontMono, marginTop: 2 }}>
              Choose a folder or create a new one
            </div>
          </div>
          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 10, background: 'rgba(0,0,0,0.03)',
            border: `1px solid ${T.border}`, cursor: 'pointer', color: T.text3,
            display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.2s',
          }} onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,0,0,0.06)'} onMouseLeave={e => e.currentTarget.style.background = 'rgba(0,0,0,0.03)'}>
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Title */}
          <div>
            <label style={labelStyle}>Query Title</label>
            <input
              ref={titleRef}
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="e.g. Monthly Revenue by Region"
              style={glassInputStyle(title === title)} // simple hook for focus later if needed, but using CSS is better
              className="premium-input"
            />
            <style>{`
              .premium-input {
                width: 100%; background: rgba(255, 255, 255, 0.4); border: 1px solid ${T.border};
                border-radius: 12px; padding: 10px 14px; color: ${T.text};
                font-family: ${T.fontBody}; fontSize: 0.9rem; outline: none;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
              }
              .premium-input:focus {
                background: #fff; border-color: ${T.accent}; box-shadow: 0 0 0 4px ${T.accent}15;
              }
            `}</style>
          </div>

          {/* Folder Custom Selector */}
          <div ref={dropdownRef} style={{ position: 'relative' }}>
            <label style={labelStyle}>Destination Folder</label>
            <div 
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              style={{
                width: '100%', background: 'rgba(255, 255, 255, 0.4)', border: `1px solid ${isDropdownOpen ? T.accent : T.border}`,
                borderRadius: 12, padding: '10px 14px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                transition: 'all 0.2s',
                boxShadow: isDropdownOpen ? `0 0 0 4px ${T.accent}15` : 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.9rem', color: T.text2 }}>
                <Folder size={16} style={{ color: T.accent }} />
                {selectedFolder === '__new__' ? (newFolderName || 'New Folder...') : selectedFolder}
              </div>
              <ChevronDown size={16} style={{ color: T.text3, transform: isDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
            </div>

            {isDropdownOpen && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 8,
                background: 'rgba(255, 255, 255, 0.95)', backdropFilter: 'blur(16px)',
                border: `1px solid ${T.border}`, borderRadius: 16,
                boxShadow: T.shadow.lg, zIndex: 20, padding: 6,
                maxHeight: 220, overflowY: 'auto',
              }}>
                {/* Options */}
                {[
                  { id: '__new__', label: 'Create new folder...', isAction: true },
                  { id: 'Uncategorized', label: 'Uncategorized' },
                  ...folders.filter(f => f.name !== 'Uncategorized' && f.name !== 'Public Library').map(f => ({ id: f.name, label: f.name })),
                ].map((opt) => (
                  <div
                    key={opt.id}
                    onClick={() => handleFolderChange(opt.id)}
                    style={{
                      padding: '10px 12px', borderRadius: 10, cursor: 'pointer',
                      fontSize: '0.88rem', color: opt.isAction ? T.accent : T.text2,
                      display: 'flex', alignItems: 'center', gap: 10,
                      background: selectedFolder === opt.id ? T.accentDim : 'transparent',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = opt.isAction ? `${T.accent}08` : T.s2}
                    onMouseLeave={e => e.currentTarget.style.background = selectedFolder === opt.id ? T.accentDim : 'transparent'}
                  >
                    {opt.isAction ? <Plus size={14} /> : <Folder size={14} style={{ opacity: 0.6 }} />}
                    {opt.label}
                  </div>
                ))}
              </div>
            )}

            {/* New folder input — appears inline */}
            {newFolderMode && (
              <div style={{ marginTop: 12, position: 'relative' }}>
                <input
                  autoFocus
                  value={newFolderName}
                  onChange={e => setNewFolderName(e.target.value)}
                  placeholder="Enter folder name..."
                  className="premium-input"
                />
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div style={{
              padding: '8px 12px', borderRadius: 8, background: `${T.red}18`,
              border: `1px solid ${T.red}44`, color: T.red, fontSize: '0.75rem',
            }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px', borderTop: `1px solid rgba(0,0,0,0.04)`,
          display: 'flex', gap: 12, justifyContent: 'flex-end',
          background: 'rgba(0,0,0,0.01)',
        }}>
          <button onClick={onClose} style={{
            padding: '10px 20px', borderRadius: 14, fontSize: '0.82rem',
            fontFamily: T.fontBody, cursor: 'pointer', fontWeight: 500,
            border: `1px solid ${T.border}`, background: 'transparent', color: T.text3,
            transition: 'all 0.2s',
          }} onMouseEnter={e => { e.currentTarget.style.background = T.s2; e.currentTarget.style.color = T.text2; }} onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = T.text3; }}>
            Cancel
          </button>
          <button onClick={handleSave} disabled={saving} style={{
            padding: '10px 24px', borderRadius: 14, fontSize: '0.82rem', fontWeight: 600,
            fontFamily: T.fontBody, cursor: saving ? 'default' : 'pointer',
            border: 'none', background: T.accent, color: '#fff',
            boxShadow: `0 8px 20px ${T.accent}30`,
            opacity: saving ? 0.7 : 1,
            transition: 'all 0.2s',
          }} onMouseEnter={e => { if (!saving) e.currentTarget.style.transform = 'translateY(-1px)'; }} onMouseLeave={e => { if (!saving) e.currentTarget.style.transform = 'translateY(0)'; }}>
            {saving ? '⏳ Saving…' : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Folder size={14} />
                Save Query
              </div>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
