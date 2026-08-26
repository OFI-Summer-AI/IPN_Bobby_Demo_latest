import styles from './TypingIndicator.module.css';

export default function TypingIndicator() {
  return (
    <div className={styles.row}>
      <div className={styles.avatar}>B</div>
      <div className={styles.bubble}>
        <span className={styles.dot} />
        <span className={styles.dot} />
        <span className={styles.dot} />
      </div>
    </div>
  );
}
