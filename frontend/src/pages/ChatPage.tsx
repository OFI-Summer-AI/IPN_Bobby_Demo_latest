import { useRef, useEffect } from 'react';
import { useChatStore } from '@/store/chatStore';
import MessageBubble from '@/components/chat/MessageBubble';
import ChatInput from '@/components/chat/ChatInput';
import TypingIndicator from '@/components/chat/TypingIndicator';
import ActionButtons from '@/components/chat/ActionButtons';
import styles from './ChatPage.module.css';

export default function ChatPage() {
  const { messages, isLoading, pendingAction, sendMessage, approveAction } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerAvatar}>B</div>
        <div>
          <h2 className={styles.headerTitle}>Bobby</h2>
          <p className={styles.headerStatus}>
            <span className={styles.statusDot} />
            AI Service Agent · Online
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className={styles.messages}>
        {messages.length === 0 && (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>👋</div>
            <h3>Hi, I'm Bobby!</h3>
            <p>I can help you with IT support, create tickets, check ticket status, unlock accounts, and more.</p>
            <div className={styles.suggestions}>
              {[
                'How do I connect to the VPN?',
                'My account is locked',
                'Show my open tickets',
                'I need to reset my password',
              ].map((s) => (
                <button key={s} className={styles.suggestion} onClick={() => sendMessage(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && <TypingIndicator />}

        {/* HITL Approval Buttons */}
        {pendingAction && !isLoading && (
          <ActionButtons
            onApprove={() => approveAction(true)}
            onReject={() => approveAction(false)}
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isLoading || !!pendingAction} />
    </div>
  );
}
