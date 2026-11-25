import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api/ApiComponent'
import {
  CheckCircleIcon,
  ClipboardIcon,
  ShareIcon,
  SparklesIcon,
  TrashIcon,
  UserPlusIcon,
  XCircleIcon,
} from '../components/Icons'
import { Modal } from '../components/Modal'
import type {
  AIRecommendation,
  ChairSubmissionItem,
  ChairSubmissionsResponse,
  Conference,
  ConferenceCommitteeResponse,
} from '../types/cmt'

interface ConferencePageProps {
  conference: Conference | null
}

const BANNER_THEMES = [
  { bg: 'var(--banner-lavender)', text: 'var(--banner-lavender-text)' },
  { bg: 'var(--banner-mint)', text: 'var(--banner-mint-text)' },
  { bg: 'var(--banner-peach)', text: 'var(--banner-peach-text)' },
  { bg: 'var(--banner-sky)', text: 'var(--banner-sky-text)' },
]

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

function paperStatusBadge(status: ChairSubmissionItem['status']): string {
  if (status === 'accepted') return 'badge badge-accepted'
  if (status === 'submitted') return 'badge badge-submitted'
  if (status === 'rejected') return 'badge badge-rejected'
  return 'badge badge-withdrawn'
}

export function ConferencePage({ conference }: ConferencePageProps) {
  const [subTab, setSubTab] = useState<'submissions' | 'committee'>('submissions')
  const [filter, setFilter] = useState<'all' | 'needs_reviews' | 'decided'>('all')
  const [chairData, setChairData] = useState<ChairSubmissionsResponse | null>(null)
  const [committeeData, setCommitteeData] = useState<ConferenceCommitteeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Assign modal state
  const [assignTarget, setAssignTarget] = useState<ChairSubmissionItem | null>(null)
  const [recommendations, setRecommendations] = useState<AIRecommendation[]>([])
  const [aiLoading, setAiLoading] = useState(false)
  const [aiProviderLabel, setAiProviderLabel] = useState('local')
  const [manualReviewerId, setManualReviewerId] = useState('')
  const [assignError, setAssignError] = useState<string | null>(null)
  const [assignBusyId, setAssignBusyId] = useState<string | null>(null)

  // Decide modal state
  const [decideTarget, setDecideTarget] = useState<ChairSubmissionItem | null>(null)
  const [decideSaving, setDecideSaving] = useState(false)

  // Invite modal state
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'reviewer' | 'guest'>('reviewer')
  const [inviteSending, setInviteSending] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [latestInviteLink, setLatestInviteLink] = useState<string | null>(null)
  const [latestRawToken, setLatestRawToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const loadWorkspace = useCallback(async () => {
    if (!conference) return
    setError(null)
    try {
      const [subsRes, commRes] = await Promise.all([
        api.conferences.getChairSubmissions(conference.id),
        api.conferences.getCommittee(conference.id),
      ])
      setChairData(subsRes)
      setCommitteeData(commRes)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load chair workspace')
    } finally {
      setLoading(false)
    }
  }, [conference])

  useEffect(() => {
    if (!conference) return
    let active = true
    Promise.all([
      api.conferences.getChairSubmissions(conference.id),
      api.conferences.getCommittee(conference.id),
    ])
      .then(([subsRes, commRes]) => {
        if (active) {
          setChairData(subsRes)
          setCommitteeData(commRes)
          setError(null)
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof ApiError ? err.message : 'Failed to load chair workspace')
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [conference])

  async function openAssignModal(paper: ChairSubmissionItem) {
    if (!conference) return
    setAssignTarget(paper)
    setRecommendations([])
    setAssignError(null)
    setAiLoading(true)
    const fallbackFirst = committeeData?.members.find((m) => m.roles.includes('reviewer'))
    setManualReviewerId(fallbackFirst?.id ?? '')

    try {
      const res = await api.ai.matchReviewers(conference.id, paper.id)
      setRecommendations(res.recommendations)
      setAiProviderLabel(res.provider)
    } catch (err) {
      setAssignError(
        err instanceof ApiError
          ? err.message
          : 'AI matcher unavailable — use manual assignment below.',
      )
    } finally {
      setAiLoading(false)
    }
  }

  async function handleConfirmAssign(reviewerId: string) {
    if (!assignTarget || !reviewerId) return
    setAssignError(null)
    setAssignBusyId(reviewerId)
    try {
      await api.reviews.assignReviewer(assignTarget.id, reviewerId)
      setRecommendations((prev) =>
        prev.map((rec) =>
          rec.reviewer_id === reviewerId ? { ...rec, already_assigned: true } : rec,
        ),
      )
      await loadWorkspace()
    } catch (err) {
      setAssignError(err instanceof ApiError ? err.message : 'Could not assign reviewer')
    } finally {
      setAssignBusyId(null)
    }
  }

  async function handleUnassign(submissionId: string, reviewerId: string) {
    setError(null)
    try {
      await api.reviews.unassignReviewer(submissionId, reviewerId)
      await loadWorkspace()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not unassign reviewer')
    }
  }

  async function handleRecordDecision(decision: 'accepted' | 'rejected') {
    if (!decideTarget) return
    setDecideSaving(true)
    setError(null)
    try {
      await api.submissions.recordDecision(decideTarget.id, decision)
      setDecideTarget(null)
      await loadWorkspace()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save decision')
    } finally {
      setDecideSaving(false)
    }
  }

  async function handleSendInvite(event: FormEvent) {
    event.preventDefault()
    if (!conference) return
    setInviteError(null)
    setCopied(false)
    setInviteSending(true)
    try {
      const res = await api.conferences.createInvitation(conference.id, inviteEmail, inviteRole)
      setLatestInviteLink(res.invite_link)
      setLatestRawToken(res.raw_token)
      setInviteEmail('')
      await loadWorkspace()
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : 'Could not send invite')
    } finally {
      setInviteSending(false)
    }
  }

  async function handleCopyInviteLink() {
    const text = latestInviteLink || window.location.origin
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  const allSubmissions = chairData?.submissions ?? []
  const filteredSubmissions = allSubmissions.filter((sub) => {
    if (filter === 'needs_reviews') {
      return sub.reviews.length === 0 || sub.reviews.some((r) => r.score === null)
    }
    if (filter === 'decided') {
      return sub.status === 'accepted' || sub.status === 'rejected'
    }
    return true
  })

  const members = committeeData?.members ?? []
  const reviewerCandidates = members.filter((m) => m.roles.includes('reviewer'))

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Chair Workspace</h1>
          <p className="page-subtitle">
            Assign reviewers, monitor review completion, and record paper decisions.
          </p>
        </div>

        <div className="header-actions">
          <div className="segmented">
            <button
              type="button"
              className={`segmented-btn${subTab === 'submissions' ? ' active' : ''}`}
              onClick={() => setSubTab('submissions')}
            >
              Submissions ({allSubmissions.length})
            </button>
            <button
              type="button"
              className={`segmented-btn${subTab === 'committee' ? ' active' : ''}`}
              onClick={() => setSubTab('committee')}
            >
              Committee ({members.length})
            </button>
          </div>

          {subTab === 'committee' && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setInviteError(null)
                setLatestInviteLink(null)
                setLatestRawToken(null)
                setInviteOpen(true)
              }}
            >
              <ShareIcon />
              Invite member
            </button>
          )}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="surface-card empty-state">Loading chair workspace...</div>
      ) : subTab === 'submissions' ? (
        <>
          {chairData && (
            <div className="surface-card progress-strip">
              <div className="progress-stats">
                <span>
                  <strong>
                    {chairData.summary.completed_reviews}/{chairData.summary.total_reviews}
                  </strong>{' '}
                  reviews completed
                </span>
                <span className="text-amber">
                  {chairData.summary.missing_reviews} missing
                </span>
                <span>
                  <strong>{chairData.summary.unassigned_papers}</strong> unassigned papers
                </span>
              </div>

              <div className="segmented">
                <button
                  type="button"
                  className={`segmented-btn${filter === 'all' ? ' active' : ''}`}
                  onClick={() => setFilter('all')}
                >
                  All
                </button>
                <button
                  type="button"
                  className={`segmented-btn${filter === 'needs_reviews' ? ' active' : ''}`}
                  onClick={() => setFilter('needs_reviews')}
                >
                  Needs reviews
                </button>
                <button
                  type="button"
                  className={`segmented-btn${filter === 'decided' ? ' active' : ''}`}
                  onClick={() => setFilter('decided')}
                >
                  Decided
                </button>
              </div>
            </div>
          )}

          <div className="surface-card table-card">
            {filteredSubmissions.length === 0 ? (
              <div className="empty-state">No submissions match this filter.</div>
            ) : (
              <table className="cmt-table">
                <thead>
                  <tr>
                    <th>Paper</th>
                    <th>Reviewers</th>
                    <th>Avg score</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSubmissions.map((sub) => (
                    <tr key={sub.id}>
                      <td style={{ maxWidth: 340 }}>
                        <div className="table-paper-title">{sub.title}</div>
                        <div className="table-paper-authors">
                          {[sub.author_name, ...sub.co_author_names].join(', ')}
                        </div>
                      </td>

                      <td>
                        {sub.reviews.length === 0 ? (
                          <span className="release-note">Unassigned</span>
                        ) : (
                          sub.reviews.map((rev) => (
                            <div key={rev.review_id} className="reviewer-chip-row">
                              <span>{rev.reviewer_name}</span>
                              {rev.score !== null ? (
                                <span className="badge badge-neutral">{rev.score}/5</span>
                              ) : (
                                <>
                                  <span className="badge badge-neutral">
                                    {rev.status.charAt(0).toUpperCase() + rev.status.slice(1)}
                                  </span>
                                  <button
                                    type="button"
                                    className="icon-trash-btn"
                                    aria-label={`Unassign ${rev.reviewer_name}`}
                                    onClick={() => handleUnassign(sub.id, rev.reviewer_id)}
                                  >
                                    <TrashIcon />
                                  </button>
                                </>
                              )}
                            </div>
                          ))
                        )}
                      </td>

                      <td>
                        <strong>
                          {sub.average_score !== null ? `${sub.average_score}/5` : '—'}
                        </strong>
                      </td>

                      <td>
                        <span className={paperStatusBadge(sub.status)}>
                          {sub.status.charAt(0).toUpperCase() + sub.status.slice(1)}
                        </span>
                      </td>

                      <td>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            type="button"
                            className="btn btn-blue btn-sm"
                            onClick={() => openAssignModal(sub)}
                          >
                            <SparklesIcon />
                            Assign
                          </button>
                          <button
                            type="button"
                            className="btn btn-soft btn-sm"
                            onClick={() => setDecideTarget(sub)}
                          >
                            Decide
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      ) : (
        <div className="committee-grid">
          {members.map((member, idx) => {
            const theme = BANNER_THEMES[idx % BANNER_THEMES.length]
            return (
              <div key={member.id} className="surface-card committee-card">
                <div className="committee-index">#{String(idx + 1).padStart(2, '0')}</div>
                <div className="committee-banner" style={{ background: theme.bg }}>
                  <div className="committee-avatar" style={{ color: theme.text }}>
                    {getInitials(member.name)}
                  </div>
                </div>
                <div>
                  <div className="committee-name">{member.name}</div>
                  <div className="committee-aff">{member.affiliation || member.email}</div>
                </div>
                <div className="committee-expertise">
                  {member.expertise || 'No expertise keywords specified.'}
                </div>
                <div className="committee-footer">
                  {member.completed_reviews}/{member.total_assigned} reviews done
                </div>
              </div>
            )
          })}
        </div>
      )}

      {assignTarget && (
        <Modal
          title={`Assign reviewers · ${assignTarget.title}`}
          icon={<SparklesIcon />}
          wide
          onClose={() => setAssignTarget(null)}
        >
          <p className="release-note" style={{ marginBottom: 14 }}>
            Matched on title &amp; abstract only ({aiProviderLabel}); author details and conflicts
            of interest are excluded.
          </p>

          {assignError && <div className="alert alert-error">{assignError}</div>}

          {aiLoading ? (
            <div className="empty-state">Computing reviewer match scores...</div>
          ) : recommendations.length === 0 ? (
            <div className="alert alert-info">
              No eligible reviewer recommendations available. Use manual assignment below.
            </div>
          ) : (
            recommendations.map((rec, idx) => (
              <div key={rec.reviewer_id} className="ai-candidate-card">
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="ai-candidate-title">
                    <span className="mono" style={{ color: 'var(--ink-muted)' }}>
                      #{String(idx + 1).padStart(2, '0')}
                    </span>
                    <span>{rec.name || rec.reviewer_id}</span>
                    <span className="badge badge-submitted">
                      {Math.round(rec.score * 100)}% Match
                    </span>
                    <span className="release-note">{rec.active_reviews} active</span>
                  </div>
                  <div className="ai-candidate-exp">
                    {rec.expertise || rec.affiliation || 'Reviewer'}
                  </div>
                </div>

                {rec.already_assigned ? (
                  <button type="button" className="btn btn-soft btn-sm" disabled>
                    <CheckCircleIcon />
                    Assigned
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={assignBusyId === rec.reviewer_id}
                    onClick={() => handleConfirmAssign(rec.reviewer_id)}
                  >
                    <CheckCircleIcon />
                    {assignBusyId === rec.reviewer_id ? 'Assigning...' : 'Confirm'}
                  </button>
                )}
              </div>
            ))
          )}

          <div className="manual-assign-bar">
            <select
              value={manualReviewerId}
              onChange={(e) => setManualReviewerId(e.target.value)}
              aria-label="Select reviewer manually"
            >
              <option value="">Select committee reviewer...</option>
              {reviewerCandidates.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.email})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-soft btn-sm"
              disabled={!manualReviewerId || assignBusyId === manualReviewerId}
              onClick={() => handleConfirmAssign(manualReviewerId)}
            >
              <UserPlusIcon />
              Assign manually
            </button>
          </div>
        </Modal>
      )}

      {decideTarget && (
        <Modal
          title={decideTarget.title}
          icon={<CheckCircleIcon />}
          onClose={() => setDecideTarget(null)}
        >
          <p className="release-note" style={{ marginBottom: 14 }}>
            Average score:{' '}
            <strong>
              {decideTarget.average_score !== null ? `${decideTarget.average_score}/5` : '—'}
            </strong>
          </p>

          {decideTarget.reviews.filter((r) => r.score !== null).length === 0 ? (
            <div className="alert alert-info">No completed reviews submitted yet.</div>
          ) : (
            decideTarget.reviews
              .filter((r) => r.score !== null)
              .map((rev) => (
                <div key={rev.review_id} className="subtle-box">
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginBottom: 6,
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    <span>{rev.reviewer_name}</span>
                    <span className="release-note">
                      Score {rev.score}/5 · Confidence {rev.confidence}/5
                    </span>
                  </div>
                  <p style={{ fontSize: 13.5, color: 'var(--ink-secondary)' }}>{rev.comments}</p>
                </div>
              ))
          )}

          <div className="form-footer-split" style={{ marginTop: 18 }}>
            <span className="release-note">
              Current status: <strong>{decideTarget.status}</strong>
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={decideSaving}
                onClick={() => handleRecordDecision('accepted')}
              >
                <CheckCircleIcon />
                Accept
              </button>
              <button
                type="button"
                className="btn btn-danger-soft btn-sm"
                disabled={decideSaving}
                onClick={() => handleRecordDecision('rejected')}
              >
                <XCircleIcon />
                Reject
              </button>
            </div>
          </div>
        </Modal>
      )}

      {inviteOpen && conference && (
        <Modal
          title={`Invite to "${conference.name}"`}
          icon={<ShareIcon />}
          onClose={() => setInviteOpen(false)}
        >
          {inviteError && <div className="alert alert-error">{inviteError}</div>}
          <form onSubmit={handleSendInvite}>
            <div className="subtle-box" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="email"
                className="input"
                style={{ border: 'none', background: 'transparent', padding: '4px 6px' }}
                placeholder="Add people by email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                required
              />
              <select
                className="conf-select"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as 'reviewer' | 'guest')}
              >
                <option value="reviewer">Reviewer</option>
                <option value="guest">Guest</option>
              </select>
            </div>

            {latestInviteLink && latestRawToken && (
              <div className="alert alert-success">
                Invitation created! Token: <code className="mono">{latestRawToken}</code>
              </div>
            )}

            <div style={{ margin: '14px 0' }}>
              <div className="release-note" style={{ marginBottom: 10 }}>
                Committee members ({members.length})
              </div>
              {members.slice(0, 5).map((member, idx) => {
                const theme = BANNER_THEMES[idx % BANNER_THEMES.length]
                return (
                  <div
                    key={member.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '6px 0',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span
                        className="committee-avatar"
                        style={{
                          width: 30,
                          height: 30,
                          fontSize: 11,
                          background: theme.bg,
                          color: theme.text,
                          boxShadow: 'none',
                        }}
                      >
                        {getInitials(member.name)}
                      </span>
                      <span style={{ fontWeight: 500 }}>{member.name}</span>
                    </div>
                    <span className="release-note">
                      {member.roles.includes('reviewer') ? 'Reviewer' : 'Guest'}
                    </span>
                  </div>
                )
              })}
            </div>

            <div className="form-footer-split">
              <button
                type="button"
                className="btn btn-soft"
                onClick={handleCopyInviteLink}
              >
                <ClipboardIcon />
                {copied ? 'Copied!' : 'Copy link'}
              </button>
              <button type="submit" className="btn btn-primary" disabled={inviteSending}>
                {inviteSending ? 'Sending...' : 'Send invite'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
