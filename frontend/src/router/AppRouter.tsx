import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../context/authContext'
import { AuthPage } from '../pages/AuthPage'
import { DashboardPage } from '../pages/DashboardPage'
import type { AppPage } from '../types/cmt'

const VALID_PAGES: AppPage[] = ['papers', 'reviews', 'chair', 'admin', 'profile']

function readPageFromHash(): AppPage | null {
  const raw = window.location.hash.replace(/^#\/?/, '') as AppPage
  return VALID_PAGES.includes(raw) ? raw : null
}

function readInviteFromQuery(): string | null {
  const params = new URLSearchParams(window.location.search)
  return params.get('invite')
}

export function AppRouter() {
  const { user, loading, hasRole } = useAuth()
  const [inviteToken, setInviteToken] = useState<string | null>(() => readInviteFromQuery())
  const [requestedPage, setRequestedPage] = useState<AppPage>(
    () => (readInviteFromQuery() ? 'reviews' : readPageFromHash() ?? 'papers'),
  )

  useEffect(() => {
    const onHashChange = () => {
      const next = readPageFromHash()
      if (next) {
        setRequestedPage(next)
      }
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const canAccessPage = useCallback(
    (page: AppPage): boolean => {
      if (!user) return false
      if (page === 'papers') return hasRole('author')
      if (page === 'reviews') return hasRole('reviewer') || Boolean(inviteToken)
      if (page === 'chair') return hasRole('organizer')
      if (page === 'admin') return hasRole('admin')
      if (page === 'profile') return true
      return false
    },
    [user, hasRole, inviteToken],
  )

  const handleNavigate = useCallback((page: AppPage) => {
    setRequestedPage(page)
    window.location.hash = `#/${page}`
  }, [])

  const handleInviteConsumed = useCallback(() => {
    setInviteToken(null)
    if (window.location.search.includes('invite=')) {
      window.history.replaceState({}, '', `${window.location.pathname}${window.location.hash}`)
    }
  }, [])

  if (loading) {
    return (
      <div className="auth-viewport">
        <div className="surface-card auth-card" style={{ textAlign: 'center' }}>
          <p className="release-note">Restoring session...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <AuthPage />
  }

  const effectivePage: AppPage = canAccessPage(requestedPage)
    ? requestedPage
    : hasRole('author')
      ? 'papers'
      : hasRole('organizer')
        ? 'chair'
        : hasRole('reviewer')
          ? 'reviews'
          : hasRole('admin')
            ? 'admin'
            : 'profile'

  return (
    <DashboardPage
      activePage={effectivePage}
      onNavigate={handleNavigate}
      pendingInviteToken={inviteToken}
      onInviteConsumed={handleInviteConsumed}
    />
  )
}
