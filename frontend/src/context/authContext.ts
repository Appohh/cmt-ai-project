import { createContext, useContext } from 'react'
import type { Role, UserPublic } from '../types/cmt'

export interface AuthContextValue {
  user: UserPublic | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (payload: {
    first_name: string
    last_name: string
    email: string
    password: string
    affiliation?: string
    expertise?: string
  }) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  setUser: (user: UserPublic | null) => void
  hasRole: (role: Role) => boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return ctx
}
