import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!getToken())

  useEffect(() => {
    if (!getToken()) return
    api('/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const out = () => setUser(null)
    window.addEventListener('pitwall:logout', out)
    return () => window.removeEventListener('pitwall:logout', out)
  }, [])

  const signIn = useCallback((session) => {
    setToken(session.token)
    setUser(session.user)
    return session.user
  }, [])

  const signOut = useCallback(() => { setToken(null); setUser(null) }, [])

  return <AuthCtx.Provider value={{ user, loading, signIn, signOut, setUser }}>{children}</AuthCtx.Provider>
}

export const useAuth = () => useContext(AuthCtx)
