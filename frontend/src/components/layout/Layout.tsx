import { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { useChatStore } from '@/store/chatStore';
import { InspiredLogo } from '@/pages/LoginPage';
import MessageBubble from '@/components/chat/MessageBubble';
import ChatInput from '@/components/chat/ChatInput';
import TypingIndicator from '@/components/chat/TypingIndicator';
import ActionButtons from '@/components/chat/ActionButtons';
import styles from './Layout.module.css';

interface Props { children: React.ReactNode; }

const QUICK_ACTIONS = [
  {
    icon: '🎫',
    title: 'Report an IT Issue',
    desc: 'Raise a Freshdesk support ticket',
    prompt: 'I want to raise an IT support ticket',
  },
  {
    icon: '🔍',
    title: 'Check Ticket Status',
    desc: 'Track your open requests',
    prompt: 'What is the status of my ticket?',
  },
  {
    icon: '🌐',
    title: 'VPN & Wi-Fi Support',
    desc: 'Connection & network guides',
    prompt: 'How do I connect to the company VPN?',
  },
  {
    icon: '🔑',
    title: 'Password & Account',
    desc: 'SSPR reset & MFA setup',
    prompt: 'How do I reset my password?',
  },
];

export default function Layout({ children }: Props) {
  const { user, messages, isLoading, pendingAction, sendMessage, approveAction } = useChatStore();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [emailNotification, setEmailNotification] = useState<{
    subject: string;
    body: string;
  } | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const getTimeGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const userName = user?.name ? user.name.split(' (')[0].split(' ')[0] : 'there';
  const greeting = `${getTimeGreeting()}, ${userName}! 👋`;

  const handleLogout = () => {
    localStorage.removeItem('bobby_user');
    localStorage.removeItem('bobby_token');
    window.location.href = '/';
  };

  useEffect(() => {
    if (isChatOpen) {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, isChatOpen]);

  useEffect(() => {
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.sender === 'bobby') {
        const text = lastMsg.content.toLowerCase();
        
        if (text.includes("shall i create a ticket")) {
          setIsChatOpen(true);
        }

        if (text.includes("escalated to p1 priority") || text.includes("escalated to high priority")) {
          setEmailNotification({
            subject: "Notification: Ticket Escalated to P1 Priority",
            body: `Hello ${user?.name.split(' (')[0] || 'Employee'},\n\nYour request has been escalated to P1 priority. An on-call engineer has been assigned.\nExpected MTTR: 15 minutes.\n\nBest Regards,\nInspired Pet Nutrition Helpdesk`
          });
          
          const timer = setTimeout(() => setEmailNotification(null), 10000);
          return () => clearTimeout(timer);
        }
      }
    }
  }, [messages, user]);

  return (
    <div className={styles.shell}>
      {/* Top Header Navigation */}
      <header className={styles.header}>
        <div className={styles.headerContainer}>
          <div className={styles.logoWrapper}>
            <InspiredLogo variant="header" />
          </div>

          <nav className={styles.nav}>
            <NavLink to="/home" className={styles.navLink}>
              HOME
            </NavLink>
            <a href="#brands" className={styles.navLink}>BRANDS</a>
            <a href="#about" className={styles.navLink}>ABOUT</a>
            <a href="#careers" className={styles.navLink}>CAREERS</a>
            <a href="#news" className={styles.navLink}>NEWS</a>
            <a href="#environment" className={styles.navLink}>ENVIRONMENT</a>
            <a href="#contact" className={styles.contactBtn}>CONTACT</a>
            
            {user && (
              <button className={styles.logoutBtn} onClick={handleLogout}>
                Sign out ({user.name.split(' (')[0]})
              </button>
            )}
          </nav>
        </div>
      </header>

      {/* Main Page Content */}
      <main className={styles.main}>
        {children}
      </main>

      {/* Simulated Email Toast Notification Card */}
      {emailNotification && (
        <div className={styles.emailToast}>
          <div className={styles.emailToastHeader}>
            <span className={styles.emailIcon}>✉️</span>
            <div>
              <p className={styles.emailSender}>Inspired Pet Nutrition Helpdesk</p>
              <p className={styles.emailSubject}>{emailNotification.subject}</p>
            </div>
            <button className={styles.toastCloseBtn} onClick={() => setEmailNotification(null)}>✕</button>
          </div>
          <div className={styles.emailToastBody}>
            {emailNotification.body.split('\n').map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </div>
      )}

      {/* Floating Chat Widget */}
      <div className={styles.widgetContainer}>
        {!isChatOpen && (
          <button 
            className={styles.chatBadge} 
            onClick={() => setIsChatOpen(true)}
            aria-label="Open Bobby Chat"
          >
            <span className={styles.statusDot} />
            <span className={styles.badgeText}>Bobby, AI agent</span>
          </button>
        )}

        {isChatOpen && (
          <div className={styles.chatWindow}>
            {/* Chat Header */}
            <div className={styles.chatHeader}>
              <div className={styles.headerInfo}>
                <div className={styles.avatar}>B</div>
                <div>
                  <h3 className={styles.headerTitle}>Bobby</h3>
                  <p className={styles.headerSub}>AI IT Service Management</p>
                </div>
              </div>
              <button 
                className={styles.closeBtn} 
                onClick={() => setIsChatOpen(false)}
                aria-label="Close Chat"
              >
                ✕
              </button>
            </div>

            {/* Chat Body */}
            <div className={styles.chatBody}>
              {messages.length === 0 && (
                <div className={styles.welcome}>
                  <div className={styles.welcomeBadge}>
                    <span className={styles.welcomeLiveDot} />
                    <span>24/7 IT Service Desk</span>
                  </div>
                  <h4 className={styles.welcomeHeading}>{greeting}</h4>
                  <p className={styles.welcomeSub}>
                    How can IT Support help you today? Select a common request or type below.
                  </p>
                  
                  <div className={styles.quickActionGrid}>
                    {QUICK_ACTIONS.map((action) => (
                      <button
                        key={action.title}
                        className={styles.quickActionCard}
                        onClick={() => sendMessage(action.prompt)}
                      >
                        <span className={styles.quickActionIcon}>{action.icon}</span>
                        <div className={styles.quickActionText}>
                          <span className={styles.quickActionTitle}>{action.title}</span>
                          <span className={styles.quickActionDesc}>{action.desc}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, index) => (
                <MessageBubble 
                  key={msg.id} 
                  message={msg} 
                  isLatest={index === messages.length - 1}
                  onApprove={(editedData) => approveAction(true, editedData)}
                  onReject={() => approveAction(false)}
                />
              ))}

              {isLoading && <TypingIndicator />}

              {pendingAction && !isLoading && (
                <ActionButtons
                  pendingAction={pendingAction}
                  onApprove={(editedData) => approveAction(true, editedData)}
                  onReject={() => approveAction(false)}
                />
              )}

              {/* Post-Resolution / Wrap-up Quick Actions */}
              {!isLoading && !pendingAction && messages.length > 0 && 
                messages[messages.length - 1].sender === 'bobby' && 
                (messages[messages.length - 1].content.includes("anything else") || 
                 messages[messages.length - 1].content.includes("Created Successfully") ||
                 messages[messages.length - 1].content.includes("Resolved")) && (
                <div className={styles.wrapUpActions}>
                  <p className={styles.wrapUpTitle}>Next Steps:</p>
                  <div className={styles.wrapUpButtons}>
                    <button 
                      className={styles.wrapUpBtn}
                      onClick={() => sendMessage("What is the status of my ticket?")}
                    >
                      🎫 Check Ticket Status
                    </button>
                    <button 
                      className={styles.wrapUpBtn}
                      onClick={() => sendMessage("I have another IT question")}
                    >
                      ❓ Ask Another Question
                    </button>
                    <button 
                      className={styles.wrapUpBtnReset}
                      onClick={() => setIsChatOpen(false)}
                    >
                      ❌ Close Chat
                    </button>
                  </div>
                </div>
              )}

              <div ref={chatBottomRef} />
            </div>

            {/* Chat Input */}
            <ChatInput onSend={sendMessage} disabled={isLoading || !!pendingAction} />
          </div>
        )}
      </div>
    </div>
  );
}

