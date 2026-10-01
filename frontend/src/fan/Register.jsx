import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import AuthShell, { GoogleButton } from './AuthShell'

export default function Register() {
  const { user, signIn } = useAuth()
  const nav = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/about" replace />

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    if (form.password !== form.confirm) { setErr('Passwords do not match'); return }
    setBusy(true)
    try {
      signIn(await api('/auth/register', { method: 'POST', body: { name: form.name, email: form.email, password: form.password } }))
      nav('/about', { replace: true })
    } catch (e2) { setErr(e2.message) } finally { setBusy(false) }
  }
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <AuthShell title="Create your account" subtitle="Join the grid. It takes less than a minute.">
      <GoogleButton onError={setErr} />
      <div className="divider"><span>or sign up with email</span></div>
      <form onSubmit={submit} className="form">
        <label>Full name<input required autoComplete="name" value={form.name} onChange={set('name')} placeholder="Ayrton Senna" /></label>
        <label>Email<input type="email" required autoComplete="email" value={form.email} onChange={set('email')} placeholder="you@example.com" /></label>
        <div className="form-row">
          <label>Password<input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set('password')} placeholder="8+ characters" /></label>
          <label>Confirm<input type="password" required autoComplete="new-password" value={form.confirm} onChange={set('confirm')} placeholder="Repeat" /></label>
        </div>
        {err && <div className="form-error">{err}</div>}
        <button className="btn btn-red btn-block" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
      </form>
      <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
    </AuthShell>
  )
}
