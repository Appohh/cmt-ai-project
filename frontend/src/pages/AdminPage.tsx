import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, api } from '../api/ApiComponent'
import { SparklesIcon } from '../components/Icons'
import { useAuth } from '../context/authContext'
import type {
  AIProviderName,
  AIProviderStatus,
  AdminOverviewResponse,
  Role,
  UserPublic,
} from '../types/cmt'

const ALL_ROLES: Role[] = ['author', 'reviewer', 'organizer', 'admin', 'guest']

export function AdminPage() {
  const { user: currentUser, refreshUser } = useAuth()
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null)
  const [aiStatus, setAiStatus] = useState<AIProviderStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [roleBusyUserId, setRoleBusyUserId] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  // AI provider form state
  const [selectedProvider, setSelectedProvider] = useState<AIProviderName>('local')
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434')
  const [ollamaModel, setOllamaModel] = useState('llama3.2')
  const [geminiModel, setGeminiModel] = useState('gemini-3-flash-preview')
  const [geminiApiKey, setGeminiApiKey] = useState('')
  const [savingAi, setSavingAi] = useState(false)
  const [aiMessage, setAiMessage] = useState<string | null>(null)

  const loadAdminData = useCallback(async () => {
    setError(null)
    try {
      const [overviewRes, providersRes] = await Promise.all([
        api.users.getAdminOverview(),
        api.ai.getProviders(),
      ])
      setOverview(overviewRes)
      setAiStatus(providersRes)
      setSelectedProvider(providersRes.active_provider)
      setOllamaUrl(providersRes.ollama_base_url)
      setOllamaModel(providersRes.ollama_model)
      setGeminiModel(providersRes.gemini_model)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load admin overview')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([api.users.getAdminOverview(), api.ai.getProviders()])
      .then(([overviewRes, providersRes]) => {
        if (active) {
          setOverview(overviewRes)
          setAiStatus(providersRes)
          setSelectedProvider(providersRes.active_provider)
          setOllamaUrl(providersRes.ollama_base_url)
          setOllamaModel(providersRes.ollama_model)
          setGeminiModel(providersRes.gemini_model)
          setError(null)
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof ApiError ? err.message : 'Failed to load admin overview')
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
  }, [])

  async function handleToggleRole(targetUser: UserPublic, role: Role) {
    setError(null)
    setStatusMessage(null)
    const hasIt = targetUser.roles.includes(role)
    const nextRoles = hasIt
      ? targetUser.roles.filter((r) => r !== role)
      : [...targetUser.roles, role]

    if (nextRoles.length === 0) {
      setError('A user must keep at least one role.')
      return
    }

    setRoleBusyUserId(targetUser.id)
    try {
      const updated = await api.users.updateRoles(targetUser.id, nextRoles)
      setStatusMessage(
        `Updated roles for ${updated.first_name} ${updated.last_name}: ${updated.roles.join(', ')}`,
      )
      await loadAdminData()
      if (currentUser && targetUser.id === currentUser.id) {
        await refreshUser()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update user roles')
    } finally {
      setRoleBusyUserId(null)
    }
  }

  async function handleSaveAiSettings(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setAiMessage(null)
    setSavingAi(true)
    try {
      const updated = await api.ai.updateProviders({
        provider: selectedProvider,
        ollama_base_url: ollamaUrl,
        ollama_model: ollamaModel,
        gemini_model: geminiModel,
        gemini_api_key: geminiApiKey.trim() || undefined,
      })
      setAiStatus(updated)
      setGeminiApiKey('')
      setAiMessage(`AI provider updated to ${updated.active_provider}.`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update AI provider settings')
    } finally {
      setSavingAi(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Admin</h1>
          <p className="page-subtitle">
            System oversight, user role management, and AI provider configuration.
          </p>
        </div>

        <div className="header-actions">
          <span
            className={
              overview?.database_connected ? 'badge badge-accepted' : 'badge badge-neutral'
            }
          >
            {overview?.database_connected ? 'Database Connected' : 'Checking Database...'}
          </span>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {statusMessage && <div className="alert alert-success">{statusMessage}</div>}

      {loading ? (
        <div className="surface-card empty-state">Loading system overview...</div>
      ) : overview ? (
        <>
          <div className="surface-card metrics-card">
            <div className="metric-cell">
              <div className="metric-label">Users</div>
              <div className="metric-value">{overview.counts.users}</div>
              <div className="metric-sub">{overview.counts.reviewers} reviewers</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Conferences</div>
              <div className="metric-value">{overview.counts.conferences}</div>
              <div className="metric-sub">{overview.counts.open_invites} open invites</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Submissions</div>
              <div className="metric-value">{overview.counts.submissions}</div>
              <div className="metric-sub">{overview.counts.accepted_submissions} accepted</div>
            </div>
            <div className="metric-cell">
              <div className="metric-label">Reviews</div>
              <div className="metric-value">
                {overview.counts.completed_reviews}/{overview.counts.total_reviews}
              </div>
              <div className="metric-sub">{overview.counts.missing_reviews} missing</div>
            </div>
          </div>

          <div className="surface-card table-card" style={{ marginBottom: 18 }}>
            <table className="cmt-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Affiliation</th>
                  <th>Roles (click to toggle)</th>
                </tr>
              </thead>
              <tbody>
                {overview.users.map((u) => {
                  const isSelf = currentUser?.id === u.id
                  const isBusy = roleBusyUserId === u.id
                  return (
                    <tr key={u.id}>
                      <td style={{ fontWeight: 600 }}>
                        {u.first_name} {u.last_name}
                      </td>
                      <td className="mono" style={{ fontSize: 12.5 }}>
                        {u.email}
                      </td>
                      <td style={{ color: 'var(--ink-secondary)' }}>
                        {u.affiliation || '—'}
                      </td>
                      <td>
                        <div className="role-toggle-group">
                          {ALL_ROLES.map((role) => {
                            const active = u.roles.includes(role)
                            const lockedSelfAdmin = isSelf && role === 'admin' && active
                            return (
                              <button
                                key={role}
                                type="button"
                                className={`role-toggle${active ? ' active' : ''}`}
                                disabled={isBusy || lockedSelfAdmin}
                                title={
                                  lockedSelfAdmin
                                    ? 'You cannot remove your own Admin role'
                                    : active
                                      ? `Remove ${role}`
                                      : `Grant ${role}`
                                }
                                onClick={() => handleToggleRole(u, role)}
                              >
                                {role.charAt(0).toUpperCase() + role.slice(1)}
                              </button>
                            )
                          })}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {aiStatus && (
            <div className="surface-card" style={{ padding: 24 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  marginBottom: 14,
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <h2 style={{ fontSize: 17, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <SparklesIcon />
                    AI Engine (LLMProviderComponent)
                  </h2>
                  <p className="release-note" style={{ marginTop: 2 }}>
                    Configure on-premise Ollama, cloud Google Gemini, or zero-config Local TF-IDF (automatic fallback).
                  </p>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span className="ai-provider-pill">
                    <span
                      className={`status-dot ${aiStatus.ollama_reachable ? 'status-dot-green' : 'status-dot-muted'}`}
                    />
                    Ollama {aiStatus.ollama_reachable ? 'Online' : 'Offline'}
                  </span>
                  <span className="ai-provider-pill">
                    <span
                      className={`status-dot ${aiStatus.gemini_configured ? 'status-dot-green' : 'status-dot-muted'}`}
                    />
                    Gemini {aiStatus.gemini_configured ? 'Key set' : 'No key'}
                  </span>
                </div>
              </div>

              {aiMessage && <div className="alert alert-success">{aiMessage}</div>}

              <form onSubmit={handleSaveAiSettings}>
                <div className="form-field">
                  <span className="form-label">Active provider</span>
                  <div className="segmented" style={{ alignSelf: 'flex-start' }}>
                    {(['local', 'ollama', 'gemini'] as AIProviderName[]).map((prov) => (
                      <button
                        key={prov}
                        type="button"
                        className={`segmented-btn${selectedProvider === prov ? ' active' : ''}`}
                        onClick={() => setSelectedProvider(prov)}
                      >
                        {prov === 'local'
                          ? 'Local TF-IDF'
                          : prov === 'ollama'
                            ? 'Ollama (On-Premise)'
                            : 'Google Gemini (Cloud)'}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="form-grid-2">
                  <div className="form-field">
                    <label className="form-label" htmlFor="ai-ollama-url">
                      Ollama Base URL
                    </label>
                    <input
                      id="ai-ollama-url"
                      className="input mono"
                      value={ollamaUrl}
                      onChange={(e) => setOllamaUrl(e.target.value)}
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-label" htmlFor="ai-ollama-model">
                      Ollama Model
                    </label>
                    <input
                      id="ai-ollama-model"
                      className="input mono"
                      value={ollamaModel}
                      onChange={(e) => setOllamaModel(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-grid-2">
                  <div className="form-field">
                    <label className="form-label" htmlFor="ai-gemini-model">
                      Gemini Model
                    </label>
                    <input
                      id="ai-gemini-model"
                      className="input mono"
                      value={geminiModel}
                      onChange={(e) => setGeminiModel(e.target.value)}
                    />
                  </div>
                  <div className="form-field">
                    <label className="form-label" htmlFor="ai-gemini-key">
                      Gemini API Key {aiStatus.gemini_configured ? '(configured — leave blank to keep)' : '(optional)'}
                    </label>
                    <input
                      id="ai-gemini-key"
                      type="password"
                      className="input mono"
                      placeholder="AIza..."
                      value={geminiApiKey}
                      onChange={(e) => setGeminiApiKey(e.target.value)}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="submit" className="btn btn-ai" disabled={savingAi}>
                    <SparklesIcon />
                    {savingAi ? 'Saving...' : 'Save AI settings'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
