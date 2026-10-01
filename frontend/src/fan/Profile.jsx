import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Loader, useApi } from '../components/common'
import { teamColor } from '../teams'
import { PageHead } from './Drivers'

const SESSIONS = [['practice', 'Practice'], ['qualifying', 'Qualifying'], ['sprint', 'Sprint'], ['race', 'Grand Prix']]

function Picker({ title, hint, options, value, onChange, max = 5, searchHistory }) {
  const [q, setQ] = useState('')
  const [extra, setExtra] = useState([])
  useEffect(() => {
    if (!searchHistory || q.length < 3) { setExtra([]); return }
    const t = setTimeout(() => searchHistory(q).then(setExtra).catch(() => setExtra([])), 250)
    return () => clearTimeout(t)
  }, [q, searchHistory])
  const all = useMemo(() => {
    const m = new Map(options.map((o) => [o.ref, o]))
    extra.forEach((o) => { if (!m.has(o.ref)) m.set(o.ref, o) })
    return [...m.values()]
  }, [options, extra])
  const shown = all.filter((o) => !q || `${o.name} ${o.code || ''} ${o.team || ''}`.toLowerCase().includes(q.toLowerCase()))
  const toggle = (ref) => onChange(value.includes(ref) ? value.filter((r) => r !== ref) : value.length >= max ? value : [...value, ref])
  const byRef = new Map(all.map((o) => [o.ref, o]))
  return (
    <section className="panel pref">
      <div className="pref-head"><h3 className="h3">{title}</h3><span className="muted small">{value.length}/{max} selected</span></div>
      <p className="muted small">{hint}</p>
      {value.length > 0 && (
        <div className="chips selected">
          {value.map((r) => <button key={r} className="chip on" onClick={() => toggle(r)} style={{ '--team': teamColor(byRef.get(r)?.team || byRef.get(r)?.name) }}>{byRef.get(r)?.name || r} ✕</button>)}
        </div>
      )}
      <input className="search" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips">
        {shown.slice(0, 40).map((o) => (
          <button key={o.ref} className={`chip ${value.includes(o.ref) ? 'on' : ''}`} onClick={() => toggle(o.ref)} style={{ '--team': teamColor(o.team || o.name) }}>
            {o.name}{o.team && <small>{o.team}</small>}{o.current && <i className="dot" title="On the current grid" />}
          </button>
        ))}
      </div>
    </section>
  )
}

export default function Profile() {
  const { setUser } = useAuth()
  const nav = useNavigate()
  const prof = useApi('/me/profile')
  const cat = useApi('/catalog')
  const [prefs, setPrefs] = useState(null)
  const [name, setName] = useState('')
  const [saved, setSaved] = useState('')
  const [err, setErr] = useState(null)

  useEffect(() => { if (prof.data) { setPrefs(prof.data.preferences); setName(prof.data.user.name) } }, [prof.data])

  const searchDrivers = useMemo(() => (q) => api('/drivers', { params: { q, limit: 15, sort: 'last_season' } })
    .then((d) => d.items.map((x) => ({ ref: x.driverRef, name: x.name, code: x.code, team: x.last_team }))), [])
  const searchTeams = useMemo(() => (q) => api('/constructors', { params: { q, limit: 15, sort: 'last_season' } })
    .then((d) => d.items.map((x) => ({ ref: x.constructorRef, name: x.name }))), [])

  if (prof.loading || cat.loading || !prefs) return <div className="wrap section"><Loader /></div>
  if (prof.error || cat.error) return <div className="wrap section"><ErrorBox error={prof.error || cat.error} /></div>
  const u = prof.data.user
  const toggleSession = (k) => setPrefs({ ...prefs, followed_sessions: prefs.followed_sessions.includes(k) ? prefs.followed_sessions.filter((x) => x !== k) : [...prefs.followed_sessions, k] })
  const toggleEvent = (k) => setPrefs({ ...prefs, followed_events: prefs.followed_events.includes(k) ? prefs.followed_events.filter((x) => x !== k) : [...prefs.followed_events, k] })

  const save = async () => {
    setErr(null); setSaved('')
    try {
      if (name !== u.name) { const r = await api('/me/profile', { method: 'PUT', body: { name } }); setUser(r.user) }
      await api('/me/preferences', { method: 'PUT', body: { ...prefs, onboarded: true } })
      setSaved('Saved. Your feed is updated.')
    } catch (e) { setErr(e) }
  }

  return (
    <div>
      <PageHead eyebrow="Account" title="Profile & preferences">
        <p className="page-sub">Tell us who you support and what you watch. We use it to build <b>My Feed</b>.</p>
      </PageHead>
      <div className="wrap section-tight profile-grid">
        <section className="panel account">
          <div className="account-avatar">{u.avatar ? <img src={u.avatar} alt="" referrerPolicy="no-referrer" /> : u.name.slice(0, 1)}</div>
          <label>Display name<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Email<input value={u.email} disabled /></label>
          <p className="muted small">Signed in with {u.provider === 'google' ? 'Google' : 'email & password'} · member since {new Date(u.created_at).toLocaleDateString()}</p>
        </section>

        <div className="pref-stack">
          <Picker title="Favourite drivers" hint={`Current grid first (${cat.data.source === 'live' ? 'live' : 'from the dataset'}). Type 3+ letters to find any driver in history.`}
            options={cat.data.drivers} value={prefs.fav_drivers} onChange={(v) => setPrefs({ ...prefs, fav_drivers: v })} searchHistory={searchDrivers} />
          <Picker title="Favourite constructors" hint="Pick the teams you support." options={cat.data.constructors}
            value={prefs.fav_constructors} onChange={(v) => setPrefs({ ...prefs, fav_constructors: v })} max={4} searchHistory={searchTeams} />

          <section className="panel pref">
            <h3 className="h3">Sessions I follow</h3>
            <p className="muted small">Only these sessions appear in your upcoming list.</p>
            <div className="chips">
              {SESSIONS.map(([k, l]) => <button key={k} className={`chip ${prefs.followed_sessions.includes(k) ? 'on' : ''}`} onClick={() => toggleSession(k)}>{l}</button>)}
            </div>
          </section>

          <section className="panel pref">
            <div className="pref-head"><h3 className="h3">Grands Prix I follow</h3>
              <button className="link-btn" onClick={() => setPrefs({ ...prefs, followed_events: [] })}>Follow all</button></div>
            <p className="muted small">{prefs.followed_events.length ? `${prefs.followed_events.length} selected` : 'Following every Grand Prix. Pick some to narrow your feed.'}</p>
            <div className="chips">
              {cat.data.events.map((e) => <button key={e.ref} className={`chip ${prefs.followed_events.includes(e.ref) ? 'on' : ''}`} onClick={() => toggleEvent(e.ref)}>{e.name.replace(' Grand Prix', ' GP')}</button>)}
            </div>
          </section>

          <div className="save-bar">
            <ErrorBox error={err} />
            {saved && <span className="ok">{saved}</span>}
            <button className="btn btn-ghost" onClick={() => nav('/feed')}>View my feed</button>
            <button className="btn btn-red" onClick={save}>Save preferences</button>
          </div>
        </div>
      </div>
    </div>
  )
}
