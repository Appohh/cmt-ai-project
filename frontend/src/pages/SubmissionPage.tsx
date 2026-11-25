import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api/ApiComponent'
import {
  CommentIcon,
  DownloadIcon,
  EditIcon,
  PlusIcon,
  TrashIcon,
  UploadIcon,
} from '../components/Icons'
import { Modal } from '../components/Modal'
import type {
  CoAuthorInput,
  Conference,
  Submission,
  SubmissionReviewsResponse,
} from '../types/cmt'

interface SubmissionPageProps {
  conference: Conference | null
}

function statusBadgeClass(status: Submission['status']): string {
  if (status === 'accepted') return 'badge badge-accepted'
  if (status === 'submitted') return 'badge badge-submitted'
  if (status === 'rejected') return 'badge badge-rejected'
  return 'badge badge-withdrawn'
}

export function SubmissionPage({ conference }: SubmissionPageProps) {
  const conferenceId = conference?.id
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Submit / Edit modal state
  const [formOpen, setFormOpen] = useState(false)
  const [editingSub, setEditingSub] = useState<Submission | null>(null)
  const [title, setTitle] = useState('')
  const [abstract, setAbstract] = useState('')
  const [coAuthors, setCoAuthors] = useState<CoAuthorInput[]>([])
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  // Reviews modal state
  const [reviewsTarget, setReviewsTarget] = useState<Submission | null>(null)
  const [reviewsData, setReviewsData] = useState<SubmissionReviewsResponse | null>(null)
  const [reviewsError, setReviewsError] = useState<string | null>(null)
  const [reviewsLoading, setReviewsLoading] = useState(false)

  const loadSubmissions = useCallback(async () => {
    setError(null)
    try {
      const data = await api.submissions.listMine(conferenceId)
      setSubmissions(data)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load submissions')
    } finally {
      setLoading(false)
    }
  }, [conferenceId])

  useEffect(() => {
    let active = true
    api.submissions
      .listMine(conferenceId)
      .then((data) => {
        if (active) {
          setSubmissions(data)
          setError(null)
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof ApiError ? err.message : 'Failed to load submissions')
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

  function openNewModal() {
    setEditingSub(null)
    setTitle('')
    setAbstract('')
    setCoAuthors([])
    setPdfFile(null)
    setFormError(null)
    setFormOpen(true)
  }

  function openEditModal(sub: Submission) {
    setEditingSub(sub)
    setTitle(sub.title)
    setAbstract(sub.abstract)
    setCoAuthors(
      sub.co_authors.map((ca) => ({
        name: ca.name,
        email: ca.email,
        affiliation: ca.affiliation ?? '',
      })),
    )
    setPdfFile(null)
    setFormError(null)
    setFormOpen(true)
  }

  async function handleFormSubmit(event: FormEvent) {
    event.preventDefault()
    if (!conference) return
    setFormError(null)

    if (!editingSub && !pdfFile) {
      setFormError('Please choose a manuscript PDF file.')
      return
    }

    setSaving(true)
    try {
      const cleanedCoAuthors = coAuthors
        .filter((ca) => ca.name.trim() && ca.email.trim())
        .map((ca) => ({
          name: ca.name.trim(),
          email: ca.email.trim(),
          affiliation: ca.affiliation?.trim() || undefined,
        }))

      if (editingSub) {
        await api.submissions.update(editingSub.id, {
          title,
          abstract,
          co_authors: cleanedCoAuthors,
          file: pdfFile,
        })
      } else if (pdfFile) {
        await api.submissions.create({
          conference_id: conference.id,
          title,
          abstract,
          co_authors: cleanedCoAuthors,
          file: pdfFile,
        })
      }
      setFormOpen(false)
      await loadSubmissions()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Could not save submission')
    } finally {
      setSaving(false)
    }
  }

  async function handleWithdraw(sub: Submission) {
    if (!window.confirm(`Withdraw "${sub.title}"? This cannot be undone.`)) return
    setError(null)
    try {
      await api.submissions.withdraw(sub.id)
      await loadSubmissions()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to withdraw submission')
    }
  }

  async function handleDownload(sub: Submission) {
    setError(null)
    try {
      await api.submissions.downloadPdf(sub.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to download PDF')
    }
  }

  async function openReviewsModal(sub: Submission) {
    setReviewsTarget(sub)
    setReviewsData(null)
    setReviewsError(null)
    setReviewsLoading(true)
    try {
      const data = await api.submissions.getReviews(sub.id)
      setReviewsData(data)
    } catch (err) {
      setReviewsError(
        err instanceof ApiError ? err.message : 'Reviews are not available yet.',
      )
    } finally {
      setReviewsLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">My Papers</h1>
          <p className="page-subtitle">
            Submit manuscripts, manage co-authors, and view released decisions.
          </p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={openNewModal}
            disabled={!conference}
          >
            <PlusIcon />
            New submission
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="surface-card empty-state">Loading your papers...</div>
      ) : submissions.length === 0 ? (
        <div className="surface-card empty-state">
          No papers submitted to {conference?.name ?? 'this conference'} yet.
        </div>
      ) : (
        <div className="paper-stack">
          {submissions.map((sub) => (
            <div key={sub.id} className="surface-card paper-card">
              <div className="paper-card-body">
                <div className="paper-meta-row">
                  <span className={statusBadgeClass(sub.status)}>
                    {sub.status.charAt(0).toUpperCase() + sub.status.slice(1)}
                  </span>
                  <span className="release-note">
                    {sub.decision_released ? 'Decision released' : 'Awaiting release date'}
                  </span>
                </div>
                <h2 className="paper-title">{sub.title}</h2>
                <p className="paper-abstract">{sub.abstract}</p>
                {sub.topic_tags.length > 0 && (
                  <div className="ai-tag-list">
                    {sub.topic_tags.map((tag, idx) => (
                      <span key={tag} className={`ai-tag ai-tag-${idx % 5}`}>
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {sub.co_authors.length > 0 && (
                  <div className="paper-coauthors">
                    Co-authors: {sub.co_authors.map((ca) => ca.name).join(', ')}
                  </div>
                )}
              </div>

              <div className="paper-actions">
                <button
                  type="button"
                  className="btn btn-soft btn-sm"
                  onClick={() => handleDownload(sub)}
                >
                  <DownloadIcon />
                  PDF
                </button>
                {sub.can_edit && (
                  <>
                    <button
                      type="button"
                      className="btn btn-soft btn-sm"
                      onClick={() => openEditModal(sub)}
                    >
                      <EditIcon />
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger-soft btn-sm"
                      onClick={() => handleWithdraw(sub)}
                    >
                      Withdraw
                    </button>
                  </>
                )}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => openReviewsModal(sub)}
                >
                  <CommentIcon />
                  Reviews
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {formOpen && conference && (
        <Modal
          title={
            editingSub
              ? `Edit "${editingSub.title}"`
              : `Submit to "${conference.name}"`
          }
          icon={<UploadIcon />}
          onClose={() => setFormOpen(false)}
        >
          {formError && <div className="alert alert-error">{formError}</div>}
          <form onSubmit={handleFormSubmit}>
            <div className="form-field">
              <label className="form-label" htmlFor="paper-title">
                Paper title
              </label>
              <input
                id="paper-title"
                className="input"
                placeholder="Enter paper title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="paper-abstract">
                Abstract
              </label>
              <textarea
                id="paper-abstract"
                className="textarea"
                placeholder="Summarize your paper..."
                value={abstract}
                onChange={(e) => setAbstract(e.target.value)}
                required
              />
            </div>

            <div className="subtle-box">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span className="form-label" style={{ margin: 0 }}>
                  Co-authors
                </span>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() =>
                    setCoAuthors((prev) => [...prev, { name: '', email: '', affiliation: '' }])
                  }
                >
                  + Add
                </button>
              </div>

              {coAuthors.length === 0 ? (
                <p className="form-hint" style={{ marginTop: 6 }}>
                  No co-authors added.
                </p>
              ) : (
                coAuthors.map((ca, idx) => (
                  <div key={idx} className="coauthor-row">
                    <input
                      className="input"
                      placeholder="Full name"
                      value={ca.name}
                      onChange={(e) => {
                        const val = e.target.value
                        setCoAuthors((prev) =>
                          prev.map((item, i) => (i === idx ? { ...item, name: val } : item)),
                        )
                      }}
                      required
                    />
                    <input
                      type="email"
                      className="input"
                      placeholder="Email"
                      value={ca.email}
                      onChange={(e) => {
                        const val = e.target.value
                        setCoAuthors((prev) =>
                          prev.map((item, i) => (i === idx ? { ...item, email: val } : item)),
                        )
                      }}
                      required
                    />
                    <input
                      className="input"
                      placeholder="Affiliation"
                      value={ca.affiliation ?? ''}
                      onChange={(e) => {
                        const val = e.target.value
                        setCoAuthors((prev) =>
                          prev.map((item, i) =>
                            i === idx ? { ...item, affiliation: val } : item,
                          ),
                        )
                      }}
                    />
                    <button
                      type="button"
                      className="icon-trash-btn"
                      aria-label="Remove co-author"
                      onClick={() =>
                        setCoAuthors((prev) => prev.filter((_, i) => i !== idx))
                      }
                    >
                      <TrashIcon />
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="form-field">
              <label className="form-label" htmlFor="paper-pdf">
                Manuscript PDF (max 10 MB){editingSub ? ' — optional replacement' : ''}
              </label>
              <input
                id="paper-pdf"
                type="file"
                accept=".pdf,application/pdf"
                className="input"
                onChange={(e) => setPdfFile(e.target.files?.[0] ?? null)}
              />
              <span className="form-hint">
                Author metadata is stripped automatically for blind review.
              </span>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-soft"
                onClick={() => setFormOpen(false)}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving...' : editingSub ? 'Save changes' : 'Submit paper'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {reviewsTarget && (
        <Modal
          title={reviewsTarget.title}
          icon={<CommentIcon />}
          onClose={() => setReviewsTarget(null)}
        >
          {reviewsLoading ? (
            <p className="release-note">Loading reviews...</p>
          ) : reviewsError ? (
            <div className="alert alert-info">{reviewsError}</div>
          ) : reviewsData ? (
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 14,
                }}
              >
                <span className="release-note">
                  Average score:{' '}
                  <strong>
                    {reviewsData.average_score !== null
                      ? `${reviewsData.average_score}/5`
                      : '—'}
                  </strong>
                </span>
                <span className={statusBadgeClass(reviewsTarget.status)}>
                  {reviewsData.status}
                </span>
              </div>

              {reviewsData.reviews.length === 0 ? (
                <div className="alert alert-info">No completed reviews recorded.</div>
              ) : (
                reviewsData.reviews.map((rev, index) => (
                  <div key={rev.id} className="subtle-box">
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        marginBottom: 6,
                        fontSize: 13,
                        fontWeight: 600,
                      }}
                    >
                      <span>Reviewer #{index + 1}</span>
                      <span className="release-note">
                        Score {rev.score}/5 · Confidence {rev.confidence}/5
                      </span>
                    </div>
                    <p style={{ fontSize: 13.5, color: 'var(--ink-secondary)' }}>
                      {rev.comments}
                    </p>
                  </div>
                ))
              )}
            </div>
          ) : null}
        </Modal>
      )}
    </div>
  )
}
