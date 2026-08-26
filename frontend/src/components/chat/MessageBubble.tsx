import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message } from '@/types/chat.types';
import { format } from 'date-fns';
import styles from './MessageBubble.module.css';

interface Props {
  message: Message;
  isLatest?: boolean;
  onApprove?: (editedData?: Record<string, unknown>) => void;
  onReject?: () => void;
}

const PRIORITY_OPTIONS = ['low', 'medium', 'high', 'urgent'];
const CATEGORY_OPTIONS = [
  'Workplace & Hardware',
  'Network & Infrastructure',
  'Identity & Access',
  'Cybersecurity',
  'Enterprise Applications',
  'HR',
  'Finance',
  'IT'
];

export default function MessageBubble({ message, isLatest, onApprove, onReject }: Props) {
  const isUser = message.sender === 'user';
  const isSystem = message.sender === 'system';
  const hasPendingAction = isLatest && (message.requiresApproval || !!message.pendingAction);

  const pendingData = message.pendingAction?.data as Record<string, any> | undefined;

  const [isEditing, setIsEditing] = useState(false);
  const [subject, setSubject] = useState(pendingData?.subject || '');
  const [category, setCategory] = useState(pendingData?.category || 'Workplace & Hardware');
  const [priority, setPriority] = useState(pendingData?.priority || 'medium');
  const [description, setDescription] = useState(pendingData?.description || '');

  if (isSystem) {
    return (
      <div className={styles.system}>
        <span>{message.content}</span>
      </div>
    );
  }

  const handleConfirmEdited = () => {
    if (onApprove) {
      onApprove({
        ...pendingData,
        subject,
        category,
        priority,
        description,
      });
      setIsEditing(false);
    }
  };

  return (
    <div className={`${styles.row} ${isUser ? styles.rowUser : styles.rowBobby} animate-fade-in-up`}>
      {!isUser && <div className={styles.avatar}>B</div>}
      <div className={`${styles.bubble} ${isUser ? styles.bubbleUser : styles.bubbleBobby}`}>
        <div className={styles.markdownContent}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>

        {/* Embedded Interactive Action Buttons for Ticket Drafts */}
        {hasPendingAction && onApprove && onReject && (
          <div className={styles.actionContainer}>
            {!isEditing ? (
              <div className={styles.buttonRow}>
                <button 
                  className={styles.btnConfirm} 
                  onClick={() => onApprove(pendingData)}
                >
                  🚀 Confirm & Submit
                </button>
                <button 
                  className={styles.btnEdit} 
                  onClick={() => {
                    setSubject(pendingData?.subject || '');
                    setCategory(pendingData?.category || 'Workplace & Hardware');
                    setPriority(pendingData?.priority || 'medium');
                    setDescription(pendingData?.description || '');
                    setIsEditing(true);
                  }}
                >
                  ✏️ Edit Details
                </button>
                <button 
                  className={styles.btnCancel} 
                  onClick={onReject}
                >
                  ✕ Cancel
                </button>
              </div>
            ) : (
              <div className={styles.editCard}>
                <p className={styles.editTitle}>✏️ Customize Ticket Details</p>
                
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Subject</label>
                  <input
                    className={styles.formInput}
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="Subject summary"
                  />
                </div>

                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Category</label>
                    <select
                      className={styles.formSelect}
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      {CATEGORY_OPTIONS.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>

                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Priority</label>
                    <select
                      className={styles.formSelect}
                      value={priority}
                      onChange={(e) => setPriority(e.target.value)}
                    >
                      {PRIORITY_OPTIONS.map((p) => (
                        <option key={p} value={p}>{p.toUpperCase()}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Description</label>
                  <textarea
                    className={styles.formTextarea}
                    rows={2}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

                <div className={styles.editActions}>
                  <button 
                    className={styles.btnEditCancel} 
                    onClick={() => setIsEditing(false)}
                  >
                    Back to Preview
                  </button>
                  <button 
                    className={styles.btnConfirm} 
                    onClick={handleConfirmEdited}
                  >
                    💾 Save & Submit
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {message.intent && (
          <span className={styles.intentTag}>{message.intent.replace('_', ' ')}</span>
        )}
        <span className={styles.timestamp}>
          {format(new Date(message.timestamp), 'HH:mm')}
        </span>
      </div>
    </div>
  );
}
