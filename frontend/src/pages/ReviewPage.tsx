import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api/ApiComponent'
import { DownloadIcon, EyeOffIcon, KeyIcon } from '../components/Icons'
import { Modal } from '../components/Modal'
import { useAuth } from '../context/authContext'
import type { Conference, ReviewAssignment } from '../types/cmt'

interface ReviewPageProps {
  conference: Conference | null
  initialInviteToken?: string | null
  onInviteConsumed?: () => void
}

const SCORE_LABELS: Record<number, string> = {
  1: 'Strong Reject',
  2: 'Reject',
  3: 'Borderline',
  4: 'Accept',
  5: 'Strong Accept',
}

const CONFIDENCE_LABELS: Record<number, string> = {
  1: 'Very Low',
  2: 'Low',
  3: 'Medium',
  4: 'High',
  5: 'Expert',
}

function formatShortDate(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString('en-US', {
    month: 'numeric',
    day: 'numeric',
    year: 'numeric',
  })
}

export function ReviewPage({
  conference,
  initialInviteToken,
  onInviteConsumed,
}: ReviewPageProps) {
  const { refreshUser } = useAuth()
  const conferenceId = conference?.id
  const [assignments, setAssignments] = useState<ReviewAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Review editor modal state
  const [activeReview, setActiveReview] = useState<ReviewAssignment | null>(null)
  const [score, setScore] = useState(4)
  const [confidence, setConfidence] = useState(4)
  const [comments, setComments] = useState('')
  const [savingReview, setSavingReview] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)

  // Invite token modal state
  const [inviteOpen, setInviteOpen] = useState(Boolean(initialInviteToken))
  const [inviteToken, setInviteToken] = useState(initialInviteToken ?? '')
  const [inviteMessage, setInviteMessage] = useState<string | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [redeeming, setRedeeming] = useState(false)

  const loadAssignments = useCallback(async () => {
    setError(null)
    try {
      const data = await api.reviews.listAssigned(conferenceId)
      setAssignments(data)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load assigned reviews')
    } finally {
      setLoading(false)
    }
  }, [conferenceId])

  useEffect(() => {
    let active = true
    api.reviews
      .listAssigned(conferenceId)
      .then((data) => {
        if (active) {
          setAssignments(data)
          setError(null)
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof ApiError ? err.message : 'Failed to load assigned reviews')
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
  }, [conferenceId])

  async function handleRespond(reviewId: string, status: 'accepted' | 'declined') {
    setError(null)
    try {
      await api.reviews.respond(reviewId, status)
      await loadAssignments()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update invitation')
    }
  }

  async function handleDownloadBlindPdf(submissionId: string) {
    setError(null)
    try {
      await api.reviews.downloadBlindPdf(submissionId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not download blind PDF')
    }
  }

  function openReviewModal(item: ReviewAssignment) {
    setActiveReview(item)
    setScore(item.score ?? 4)
    setConfidence(item.confidence ?? 4)
    setComments(item.comments ?? '')
    setReviewError(null)
  }

  async function handleSaveReview(event: FormEvent) {
    event.preventDefault()
    if (!activeReview) return
    setReviewError(null)
    setSavingReview(true)
    try {
      await api.reviews.submit(activeReview.id, { score, confidence, comments })
      setActiveReview(null)
      await loadAssignments()
    } catch (err) {
      setReviewError(err instanceof ApiError ? err.message : 'Failed to save review')
    } finally {
      setSavingReview(false)
    }
  }

  async function handleRedeemInvite(event: FormEvent) {
    event.preventDefault()
    setInviteError(null)
    setInviteMessage(null)
    setRedeeming(true)
    try {
      const res = await api.conferences.acceptInvitation(inviteToken)
      await refreshUser()
      setInviteMessage(`Invitation accepted — granted role: ${res.role_granted}.`)
      setInviteToken('')
      onInviteConsumed?.()
      await loadAssignments()
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : 'Could not redeem invite token')
    } finally {
      setRedeeming(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Reviews</h1>
          <p className="page-subtitle">
            Double-blind evaluations. Author identities are hidden.
          </p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn btn-soft"
            onClick={() => {
              setInviteError(null)
              setInviteMessage(null)
              setInviteOpen(true)
            }}
          >
            <KeyIcon />
            Redeem invite token
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="surface-card empty-state">Loading your review assignments...</div>
      ) : assignments.length === 0 ? (
        <div className="surface-card empty-state">
          No papers assigned to you in {conference?.name ?? 'this conference'} yet.
        </div>
      ) : (
        <div className="reviews-grid">
          {assignments.map((item) => (
            <div key={item.id} className="surface-card review-card">
              <div className="review-card-top">
                <span className="badge badge-neutral">
                  <EyeOffIcon />
                  Anonymous
                </span>
                <span
                  className={
                    item.status === 'accepted'
                      ? 'badge badge-submitted'
                      : item.status === 'declined'
                        ? 'badge badge-declined'
                        : 'badge badge-neutral'
                  }
                >
                  {item.score !== null
                    ? `Scored ${item.score}/5`
                    : item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                </span>
              </div>

              <div className="review-card-meta">
                {item.conference_name} · Due {formatShortDate(item.review_deadline)}
              </div>

              <h2 className="paper-title" style={{ marginBottom: 0 }}>
                {item.title}
              </h2>
              <p className="paper-abstract" style={{ flex: 1 }}>
                {item.abstract}
              </p>

              <div className="paper-actions">
                {item.status === 'invited' && (
                  <>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => handleRespond(item.id, 'accepted')}
                    >
                      Accept invitation
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger-soft btn-sm"
                      onClick={() => handleRespond(item.id, 'declined')}
                    >
                      Decline
                    </button>
                  </>
                )}
                {item.status === 'accepted' && (
                  <>
                    <button
                      type="button"
                      className="btn btn-soft btn-sm"
                      onClick={() => handleDownloadBlindPdf(item.submission_id)}
                    >
                      <DownloadIcon />
                      Blind PDF
                    </button>
                    <button
                      type="button"
                      className="btn btn-blue btn-sm"
                      disabled={!item.can_review}
                      onClick={() => openReviewModal(item)}
                    >
                      {item.score !== null ? 'Edit review' : 'Write review'}
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeReview && (
        <Modal
          title={activeReview.title}
          icon={<EyeOffIcon />}
          wide
          onClose={() => setActiveReview(null)}
        >
          {reviewError && <div className="alert alert-error">{reviewError}</div>}
          <form onSubmit={handleSaveReview}>
            <div className="form-grid-2" style={{ marginBottom: 14 }}>
              <div>
                <div className="form-label" style={{ marginBottom: 8 }}>
                  Score — {SCORE_LABELS[score]}
                </div>
                <div className="score-row">
                  {[1, 2, 3, 4, 5].map((val) => (
                    <button
                      key={val}
                      type="button"
                      className={`score-btn${score === val ? ' active' : ''}`}
                      onClick={() => setScore(val)}
                    >
                      {val}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="form-label" style={{ marginBottom: 8 }}>
                  Confidence — {CONFIDENCE_LABELS[confidence]}
                </div>
                <div className="score-row">
                  {[1, 2, 3, 4, 5].map((val) => (
                    <button
                      key={val}
                      type="button"
                      className={`score-btn${confidence === val ? ' active' : ''}`}
                      onClick={() => setConfidence(val)}
                    >
                      {val}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="review-comments">
                Comments
              </label>
              <textarea
                id="review-comments"
                className="textarea"
                style={{ minHeight: 130 }}
                placeholder="Share constructive feedback, strengths, and weaknesses..."
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                required
              />
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-soft"
                onClick={() => setActiveReview(null)}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={savingReview}>
                {savingReview ? 'Saving...' : 'Save review'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {inviteOpen && (
        <Modal
          title="Redeem committee invite token"
          icon={<KeyIcon />}
          onClose={() => {
            setInviteOpen(false)
            onInviteConsumed?.()
          }}
        >
          {inviteError && <div className="alert alert-error">{inviteError}</div>}
          {inviteMessage && <div className="alert alert-success">{inviteMessage}</div>}
          <form onSubmit={handleRedeemInvite}>
            <div className="form-field">
              <label className="form-label" htmlFor="invite-token-input">
                Invitation token
              </label>
              <input
                id="invite-token-input"
                className="input mono"
                placeholder="Paste your invitation token"
                value={inviteToken}
                onChange={(e) => setInviteToken(e.target.value)}
                required
              />
              <span className="form-hint">
                Tokens are SHA-256 verified and expire automatically after their validity window.
              </span>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-soft"
                onClick={() => setInviteOpen(false)}
              >
                Close
              </button>
              <button type="submit" className="btn btn-primary" disabled={redeeming}>
                {redeeming ? 'Redeeming...' : 'Accept invitation'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
