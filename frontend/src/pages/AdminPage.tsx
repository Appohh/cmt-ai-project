import { useEffect, useState } from 'react'
import { ApiError, api } from '../api/ApiComponent'
import type { AdminOverviewResponse } from '../types/cmt'

export function AdminPage() {
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api.users
      .getAdminOverview()
      .then((data) => {
        if (active) {
          setOverview(data)
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

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Admin</h1>
          <p className="page-subtitle">
            System oversight across users, conferences, submissions, and reviews.
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

          <div className="surface-card table-card">
            <table className="cmt-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Affiliation</th>
                  <th>Roles</th>
                </tr>
              </thead>
              <tbody>
                {overview.users.map((u) => (
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
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {u.roles.map((role) => (
                          <span key={role} className="badge badge-neutral">
                            {role.charAt(0).toUpperCase() + role.slice(1)}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}
