import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import AuthShell, { GoogleButton } from './AuthShell'

export default function Login() {
  const { user, signIn } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [form, setForm] = useState({ email: '', password: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to={user.role === 'admin' ? '/admin' : '/about'} replace />

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      signIn(await api('/auth/login', { method: 'POST', body: form }))
      nav(loc.state?.from || '/about', { replace: true })
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your PITWALL account.">
      <GoogleButton onError={setErr} />
      <div className="divider"><span>or with email</span></div>
      <form onSubmit={submit} className="form">
        <label>Email<input type="email" required autoComplete="email" value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@example.com" /></label>
        <label>Password<input type="password" required autoComplete="current-password" value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="••••••••" /></label>
        {err && <div className="form-error">{err}</div>}
        <button className="btn btn-red btn-block" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
      <p className="auth-switch">New to PITWALL? <Link to="/register">Create an account</Link></p>
    </AuthShell>
  )
}
