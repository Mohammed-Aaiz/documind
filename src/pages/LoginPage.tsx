import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Icon } from '../features/workspace/WorkspaceSidebar';

export const LoginPage: React.FC<{ onLoginSuccess: () => void }> = ({ onLoginSuccess }) => {
  const { login, register } = useAuth();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    if (creating) {
      if (!name.trim()) { setError('Enter your name.'); return; }
      if (password.length < 8 || new TextEncoder().encode(password).length > 72) {
        setError('Use at least 8 characters and no more than 72 UTF-8 bytes for your password.'); return;
      }
      if (password !== confirmation) { setError('Your passwords do not match.'); return; }
    }
    setLoading(true);
    try {
      if (creating) await register(name.trim(), email.trim(), password);
      else await login(email.trim(), password);
      onLoginSuccess();
    } catch (reason) {
      setError(reason instanceof TypeError ? 'Cannot reach DocuMind. Check that the backend is running and try again.' : reason instanceof Error ? reason.message : 'Could not sign in. Please try again.');
    } finally { setLoading(false); }
  }
  return <div className="dm-login">
    <section className="dm-login-story"><div className="dm-brand"><span className="dm-brand-symbol"><Icon name="auto_stories" /></span>DocuMind<span className="dm-brand-dot">.</span></div><div className="dm-login-story-content"><span className="dm-eyebrow">A WORKSPACE FOR CURIOUS MINDS</span><h1>Your sources.<br />Your questions.<br /><em>Your next idea.</em></h1><p>Turn the material you read into knowledge you can use. A focused space for studying and research, with evidence always within reach.</p><div className="dm-login-spaces"><span><Icon name="school" />Study with purpose</span><span><Icon name="biotech" />Research with clarity</span></div></div><p className="dm-login-footer">Built around evidence. Made for understanding.</p></section>
    <main className="dm-login-form"><div>
      <div className="dm-auth-tabs" aria-label="Account access">
        <button type="button" disabled={loading} aria-pressed={!creating} onClick={() => { setCreating(false); setError(''); }}>Sign in</button>
        <button type="button" disabled={loading} aria-pressed={creating} onClick={() => { setCreating(true); setError(''); }}>Create account</button>
      </div>
      <span className="dm-eyebrow">{creating ? 'YOUR NEXT CHAPTER' : 'WELCOME BACK'}</span>
      <h2>{creating ? 'Start with a curious mind.' : 'A clearer place to think.'}</h2>
      <p>{creating ? 'Create an account for your study and research.' : 'Sign in to your DocuMind workspace.'}</p>
      <form onSubmit={submit}>
        {creating && <><label htmlFor="register-name">Your name</label><input id="register-name" required maxLength={100} autoComplete="name" placeholder="Alex Morgan" value={name} onChange={(event) => setName(event.target.value)} /></>}
        <label htmlFor="login-email">Email address</label><input id="login-email" type="email" required autoComplete="username" placeholder="you@university.edu" value={email} onChange={(event) => setEmail(event.target.value)} />
        <div className="dm-password-label"><label htmlFor="login-password">Password</label><button type="button" aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? 'Hide' : 'Show'} password</button></div>
        <input id="login-password" type={showPassword ? 'text' : 'password'} required minLength={creating ? 8 : undefined} autoComplete={creating ? 'new-password' : 'current-password'} placeholder={creating ? 'At least 8 characters' : 'Your password'} value={password} onChange={(event) => setPassword(event.target.value)} />
        {creating && <><label htmlFor="confirm-password">Confirm password</label><input id="confirm-password" type={showPassword ? 'text' : 'password'} required autoComplete="new-password" placeholder="Enter your password again" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></>}
        {error && <p role="alert" className="dm-alert">{error}</p>}
        <button className="dm-button dm-primary" disabled={loading}>{loading ? (creating ? 'Creating account…' : 'Signing in…') : creating ? 'Create your workspace' : 'Enter workspace'}<Icon name="arrow_forward" /></button>
      </form>
      <p className="dm-login-help">{creating ? 'One account, two focused workspaces. Your Student and Research conversations stay separate.' : 'New to DocuMind? Choose Create account above to get started.'}</p>
    </div></main>
  </div>;
};
