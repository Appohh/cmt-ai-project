import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../api/ApiComponent'
import { BrandMark } from '../components/Icons'
import { useAuth } from '../context/authContext'

const DEMO_ACCOUNTS = [
  { label: 'Chair · chair@example.com', email: 'chair@example.com' },
  { label: 'Author · author@example.com', email: 'author@example.com' },
  { label: 'Reviewer 1 · reviewer@example.com', email: 'reviewer@example.com' },
  { label: 'Reviewer 2 · reviewer2@example.com', email: 'reviewer2@example.com' },
  { label: 'Reviewer 3 · reviewer3@example.com', email: 'reviewer3@example.com' },
  { label: 'Admin · admin@example.com', email: 'admin@example.com' },
  { label: 'Guest · guest@example.com', email: 'guest@example.com' },
  { label: 'All roles · demo@eamt.org', email: 'demo@eamt.org' },
]

export function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [affiliation, setAffiliation] = useState('')
  const [expertise, setExpertise] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register({
          first_name: firstName,
          last_name: lastName,
          email,
          password,
          affiliation: affiliation || undefined,
          expertise: expertise || undefined,
        })
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Authentication failed')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDemoLogin(demoEmail: string) {
    setError(null)
    setEmail(demoEmail)
    setPassword('password')
    setSubmitting(true)
    try {
      await login(demoEmail, 'password')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Demo sign-in failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-viewport">
      <div className="surface-card auth-card">
        <div className="auth-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <BrandMark />
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: '-0.02em' }}>
                EAMT CMT
              </div>
              <div className="auth-brand-sub">EAMT 2028</div>
            </div>
          </div>

          <div className="segmented">
            <button
              type="button"
              className={`segmented-btn${mode === 'login' ? ' active' : ''}`}
              onClick={() => {
                setMode('login')
                setError(null)
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              className={`segmented-btn${mode === 'register' ? ' active' : ''}`}
              onClick={() => {
                setMode('register')
                setError(null)
              }}
            >
              Register
            </button>
          </div>
        </div>

        <h1 className="auth-title">
          {mode === 'login' ? 'Welcome back' : 'Create your account'}
        </h1>
        <p className="auth-subtitle">
          {mode === 'login'
            ? 'Sign in to manage papers, reviews, or conference chairs.'
            : 'Register as an author to submit papers and participate in peer review.'}
        </p>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          {mode === 'register' && (
            <div className="form-grid-2">
              <div className="form-field">
                <label className="form-label" htmlFor="reg-first">
                  First name
                </label>
                <input
                  id="reg-first"
                  className="input"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                />
              </div>
              <div className="form-field">
                <label className="form-label" htmlFor="reg-last">
                  Last name
                </label>
                <input
                  id="reg-last"
                  className="input"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                />
              </div>
            </div>
          )}

          <div className="form-field">
            <label className="form-label" htmlFor="auth-email">
              Email
            </label>
            <input
              id="auth-email"
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="chair@example.com"
              required
            />
          </div>

          {mode === 'register' && (
            <>
              <div className="form-field">
                <label className="form-label" htmlFor="reg-aff">
                  Affiliation
                </label>
                <input
                  id="reg-aff"
                  className="input"
                  value={affiliation}
                  onChange={(e) => setAffiliation(e.target.value)}
                  placeholder="University or research lab"
                />
              </div>
              <div className="form-field">
                <label className="form-label" htmlFor="reg-exp">
                  Research expertise
                </label>
                <input
                  id="reg-exp"
                  className="input"
                  value={expertise}
                  onChange={(e) => setExpertise(e.target.value)}
                  placeholder="e.g., neural machine translation, privacy"
                />
              </div>
            </>
          )}

          <div className="form-field">
            <label className="form-label" htmlFor="auth-password">
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              minLength={mode === 'register' ? 8 : undefined}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary btn-full" disabled={submitting}>
            {submitting
              ? 'Please wait...'
              : mode === 'login'
                ? 'Sign in'
                : 'Create account'}
          </button>
        </form>

        {import.meta.env.DEV && mode === 'login' && (
          <div className="demo-divider">
            <div className="demo-label">
              Quick sign-in — real role accounts (password: <code className="mono">password</code>)
            </div>
            <div className="demo-pills">
              {DEMO_ACCOUNTS.map((acct) => (
                <button
                  key={acct.email}
                  type="button"
                  className="btn btn-soft btn-sm"
                  disabled={submitting}
                  onClick={() => handleDemoLogin(acct.email)}
                >
                  {acct.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
