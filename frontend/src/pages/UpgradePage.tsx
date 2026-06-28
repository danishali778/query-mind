import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { T } from '../components/dashboard/tokens';
import { upgradePlan } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/common/ToastProvider';

export function UpgradePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);

  const handleConfirmUpgrade = async () => {
    setLoading(true);
    
    // Check if user has provided a real Lemon Squeezy URL in the .env file
    const checkoutUrl = import.meta.env.VITE_LEMON_SQUEEZY_CHECKOUT_URL;
    
    if (checkoutUrl) {
      // Real SaaS Flow: Send them to Lemon Squeezy with their user_id attached!
      let url = new URL(checkoutUrl);
      if (user?.id) {
        url.searchParams.append('checkout[custom][user_id]', user.id);
      }
      window.location.href = url.toString();
      return; 
    }

    // Fallback: Portfolio Demo Flow (If no URL is provided, simulate payment)
    try {
      console.warn("No VITE_LEMON_SQUEEZY_CHECKOUT_URL found. Simulating payment.");
      await upgradePlan();
      addToast('Upgraded to Pro. Limits and counters reset.', 'success');
      navigate('/settings');
    } catch (err) {
      console.error(err);
      const msg = err instanceof Error ? err.message : 'Upgrade failed. Please try again.';
      addToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: T.s1,
      fontFamily: T.fontBody,
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '60px 24px',
    }}>
      
      {/* Header */}
      <div style={{ textAlign: 'center', maxWidth: 600, marginBottom: 50 }}>
        <h1 style={{ fontFamily: T.fontHead, fontWeight: 800, fontSize: '2.4rem', color: T.text, margin: '0 0 16px 0', letterSpacing: '-0.03em' }}>
          Upgrade to <span style={{ background: `linear-gradient(135deg, ${T.accent}, ${T.purple})`, WebkitBackgroundClip: 'text', color: 'transparent' }}>query-mind Pro</span>
        </h1>
        <p style={{ fontSize: '1.05rem', color: T.text2, lineHeight: 1.6, margin: 0 }}>
          Unleash the full power of autonomous AI database analytics. Run complex graphs, automate dashboards, and never hit a limit again.
        </p>
      </div>

      {/* Pricing Cards Container */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', justifyContent: 'center', width: '100%', maxWidth: 900 }}>
        
        {/* Free Tier */}
        <div style={{
          flex: '1 1 350px', maxWidth: 400,
          background: T.s2, border: `1px solid ${T.border}`, borderRadius: 24,
          padding: '32px 32px 40px', display: 'flex', flexDirection: 'column'
        }}>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: T.text, marginBottom: 8, fontFamily: T.fontHead }}>Hobbyist</div>
          <div style={{ fontSize: '0.86rem', color: T.text3, marginBottom: 24 }}>Perfect for trying out the platform.</div>
          
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 32 }}>
            <span style={{ fontSize: '2.5rem', fontWeight: 800, color: T.text, fontFamily: T.fontHead }}>$0</span>
            <span style={{ fontSize: '0.9rem', color: T.text3 }}>/month</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, marginBottom: 32 }}>
            <Feature icon="✓" text="1 Database Connection" />
            <Feature icon="✓" text="100 Manual Query Runs /mo" />
            <Feature icon="✓" text="30 AI Requests /mo" color={T.yellow} />
            <Feature icon="✓" text="Standard Charting" />
            <Feature icon="✗" text="AI Graphing Autosave" disabled />
          </div>

          <button 
            onClick={() => navigate('/settings')}
            style={{
              width: '100%', padding: '14px', borderRadius: 12, border: `1px solid ${T.border2}`,
              background: 'transparent', color: T.text2, fontWeight: 600, fontSize: '0.95rem', cursor: 'pointer',
              transition: 'background 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = T.border}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            Current Plan
          </button>
        </div>

        {/* Pro Tier (Highlighted) */}
        <div style={{
          flex: '1 1 350px', maxWidth: 420,
          background: `linear-gradient(135deg, ${T.s1}, rgba(124,58,255,0.05))`, 
          border: `2px solid ${T.purple}`, borderRadius: 24,
          padding: '32px 32px 40px', display: 'flex', flexDirection: 'column',
          boxShadow: '0 24px 48px rgba(124, 58, 255, 0.1)', position: 'relative'
        }}>
          <div style={{
            position: 'absolute', top: -14, left: '50%', transform: 'translateX(-50%)',
            background: `linear-gradient(135deg, ${T.accent}, ${T.purple})`, color: '#fff',
            fontSize: '0.75rem', fontWeight: 700, padding: '4px 14px', borderRadius: 20, letterSpacing: '0.05em', textTransform: 'uppercase'
          }}>
            Most Popular
          </div>

          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: T.text, marginBottom: 8, fontFamily: T.fontHead }}>Pro</div>
          <div style={{ fontSize: '0.86rem', color: T.text3, marginBottom: 24 }}>For teams moving fast with data.</div>
          
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 32 }}>
            <span style={{ fontSize: '2.5rem', fontWeight: 800, color: T.text, fontFamily: T.fontHead }}>$49</span>
            <span style={{ fontSize: '0.9rem', color: T.text3 }}>/month</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flex: 1, marginBottom: 32 }}>
            <Feature icon="✓" text="Unlimited DB Connections" />
            <Feature icon="✓" text="5,000 Manual Query Runs /mo" />
            <Feature icon="✓" text="500 AI Requests /mo" color={T.purple} />
            <Feature icon="✓" text="Advanced Interactive Charting" />
            <Feature icon="✓" text="Priority Background Sync" />
            <Feature icon="✓" text="API & Webhook Access" />
          </div>

          <button 
            onClick={handleConfirmUpgrade}
            disabled={loading}
            style={{
              width: '100%', padding: '14px', borderRadius: 12, border: 'none', cursor: loading ? 'wait' : 'pointer',
              background: `linear-gradient(135deg, ${T.accent}, ${T.purple})`,
              color: '#fff', fontWeight: 700, fontSize: '1rem',
              boxShadow: '0 8px 16px rgba(124,58,255,0.25)', transition: 'transform 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
            onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
          >
            {loading ? 'Processing via Stripe...' : 'Checkout via Lemon Squeezy'}
          </button>
          
          <div style={{ textAlign: 'center', marginTop: 16, fontSize: '0.75rem', color: T.text3 }}>
            {!import.meta.env.VITE_LEMON_SQUEEZY_CHECKOUT_URL 
              ? 'Local Sandbox: This will run locally without a redirect.'
              : 'Secured via Lemon Squeezy'}
          </div>
        </div>

      </div>
    </div>
  );
}

function Feature({ icon, text, disabled = false, color = T.green }: { icon: string; text: string; disabled?: boolean; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, opacity: disabled ? 0.4 : 1 }}>
      <div style={{ 
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        width: 20, height: 20, borderRadius: '50%', 
        background: disabled ? 'transparent' : `${color}25`, 
        color: disabled ? T.text3 : color, fontSize: '0.75rem', fontWeight: 800 
      }}>
        {icon}
      </div>
      <span style={{ fontSize: '0.9rem', color: disabled ? T.text3 : T.text2 }}>{text}</span>
    </div>
  );
}
