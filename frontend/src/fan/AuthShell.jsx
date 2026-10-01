import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { MEDIA } from '../media'

export function Brand({ small }) {
  return (
    <span className={`brand ${small ? 'brand-sm' : ''}`}>
      <svg viewBox="0 0 64 40" className="brand-mark" aria-hidden>
        <path d="M2 38 L24 6 H62 L54 16 H30 L14 38Z" fill="#e10600" />
        <path d="M20 38 L30 24 H50 L42 38Z" fill="currentColor" />
      </svg>
      <span className="brand-word">PIT<b>WALL</b></span>
    </span>
  )
}

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="fan-root auth-page">
      <aside className="auth-visual" style={{ backgroundImage: `url("${MEDIA.images.auth}")` }}>
        <div className="auth-visual-shade" />
        <div className="auth-visual-inner">
          <Brand />
          <h1 className="auth-tag">Lights out<br />and away we go.</h1>
          <p className="auth-copy">75 seasons of Formula 1, every driver and team, and a feed tuned to the races you follow.</p>
          <ul className="auth-facts">
            <li><b>861</b><span>drivers</span></li>
            <li><b>211</b><span>constructors</span></li>
            <li><b>1,125</b><span>Grands Prix</span></li>
          </ul>
        </div>
        <div className="kerb" />
      </aside>
      <main className="auth-panel">
        <div className="auth-card">
          <div className="auth-mobile-brand"><Brand small /></div>
          <h2>{title}</h2>
          <p className="muted">{subtitle}</p>
          {children}
        </div>
      </main>
    </div>
  )
}

export function GoogleButton({ onError }) {
  const [clientId, setClientId] = useState(undefined)
  const ref = useRef(null)
  const { signIn } = useAuth()
  const nav = useNavigate()

  useEffect(() => { api('/auth/config').then((c) => setClientId(c.google_client_id)).catch(() => setClientId(null)) }, [])

  useEffect(() => {
    if (!clientId || !ref.current) return
    const init = () => {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (resp) => {
          try {
            const s = await api('/auth/google', { method: 'POST', body: { credential: resp.credential } })
            signIn(s)
            nav('/about')
          } catch (e) { onError?.(e.message) }
        },
      })
      window.google.accounts.id.renderButton(ref.current, {
        theme: 'filled_black', size: 'large', shape: 'rectangular', text: 'continue_with', width: ref.current.offsetWidth || 360,
      })
    }
    if (window.google?.accounts?.id) { init(); return }
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.async = true
    s.onload = init
    s.onerror = () => onError?.('Could not load Google sign-in')
    document.head.appendChild(s)
  }, [clientId, nav, onError, signIn])

  if (clientId) return <div className="google-slot" ref={ref} />
  return (
    <button type="button" className="btn btn-google" disabled={clientId === undefined}
      onClick={() => onError?.('Google sign-in is not set up on this server yet. Add GOOGLE_CLIENT_ID to the .env file (see README), then restart.')}>
      <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
      Continue with Google
    </button>
  )
}
