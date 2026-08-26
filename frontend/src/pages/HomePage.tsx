import styles from './HomePage.module.css';

export default function HomePage() {
  return (
    <div className={styles.container}>
      <div className={styles.heroSection}>
        {/* Left Side Illustration */}
        <div className={styles.illCol}>
          <div className={styles.illustrationCard}>
            {/* Cute SVG pet illustration matching Figma screenshot */}
            <svg width="220" height="220" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Pedestal base */}
              <ellipse cx="100" cy="165" rx="35" ry="6" fill="#15362E" />
              <ellipse cx="100" cy="161" rx="30" ry="5" fill="#84A78E" />

              {/* Egg body */}
              <path d="M100,50 C130,50 145,95 145,125 C145,152 125,160 100,160 C75,160 55,152 55,125 C55,95 70,50 100,50 Z" fill="#E5B84F" />

              {/* Ears */}
              {/* Left ear */}
              <path d="M68,58 C62,45 60,35 68,35 C76,35 76,45 74,53" fill="#E5B84F" />
              <path d="M69,55 C65,46 64,39 68,39 C72,39 73,46 72,52" fill="#EAE6DB" />
              {/* Right ear */}
              <path d="M132,58 C138,45 140,35 132,35 C124,35 124,45 126,53" fill="#E5B84F" />
              <path d="M131,55 C135,46 136,39 132,39 C128,39 127,46 128,52" fill="#EAE6DB" />

              {/* Face patch (white oval) */}
              <ellipse cx="100" cy="120" rx="34" ry="26" fill="#FFFFFF" />

              {/* Eyes */}
              <circle cx="85" cy="115" r="4.5" fill="#1C2E2A" />
              <circle cx="115" cy="115" r="4.5" fill="#1C2E2A" />
              <circle cx="83.5" cy="113.5" r="1.5" fill="#FFFFFF" />
              <circle cx="113.5" cy="113.5" r="1.5" fill="#FFFFFF" />

              {/* Nose/mouth */}
              <path d="M97,122 L103,122 L100,125 Z" fill="#1C2E2A" />
              <path d="M96,128 Q100,131 104,128" stroke="#1C2E2A" strokeWidth="1.5" strokeLinecap="round" fill="none" />

              {/* Rosy cheeks */}
              <circle cx="74" cy="123" r="4" fill="#F87171" opacity="0.6" />
              <circle cx="126" cy="123" r="4" fill="#F87171" opacity="0.6" />

              {/* Cute little feet */}
              <ellipse cx="78" cy="158" rx="8" ry="4" fill="#C9A03C" />
              <ellipse cx="122" cy="158" rx="8" ry="4" fill="#C9A03C" />
            </svg>
          </div>
        </div>

        {/* Right Side Content */}
        <div className={styles.contentCol}>
          <p className={styles.subText}>Care that doesn't go stale</p>
          <h2 className={styles.mainTitle}>Support for every questions, every Day.</h2>
          
          <p className={styles.descText}>
            Bobby is your Ai support Agent, always here to help with your tickets, questions, and updates.
          </p>

          <div className={styles.features}>
            <div className={styles.featureItem}>
              <div className={styles.featureIcon}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/>
                  <path d="M13 5v14"/>
                </svg>
              </div>
              <div>
                <h4 className={styles.featureTitle}>Ticket Support</h4>
                <p className={styles.featureDesc}>Raise, track, and update IT support tickets.</p>
              </div>
            </div>

            <div className={styles.featureItem}>
              <div className={styles.featureIcon}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3Z"/>
                </svg>
              </div>
              <div>
                <h4 className={styles.featureTitle}>Instant Assistance</h4>
                <p className={styles.featureDesc}>Get quick answers to common IT questions.</p>
              </div>
            </div>

            <div className={styles.featureItem}>
              <div className={styles.featureIcon}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </div>
              <div>
                <h4 className={styles.featureTitle}>Smart Escalation</h4>
                <p className={styles.featureDesc}>Automatically route unresolved issues to the right support team.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
