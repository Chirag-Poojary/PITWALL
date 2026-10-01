import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

export default function AdminLogin() {
  const { user, signIn } = useAuth()
  const nav = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (user?.role === 'admin') return <Navigate to="/admin" replace />

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      signIn(await api('/auth/admin/login', { method: 'POST', body: form }))
      nav('/admin', { replace: true })
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }

  return (
    <div className="admin-root a-login">
      <form className="a-login-card" onSubmit={submit}>
        <div className="a-logo"><span className="a-logo-mark" />PITWALL <em>Analyst</em></div>
        <h1>Sign in to the analyst workspace</h1>
        <p className="a-muted">Restricted to admin accounts.</p>
        <label className="a-field"><span>Email</span><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="username" /></label>
        <label className="a-field"><span>Password</span><input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="current-password" /></label>
        {err && <div className="a-error">{err}</div>}
        <button className="a-btn primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="a-muted small">Fan account? <Link to="/login">Go to the fan site</Link></p>
      </form>
    </div>
  )
}
