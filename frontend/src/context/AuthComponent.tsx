import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getStoredToken, setStoredToken } from '../api/ApiComponent'
import { AuthContext } from './authContext'
import type { Role, UserPublic } from '../types/cmt'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [loading, setLoading] = useState<boolean>(() => Boolean(getStoredToken()))

  useEffect(() => {
    const token = getStoredToken()
    if (!token) {
      return
    }
    let active = true
    api.auth
      .me()
      .then((me) => {
        if (active) {
          setUser(me)
        }
      })
      .catch(() => {
        setStoredToken(null)
        if (active) {
          setUser(null)
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

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.auth.login(email, password)
    setStoredToken(res.access_token)
    setUser(res.user)
  }, [])

  const register = useCallback(
    async (payload: {
      first_name: string
      last_name: string
      email: string
      password: string
      affiliation?: string
      expertise?: string
    }) => {
      const res = await api.auth.register(payload)
      setStoredToken(res.access_token)
      setUser(res.user)
    },
    [],
  )

  const logout = useCallback(async () => {
    try {
      await api.auth.logout()
    } catch {
      // ignore if token already expired
    } finally {
      setStoredToken(null)
      setUser(null)
    }
  }, [])

  const refreshUser = useCallback(async () => {
    const me = await api.auth.me()
    setUser(me)
  }, [])

  const hasRole = useCallback(
    (role: Role) => Boolean(user?.roles.includes(role)),
    [user],
  )

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refreshUser,
        setUser,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
