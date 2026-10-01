import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Flag, fmt, Loader, useApi } from '../components/common'
import { teamColor } from '../teams'

const SORTS = [['points', 'Points'], ['wins', 'Wins'], ['podiums', 'Podiums'], ['titles', 'Titles'], ['poles', 'Poles'], ['starts', 'Starts'], ['last_season', 'Most recent']]

export function PageHead({ eyebrow, title, children }) {
  return (
    <section className="page-head">
      <div className="wrap">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        {children}
      </div>
    </section>
  )
}

export function Tabs({ value, onChange, items }) {
  return (
    <div className="tabs">
      {items.map(([k, l]) => <button key={k} className={value === k ? 'active' : ''} onClick={() => onChange(k)}>{l}</button>)}
    </div>
  )
}

export function StandingsTable({ kind, season }) {
  const s = useApi(`/standings/${kind}`, { season })
  if (s.loading) return <Loader />
  if (s.error) return <ErrorBox error={s.error} />
  if (!s.data.length) return <p className="muted">No championship standings recorded for {season}.</p>
  const max = s.data[0].points || 1
  return (
    <div className="standings">
      {s.data.map((r) => {
        const team = kind === 'drivers' ? r.constructor_name : r.name
        const link = kind === 'drivers' ? `/drivers/${r.driverId}` : `/constructors/${r.constructorId}`
        return (
          <Link key={link} to={link} className={`standing-row ${r.position === 1 ? 'leader' : ''}`} style={{ '--team': teamColor(team) }}>
            <span className="pos">{r.position}</span>
            <span className="who">
              <b><Flag nationality={r.nationality} /> {r.name}</b>
              {kind === 'drivers' && <small>{r.constructor_name}</small>}
            </span>
            <span className="bar"><i style={{ width: `${(r.points / max) * 100}%` }} /></span>
            <span className="num">{r.wins}<small>wins</small></span>
            <span className="num">{r.podiums ?? 0}<small>podiums</small></span>
            <span className="pts">{fmt.pts(r.points)}<small>PTS</small></span>
          </Link>
        )
      })}
    </div>
  )
}

export default function Drivers() {
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') || 'all'
  const meta = useApi('/meta')
  const [season, setSeason] = useState(null)
  const [f, setF] = useState({ q: '', nationality: '', decade: '', champions: false, sort: 'points', active: '' })
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => { if (meta.data && !season) setSeason(meta.data.latest_season) }, [meta.data, season])

  useEffect(() => {
    if (tab !== 'all') return
    const t = setTimeout(() => {
      setLoading(true)
      api('/drivers', { params: { q: f.q, nationality: f.nationality, decade: f.decade, champions: f.champions, sort: f.sort, season: f.active, limit: 48 } })
        .then((d) => { setItems(d.items); setTotal(d.total); setErr(null) }).catch(setErr).finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(t)
  }, [f, tab])

  const more = () => api('/drivers', { params: { q: f.q, nationality: f.nationality, decade: f.decade, champions: f.champions, sort: f.sort, season: f.active, limit: 48, offset: items.length } })
    .then((d) => setItems([...items, ...d.items]))
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  return (
    <div>
      <PageHead eyebrow="The grid, 1950 → today" title="Drivers">
        <p className="page-sub">Every driver who has started a World Championship Grand Prix, with career numbers and season standings.</p>
        <Tabs value={tab} onChange={(t) => setSp({ tab: t })} items={[['all', 'All drivers'], ['standings', 'Championship standings']]} />
      </PageHead>
      <div className="wrap section-tight">
        {tab === 'standings' ? (
          <>
            <div className="filters">
              <label>Season
                <select value={season || ''} onChange={(e) => setSeason(+e.target.value)}>
                  {meta.data?.seasons.slice().reverse().map((y) => <option key={y}>{y}</option>)}
                </select>
              </label>
              <p className="muted small">Final Drivers’ Championship standings after the last race of {season}.</p>
            </div>
            {season && <StandingsTable kind="drivers" season={season} />}
          </>
        ) : (
          <>
            <div className="filters">
              <input className="search" placeholder="Search a driver (name or code: HAM, VER…)" value={f.q} onChange={set('q')} />
              <select value={f.nationality} onChange={set('nationality')}>
                <option value="">All nationalities</option>
                {meta.data?.driver_nationalities.map((n) => <option key={n}>{n}</option>)}
              </select>
              <select value={f.decade} onChange={set('decade')}>
                <option value="">All eras</option>
                {meta.data?.decades.map((d) => <option key={d} value={d}>{d}s</option>)}
              </select>
              <select value={f.active} onChange={set('active')}>
                <option value="">Any season</option>
                {meta.data?.seasons.slice().reverse().map((y) => <option key={y} value={y}>Raced in {y}</option>)}
              </select>
              <select value={f.sort} onChange={set('sort')}>
                {SORTS.map(([k, l]) => <option key={k} value={k}>Sort: {l}</option>)}
              </select>
              <label className="check"><input type="checkbox" checked={f.champions} onChange={set('champions')} /> World champions</label>
            </div>
            <ErrorBox error={err} />
            <p className="muted small count">{loading ? 'Loading…' : `${fmt.int(total)} drivers`}</p>
            <div className="card-grid">
              {items.map((d) => (
                <Link key={d.driverId} to={`/drivers/${d.driverId}`} className="person-card" style={{ '--team': teamColor(d.last_team) }}>
                  <div className="pc-top">
                    <span className="pc-code">{d.code || d.name.split(' ').pop().slice(0, 3).toUpperCase()}</span>
                    {d.number && <span className="pc-num">{d.number}</span>}
                  </div>
                  <h3><Flag nationality={d.nationality} /> {d.name}</h3>
                  <p className="pc-sub">{d.last_team} · {d.first_season === d.last_season ? d.first_season : `${d.first_season}–${d.last_season}`}</p>
                  <div className="pc-stats">
                    <span><b>{d.titles}</b>Titles</span>
                    <span><b>{d.wins}</b>Wins</span>
                    <span><b>{d.podiums}</b>Podiums</span>
                    <span><b>{fmt.pts(d.points)}</b>Points</span>
                  </div>
                </Link>
              ))}
            </div>
            {items.length < total && !loading && <div className="center"><button className="btn btn-ghost" onClick={more}>Load more</button></div>}
          </>
        )}
      </div>
    </div>
  )
}
