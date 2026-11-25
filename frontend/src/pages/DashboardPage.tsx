import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api/ApiComponent'
import { BrandMark, ChevronDownIcon, LogoutIcon, PlusIcon } from '../components/Icons'
import { Modal } from '../components/Modal'
import { useAuth } from '../context/authContext'
import type { AppPage, Conference } from '../types/cmt'
import { AdminPage } from './AdminPage'
import { ConferencePage } from './ConferencePage'
import { ProfilePage } from './ProfilePage'
import { ReviewPage } from './ReviewPage'
import { SubmissionPage } from './SubmissionPage'

interface DashboardPageProps {
  activePage: AppPage
  onNavigate: (page: AppPage) => void
  pendingInviteToken: string | null
  onInviteConsumed: () => void
}

function formatDeadline(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function toDatetimeLocalValue(daysFromNow: number): string {
  const d = new Date(Date.now() + daysFromNow * 24 * 60 * 60 * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T23:59`
}

export function DashboardPage({
  activePage,
  onNavigate,
  pendingInviteToken,
  onInviteConsumed,
}: DashboardPageProps) {
  const { user, logout, hasRole } = useAuth()
  const [conferences, setConferences] = useState<Conference[]>([])
  const [selectedConferenceId, setSelectedConferenceId] = useState<string>('')
  const [confError, setConfError] = useState<string | null>(null)

  // Create conference modal state
  const [createOpen, setCreateOpen] = useState(false)
  const [confName, setConfName] = useState('')
  const [confDescription, setConfDescription] = useState('')
  const [subDeadline, setSubDeadline] = useState(() => toDatetimeLocalValue(30))
  const [revDeadline, setRevDeadline] = useState(() => toDatetimeLocalValue(60))
  const [notifDeadline, setNotifDeadline] = useState(() => toDatetimeLocalValue(90))
  const [creatingConf, setCreatingConf] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const refreshConferences = useCallback(async () => {
    try {
      const list = await api.conferences.list()
      setConferences(list)
      setSelectedConferenceId((prev) =>
        prev && list.some((c) => c.id === prev) ? prev : (list[0]?.id ?? ''),
      )
    } catch (err) {
      setConfError(err instanceof ApiError ? err.message : 'Failed to load conferences')
    }
  }, [])

  useEffect(() => {
    let active = true
    api.conferences
      .list()
      .then((list) => {
        if (active) {
          setConferences(list)
          setSelectedConferenceId((prev) =>
            prev && list.some((c) => c.id === prev) ? prev : (list[0]?.id ?? ''),
          )
        }
      })
      .catch((err) => {
        if (active) {
          setConfError(err instanceof ApiError ? err.message : 'Failed to load conferences')
        }
      })
    return () => {
      active = false
    }
  }, [])

  async function handleCreateConference(event: FormEvent) {
    event.preventDefault()
    setCreateError(null)
    setCreatingConf(true)
    try {
      const created = await api.conferences.create({
        name: confName,
        description: confDescription || undefined,
        submission_deadline: new Date(subDeadline).toISOString(),
        review_deadline: new Date(revDeadline).toISOString(),
        notification_deadline: new Date(notifDeadline).toISOString(),
      })
      await refreshConferences()
      setSelectedConferenceId(created.id)
      setConfName('')
      setConfDescription('')
      setCreateOpen(false)
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : 'Could not create conference')
    } finally {
      setCreatingConf(false)
    }
  }

  if (!user) return null

  const activeConference =
    conferences.find((c) => c.id === selectedConferenceId) ?? conferences[0] ?? null
  const initials = `${user.first_name[0] ?? ''}${user.last_name[0] ?? ''}`.toUpperCase()

  const navItems: { id: AppPage; label: string; visible: boolean }[] = [
    { id: 'papers', label: 'Papers', visible: hasRole('author') },
    {
      id: 'reviews',
      label: 'Reviews',
      visible: hasRole('reviewer') || Boolean(pendingInviteToken),
    },
    { id: 'chair', label: 'Chair', visible: hasRole('organizer') },
    { id: 'admin', label: 'Admin', visible: hasRole('admin') },
  ]

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="topbar-left">
            <button
              type="button"
              className="brand-lockup"
              onClick={() => onNavigate('papers')}
            >
              <BrandMark />
              <span>EAMT CMT</span>
            </button>

            {conferences.length > 0 && (
              <div className="conf-select-wrap">
                <select
                  className="conf-select"
                  aria-label="Select conference"
                  value={activeConference?.id ?? ''}
                  onChange={(e) => setSelectedConferenceId(e.target.value)}
                >
                  {conferences.map((conf) => (
                    <option key={conf.id} value={conf.id}>
                      {conf.name}
                    </option>
                  ))}
                </select>
                <span className="conf-select-chevron">
                  <ChevronDownIcon />
                </span>
              </div>
            )}

            {(hasRole('organizer') || hasRole('admin')) && (
              <button
                type="button"
                className="icon-circle-btn"
                title="Create conference"
                aria-label="Create conference"
                onClick={() => {
                  setCreateError(null)
                  setCreateOpen(true)
                }}
              >
                <PlusIcon />
              </button>
            )}
          </div>

          <nav className="nav-pill-track" aria-label="Primary navigation">
            {navItems
              .filter((item) => item.visible)
              .map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`nav-pill-item${activePage === item.id ? ' active' : ''}`}
                  onClick={() => onNavigate(item.id)}
                >
                  {item.label}
                </button>
              ))}
          </nav>

          <div className="topbar-right">
            <button
              type="button"
              className={`user-pill-btn${activePage === 'profile' ? ' active' : ''}`}
              onClick={() => onNavigate('profile')}
            >
              <span className="user-initials">{initials}</span>
              <span>{user.first_name}</span>
            </button>

            <button
              type="button"
              className="icon-circle-btn"
              title="Log out"
              aria-label="Log out"
              onClick={() => {
                void logout()
              }}
            >
              <LogoutIcon />
            </button>
          </div>
        </div>
      </header>

      {activeConference && (
        <div className="conf-subbar">
          <div className="conf-subbar-inner">
            <div className="conf-title-line">
              <strong>{activeConference.name}</strong>
              {activeConference.description ? ` — ${activeConference.description}` : ''}
            </div>
            <div className="conf-deadlines">
              <span>Submit by {formatDeadline(activeConference.submission_deadline)}</span>
              <span>Review by {formatDeadline(activeConference.review_deadline)}</span>
              <span>Decisions {formatDeadline(activeConference.notification_deadline)}</span>
            </div>
          </div>
        </div>
      )}

      <main className="workspace-main">
        {confError && <div className="alert alert-error">{confError}</div>}
        {activePage === 'papers' && <SubmissionPage conference={activeConference} />}
        {activePage === 'reviews' && (
          <ReviewPage
            conference={activeConference}
            initialInviteToken={pendingInviteToken}
            onInviteConsumed={onInviteConsumed}
          />
        )}
        {activePage === 'chair' && <ConferencePage conference={activeConference} />}
        {activePage === 'admin' && <AdminPage />}
        {activePage === 'profile' && <ProfilePage />}
      </main>

      {createOpen && (
        <Modal
          title="Create conference"
          icon={<PlusIcon />}
          onClose={() => setCreateOpen(false)}
        >
          {createError && <div className="alert alert-error">{createError}</div>}
          <form onSubmit={handleCreateConference}>
            <div className="form-field">
              <label className="form-label" htmlFor="conf-name">
                Conference name
              </label>
              <input
                id="conf-name"
                className="input"
                placeholder="e.g., EAMT 2029"
                value={confName}
                onChange={(e) => setConfName(e.target.value)}
                required
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="conf-desc">
                Description
              </label>
              <textarea
                id="conf-desc"
                className="textarea"
                placeholder="Track or conference summary..."
                value={confDescription}
                onChange={(e) => setConfDescription(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="conf-sub-dl">
                Submission deadline
              </label>
              <input
                id="conf-sub-dl"
                type="datetime-local"
                className="input"
                value={subDeadline}
                onChange={(e) => setSubDeadline(e.target.value)}
                required
              />
            </div>

            <div className="form-grid-2">
              <div className="form-field">
                <label className="form-label" htmlFor="conf-rev-dl">
                  Review deadline
                </label>
                <input
                  id="conf-rev-dl"
                  type="datetime-local"
                  className="input"
                  value={revDeadline}
                  onChange={(e) => setRevDeadline(e.target.value)}
                  required
                />
              </div>
              <div className="form-field">
                <label className="form-label" htmlFor="conf-not-dl">
                  Notification deadline
                </label>
                <input
                  id="conf-not-dl"
                  type="datetime-local"
                  className="input"
                  value={notifDeadline}
                  onChange={(e) => setNotifDeadline(e.target.value)}
                  required
                />
              </div>
            </div>

            <span className="form-hint">
              Deadlines must be ordered chronologically: Submission &lt; Review &lt; Notification.
            </span>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-soft"
                onClick={() => setCreateOpen(false)}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={creatingConf}>
                {creatingConf ? 'Creating...' : 'Create conference'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
