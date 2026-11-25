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
  AIProviderName,
  AIProviderStatus,
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

function tagColorClass(tag: string): string {
  let hash = 0
  for (let i = 0; i < tag.length; i += 1) {
    hash = (hash * 31 + tag.charCodeAt(i)) >>> 0
  }
  return `ai-tag-${hash % 5}`
}

export function ConferencePage({ conference }: ConferencePageProps) {
  const conferenceId = conference?.id
  const [subTab, setSubTab] = useState<'submissions' | 'committee'>('submissions')
  const [filter, setFilter] = useState<'all' | 'needs_reviews' | 'decided'>('all')
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [chairData, setChairData] = useState<ChairSubmissionsResponse | null>(null)
  const [committeeData, setCommitteeData] = useState<ConferenceCommitteeResponse | null>(null)
  const [aiStatus, setAiStatus] = useState<AIProviderStatus | null>(null)
  const [activeProvider, setActiveProvider] = useState<AIProviderName>('local')
  const [generatingTags, setGeneratingTags] = useState(false)
  const [aiNotice, setAiNotice] = useState<string | null>(null)
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
    if (!conferenceId) return
    setError(null)
    try {
      const [subsRes, commRes, provRes] = await Promise.all([
        api.conferences.getChairSubmissions(conferenceId),
        api.conferences.getCommittee(conferenceId),
        api.ai.getProviders(),
      ])
      setChairData(subsRes)
      setCommitteeData(commRes)
      setAiStatus(provRes)
      setActiveProvider(provRes.active_provider)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load chair workspace')
    } finally {
      setLoading(false)
    }
  }, [conferenceId])

  useEffect(() => {
    if (!conferenceId) return
    let active = true
    Promise.all([
      api.conferences.getChairSubmissions(conferenceId),
      api.conferences.getCommittee(conferenceId),
      api.ai.getProviders(),
    ])
      .then(([subsRes, commRes, provRes]) => {
        if (active) {
          setChairData(subsRes)
          setCommitteeData(commRes)
          setAiStatus(provRes)
          setActiveProvider(provRes.active_provider)
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
  }, [conferenceId])

  async function handleSwitchProvider(next: AIProviderName) {
    setActiveProvider(next)
    setAiNotice(null)
    try {
      const updated = await api.ai.updateProviders({ provider: next })
      setAiStatus(updated)
      setActiveProvider(updated.active_provider)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not switch AI provider')
    }
  }

  async function handleGenerateAllTags() {
    if (!conferenceId) return
    setError(null)
    setAiNotice(null)
    setGeneratingTags(true)
    try {
      const res = await api.ai.generateAllConferenceTags(conferenceId, activeProvider)
      setAiNotice(
        `Generated AI topic tags for ${res.submissions_tagged} papers & ${res.reviewers_tagged} reviewers (${res.provider}).`,
      )
      await loadWorkspace()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to generate AI topic tags')
    } finally {
      setGeneratingTags(false)
    }
  }

  async function runAiMatch(paper: ChairSubmissionItem, providerChoice: AIProviderName) {
    if (!conferenceId) return
    setAiLoading(true)
    setAssignError(null)
    try {
      const res = await api.ai.matchReviewers(conferenceId, paper.id, providerChoice)
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

  async function openAssignModal(paper: ChairSubmissionItem) {
    if (!conferenceId) return
    setAssignTarget(paper)
    setRecommendations([])
    const fallbackFirst = committeeData?.members.find((m) => m.roles.includes('reviewer'))
    setManualReviewerId(fallbackFirst?.id ?? '')
    await runAiMatch(paper, activeProvider)
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
    if (!conferenceId) return
    setInviteError(null)
    setCopied(false)
    setInviteSending(true)
    try {
      const res = await api.conferences.createInvitation(conferenceId, inviteEmail, inviteRole)
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
  const members = committeeData?.members ?? []

  // Collect all unique AI topic tags across submissions & reviewers for filtering (US-26)
  const tagSet = new Set<string>()
  for (const s of allSubmissions) {
    for (const t of s.topic_tags) tagSet.add(t)
  }
  for (const m of members) {
    for (const t of m.topic_tags) tagSet.add(t)
  }
  const allTags = Array.from(tagSet).sort((a, b) => a.localeCompare(b))

  const filteredSubmissions = allSubmissions.filter((sub) => {
    if (selectedTag && !sub.topic_tags.includes(selectedTag)) {
      return false
    }
    if (filter === 'needs_reviews') {
      return sub.reviews.length === 0 || sub.reviews.some((r) => r.score === null)
    }
    if (filter === 'decided') {
      return sub.status === 'accepted' || sub.status === 'rejected'
    }
    return true
  })

  const filteredMembers = selectedTag
    ? members.filter((m) => m.topic_tags.includes(selectedTag))
    : members

  const reviewerCandidates = members.filter((m) => m.roles.includes('reviewer'))

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Chair Workspace</h1>
          <p className="page-subtitle">
            Assign AI-matched reviewers, generate topic tags, and record paper decisions.
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

          <button
            type="button"
            className="btn btn-ai btn-sm"
            disabled={generatingTags || !conference}
            onClick={handleGenerateAllTags}
          >
            <SparklesIcon />
            {generatingTags ? 'Tagging...' : 'Generate AI Tags'}
          </button>

          {subTab === 'committee' && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
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
      {aiNotice && <div className="alert alert-success">{aiNotice}</div>}

      {/* AI Engine Switcher & Topic Tag Filter Bar */}
      <div className="surface-card ai-toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="ai-provider-pill">
            <SparklesIcon />
            AI Engine
          </span>
          <div className="segmented">
            {(['local', 'ollama', 'gemini'] as AIProviderName[]).map((prov) => (
              <button
                key={prov}
                type="button"
                className={`segmented-btn${activeProvider === prov ? ' active' : ''}`}
                onClick={() => handleSwitchProvider(prov)}
              >
                {prov === 'local'
                  ? 'Local TF-IDF'
                  : prov === 'ollama'
                    ? `Ollama${aiStatus?.ollama_reachable ? ' ●' : ''}`
                    : `Gemini${aiStatus?.gemini_configured ? ' ●' : ''}`}
              </button>
            ))}
          </div>
        </div>

        {allTags.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <button
              type="button"
              className={`ai-tag ${selectedTag === null ? 'ai-tag-active' : 'ai-tag-0'}`}
              onClick={() => setSelectedTag(null)}
            >
              All topics
            </button>
            {allTags.map((tag) => (
              <button
                key={tag}
                type="button"
                className={`ai-tag ${selectedTag === tag ? 'ai-tag-active' : tagColorClass(tag)}`}
                onClick={() => setSelectedTag((prev) => (prev === tag ? null : tag))}
              >
                <SparklesIcon />
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

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
                      <td style={{ maxWidth: 360 }}>
                        <div className="table-paper-title">{sub.title}</div>
                        <div className="table-paper-authors">
                          {[sub.author_name, ...sub.co_author_names].join(', ')}
                        </div>
                        {sub.topic_tags.length > 0 && (
                          <div className="ai-tag-list">
                            {sub.topic_tags.map((tag) => (
                              <button
                                key={tag}
                                type="button"
                                className={`ai-tag ${selectedTag === tag ? 'ai-tag-active' : tagColorClass(tag)}`}
                                onClick={() =>
                                  setSelectedTag((prev) => (prev === tag ? null : tag))
                                }
                              >
                                {tag}
                              </button>
                            ))}
                          </div>
                        )}
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
                            className="btn btn-ai btn-sm"
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
          {filteredMembers.map((member, idx) => {
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
                  {member.topic_tags.length > 0 && (
                    <div className="ai-tag-list">
                      {member.topic_tags.map((tag) => (
                        <button
                          key={tag}
                          type="button"
                          className={`ai-tag ${selectedTag === tag ? 'ai-tag-active' : tagColorClass(tag)}`}
                          onClick={() =>
                            setSelectedTag((prev) => (prev === tag ? null : tag))
                          }
                        >
                          {tag}
                        </button>
                      ))}
                    </div>
                  )}
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
          title={`AI Reviewers · ${assignTarget.title}`}
          icon={<SparklesIcon />}
          wide
          onClose={() => setAssignTarget(null)}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 10,
              marginBottom: 14,
              flexWrap: 'wrap',
            }}
          >
            <p className="release-note">
              Matched on title &amp; abstract only ({aiProviderLabel}); author PII &amp; COI
              excluded.
            </p>
            <div className="segmented">
              {(['local', 'ollama', 'gemini'] as AIProviderName[]).map((prov) => (
                <button
                  key={prov}
                  type="button"
                  className={`segmented-btn${activeProvider === prov ? ' active' : ''}`}
                  disabled={aiLoading}
                  onClick={() => {
                    setActiveProvider(prov)
                    void runAiMatch(assignTarget, prov)
                  }}
                >
                  {prov === 'local' ? 'Local' : prov === 'ollama' ? 'Ollama' : 'Gemini'}
                </button>
              ))}
            </div>
          </div>

          {assignError && <div className="alert alert-error">{assignError}</div>}

          {aiLoading ? (
            <div className="empty-state">Computing AI reviewer match scores...</div>
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
                    <span className="ai-tag ai-tag-0">
                      {Math.round(rec.score * 100)}% Match
                    </span>
                    <span className="release-note">{rec.active_reviews} active</span>
                  </div>
                  <div className="ai-candidate-exp">
                    {rec.expertise || rec.affiliation || 'Reviewer'}
                  </div>
                  {rec.topic_tags.length > 0 && (
                    <div className="ai-tag-list">
                      {rec.topic_tags.map((tag) => (
                        <span key={tag} className={`ai-tag ${tagColorClass(tag)}`}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
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
