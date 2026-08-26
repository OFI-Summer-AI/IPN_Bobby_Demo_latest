import { useState, useRef, KeyboardEvent, ChangeEvent } from 'react';
import styles from './ChatInput.module.css';

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('');
  const [attachedFile, setAttachedFile] = useState<{ name: string; size: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAttachedFile({
        name: file.name,
        size: formatFileSize(file.size),
      });
    }
  };

  const handleRemoveFile = () => {
    setAttachedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSend = () => {
    let msg = value.trim();
    if (!msg && !attachedFile) return;
    if (disabled) return;

    if (attachedFile) {
      const fileHeader = `📎 [Attached File: ${attachedFile.name} (${attachedFile.size})]`;
      msg = msg ? `${msg}\n${fileHeader}` : fileHeader;
    }

    onSend(msg);
    setValue('');
    setAttachedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 80) + 'px';
  };

  return (
    <div className={styles.container}>
      {/* Attached File Preview Chip */}
      {attachedFile && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          margin: '0 8px 6px 8px',
          backgroundColor: '#ECFDF5',
          border: '1px solid #10B981',
          borderRadius: '8px',
          fontSize: '12px',
          color: '#064E3B'
        }}>
          <span style={{ fontSize: '14px' }}>📄</span>
          <span style={{ fontWeight: 600, maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {attachedFile.name}
          </span>
          <span style={{ color: '#059669', fontSize: '11px' }}>({attachedFile.size})</span>
          <button
            type="button"
            onClick={handleRemoveFile}
            style={{
              marginLeft: 'auto',
              background: 'none',
              border: 'none',
              color: '#991B1B',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '14px',
              padding: '0 4px'
            }}
            title="Remove attached file"
          >
            ✕
          </button>
        </div>
      )}

      <div className={styles.inputRow}>
        {/* Hidden File Input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          style={{ display: 'none' }}
          accept="image/*,.pdf,.doc,.docx,.txt,.log,.xlsx"
        />

        {/* Attachment icon button */}
        <button
          type="button"
          className={styles.attachBtn}
          onClick={handleFileClick}
          aria-label="Attach file"
          title="Upload screenshot or document"
          style={{ cursor: 'pointer' }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={attachedFile ? '#10B981' : 'currentColor'} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
          </svg>
        </button>

        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Type your message..."
          disabled={disabled}
          rows={1}
        />

        {/* Send button (circle) */}
        <button
          className={styles.sendBtn}
          onClick={handleSend}
          disabled={(!value.trim() && !attachedFile) || disabled}
          aria-label="Send message"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
      <p className={styles.hint}>Ask Bobby anything Usually replies in under a minute</p>
    </div>
  );
}
