import { useState } from 'react';
import styles from './ActionButtons.module.css';

interface PendingActionData {
  subject?: string;
  description?: string;
  priority?: string;
  category?: string;
  [key: string]: unknown;
}

interface Props {
  onApprove: (editedData?: PendingActionData) => void;
  onReject: () => void;
  pendingAction?: {
    type: string;
    data?: PendingActionData;
    message?: string;
  } | null;
}

const PRIORITY_OPTIONS = ['low', 'medium', 'high', 'urgent'];
const CATEGORY_OPTIONS = ['IT', 'HR', 'Finance', 'General'];

const PRIORITY_COLORS: Record<string, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#f97316',
  urgent: '#ef4444',
};

export default function ActionButtons({ onApprove, onReject, pendingAction }: Props) {
  const data = pendingAction?.data as PendingActionData | undefined;
  const isTicket = pendingAction?.type === 'create_ticket';

  const [subject, setSubject] = useState(data?.subject || '');
  const [description, setDescription] = useState(
    (data?.description || '').split('\n\nThis ticket was automatically created')[0]
  );
  const [priority, setPriority] = useState(data?.priority || 'medium');
  const [category, setCategory] = useState(data?.category || 'IT');
  const [isEditing, setIsEditing] = useState(false);

  const handleConfirm = () => {
    onApprove({
      ...data,
      subject,
      description,
      priority,
      category,
    });
  };

  if (!isTicket) {
    return (
      <div className={styles.container}>
        <p className={styles.label}>Bobby is waiting for your approval:</p>
        <div className={styles.buttons}>
          <button className={styles.approve} onClick={() => onApprove()}>
            ✅ Approve
          </button>
          <button className={styles.reject} onClick={onReject}>
            ✕ Reject
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.draftCard}>
      <div className={styles.draftHeader}>
        <span className={styles.draftIcon}>🎫</span>
        <div>
          <p className={styles.draftTitle}>Ticket Draft — Please Review</p>
          <p className={styles.draftSub}>Review details and confirm or edit before submitting</p>
        </div>
      </div>

      <div className={styles.draftBody}>
        {/* Subject */}
        <div className={styles.field}>
          <label className={styles.fieldLabel}>Subject</label>
          {isEditing ? (
            <input
              className={styles.fieldInput}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Brief description of the issue"
            />
          ) : (
            <p className={styles.fieldValue}>{subject || 'IT Support Request'}</p>
          )}
        </div>

        {/* Priority & Category row */}
        <div className={styles.fieldRow}>
          <div className={styles.field}>
            <label className={styles.fieldLabel}>Priority</label>
            {isEditing ? (
              <select
                className={styles.fieldSelect}
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            ) : (
              <span
                className={styles.priorityBadge}
                style={{ background: `${PRIORITY_COLORS[priority]}20`, color: PRIORITY_COLORS[priority], border: `1px solid ${PRIORITY_COLORS[priority]}40` }}
              >
                {priority.charAt(0).toUpperCase() + priority.slice(1)}
              </span>
            )}
          </div>

          <div className={styles.field}>
            <label className={styles.fieldLabel}>Category</label>
            {isEditing ? (
              <select
                className={styles.fieldSelect}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            ) : (
              <span className={styles.categoryBadge}>{category}</span>
            )}
          </div>
        </div>

        {/* Description */}
        <div className={styles.field}>
          <label className={styles.fieldLabel}>Description</label>
          {isEditing ? (
            <textarea
              className={styles.fieldTextarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Detailed description for the IT team"
            />
          ) : (
            <p className={styles.fieldDesc}>{description}</p>
          )}
        </div>
      </div>

      <div className={styles.draftActions}>
        {!isEditing && (
          <button className={styles.editBtn} onClick={() => setIsEditing(true)}>
            ✏️ Edit Details
          </button>
        )}
        {isEditing && (
          <button className={styles.editBtn} onClick={() => setIsEditing(false)}>
            👁 Preview
          </button>
        )}
        <button className={styles.rejectBtn} onClick={onReject}>
          ✕ Cancel
        </button>
        <button className={styles.confirmBtn} onClick={handleConfirm}>
          ✅ Confirm & Submit
        </button>
      </div>
    </div>
  );
}
