import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api/ApiComponent'
import { useAuth } from '../context/authContext'

export function ProfilePage() {
  const { user, setUser, refreshUser } = useAuth()
  const [firstName, setFirstName] = useState(user?.first_name ?? '')
  const [lastName, setLastName] = useState(user?.last_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [affiliation, setAffiliation] = useState(user?.affiliation ?? '')
  const [expertise, setExpertise] = useState(user?.expertise ?? '')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMessage, setProfileMessage] = useState<string | null>(null)
  const [profileError, setProfileError] = useState<string | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)

  const [inviteToken, setInviteToken] = useState('')
  const [redeemingInvite, setRedeemingInvite] = useState(false)
  const [inviteMessage, setInviteMessage] = useState<string | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)

  async function handleSaveProfile(event: FormEvent) {
    event.preventDefault()
    setProfileMessage(null)
    setProfileError(null)
    setSavingProfile(true)
    try {
      const updated = await api.users.updateProfile({
        first_name: firstName,
        last_name: lastName,
        email,
        affiliation,
        expertise,
      })
      setUser(updated)
      setProfileMessage('Profile updated.')
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : 'Failed to save profile')
    } finally {
      setSavingProfile(false)
    }
  }

  async function handleChangePassword(event: FormEvent) {
    event.preventDefault()
    setPasswordMessage(null)
    setPasswordError(null)
    setSavingPassword(true)
    try {
      await api.users.changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setPasswordMessage('Password updated successfully.')
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : 'Failed to update password')
    } finally {
      setSavingPassword(false)
    }
  }

  async function handleRedeemInvite(event: FormEvent) {
    event.preventDefault()
    setInviteMessage(null)
    setInviteError(null)
    setRedeemingInvite(true)
    try {
      const res = await api.conferences.acceptInvitation(inviteToken)
      await refreshUser()
      setInviteToken('')
      setInviteMessage(`Invitation accepted — granted role: ${res.role_granted}.`)
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : 'Could not redeem invitation token')
    } finally {
      setRedeemingInvite(false)
    }
  }

  if (!user) return null

  return (
    <div style={{ maxWidth: 680, margin: '0 auto' }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">
            Manage your personal details, affiliation, and password.
          </p>
        </div>
      </div>

      <div className="surface-card profile-card">
        {profileError && <div className="alert alert-error">{profileError}</div>}
        {profileMessage && <div className="alert alert-success">{profileMessage}</div>}

        <form onSubmit={handleSaveProfile}>
          <div className="form-grid-2">
            <div className="form-field">
              <label className="form-label" htmlFor="prof-first">
                First name
              </label>
              <input
                id="prof-first"
                className="input"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="prof-last">
                Last name
              </label>
              <input
                id="prof-last"
                className="input"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="prof-email">
              Email
            </label>
            <input
              id="prof-email"
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="prof-aff">
              Affiliation
            </label>
            <input
              id="prof-aff"
              className="input"
              value={affiliation}
              onChange={(e) => setAffiliation(e.target.value)}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="prof-exp">
              Expertise
            </label>
            <textarea
              id="prof-exp"
              className="textarea"
              value={expertise}
              onChange={(e) => setExpertise(e.target.value)}
            />
          </div>

          <div className="form-footer-split">
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {user.roles.map((role) => (
                <span key={role} className="badge badge-neutral">
                  {role.charAt(0).toUpperCase() + role.slice(1)}
                </span>
              ))}
            </div>
            <button type="submit" className="btn btn-primary" disabled={savingProfile}>
              {savingProfile ? 'Saving...' : 'Save profile'}
            </button>
          </div>
        </form>

        <hr className="section-divider" />

        <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 14 }}>Change password</h2>
        {passwordError && <div className="alert alert-error">{passwordError}</div>}
        {passwordMessage && <div className="alert alert-success">{passwordMessage}</div>}

        <form onSubmit={handleChangePassword}>
          <div className="form-grid-2">
            <div className="form-field">
              <label className="form-label" htmlFor="prof-cur-pw">
                Current password
              </label>
              <input
                id="prof-cur-pw"
                type="password"
                className="input"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="prof-new-pw">
                New password
              </label>
              <input
                id="prof-new-pw"
                type="password"
                className="input"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-soft" disabled={savingPassword}>
              {savingPassword ? 'Updating...' : 'Update password'}
            </button>
          </div>
        </form>

        <hr className="section-divider" />

        <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>
          Redeem invitation token
        </h2>
        <p className="release-note" style={{ marginBottom: 14 }}>
          Paste a committee invitation token from a Chair to activate a Reviewer or Guest role.
        </p>
        {inviteError && <div className="alert alert-error">{inviteError}</div>}
        {inviteMessage && <div className="alert alert-success">{inviteMessage}</div>}

        <form onSubmit={handleRedeemInvite}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input
              className="input mono"
              placeholder="Paste invitation token"
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-soft" disabled={redeemingInvite}>
              {redeemingInvite ? 'Redeeming...' : 'Redeem'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
