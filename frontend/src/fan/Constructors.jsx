import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Flag, fmt, useApi } from '../components/common'
import { teamColor } from '../teams'
import { PageHead, StandingsTable, Tabs } from './Drivers'

const SORTS = [['points', 'Points'], ['wins', 'Wins'], ['titles', 'Titles'], ['podiums', 'Podiums'], ['races', 'Races'], ['last_season', 'Most recent']]

export default function Constructors() {
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') || 'all'
  const meta = useApi('/meta')
  const [season, setSeason] = useState(null)
  const [f, setF] = useState({ q: '', nationality: '', decade: '', champions: false, sort: 'points', active: '' })
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => { if (meta.data && !season) setSeason(meta.data.latest_season) }, [meta.data, season])
  useEffect(() => {
    if (tab !== 'all') return
    const t = setTimeout(() => {
      setLoading(true)
      api('/constructors', { params: { q: f.q, nationality: f.nationality, decade: f.decade, champions: f.champions, sort: f.sort, season: f.active, limit: 300 } })
        .then((d) => { setData(d); setErr(null) }).catch(setErr).finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(t)
  }, [f, tab])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  // Constructor standings only exist from 1958 onward
  const seasons = meta.data?.seasons.filter((y) => y >= 1958).reverse() || []

  return (
    <div>
      <PageHead eyebrow="Teams & manufacturers" title="Constructors">
        <p className="page-sub">From works giants to one-season privateers: every team that has entered a Grand Prix, and the Constructors’ Championship since 1958.</p>
        <Tabs value={tab} onChange={(t) => setSp({ tab: t })} items={[['all', 'All constructors'], ['standings', 'Championship standings']]} />
      </PageHead>
      <div className="wrap section-tight">
        {tab === 'standings' ? (
          <>
            <div className="filters">
              <label>Season
                <select value={season || ''} onChange={(e) => setSeason(+e.target.value)}>
                  {seasons.map((y) => <option key={y}>{y}</option>)}
                </select>
              </label>
              <p className="muted small">Final Constructors’ Championship standings for {season}.</p>
            </div>
            {season && <StandingsTable kind="constructors" season={season} />}
          </>
        ) : (
          <>
            <div className="filters">
              <input className="search" placeholder="Search a team" value={f.q} onChange={set('q')} />
              <select value={f.nationality} onChange={set('nationality')}>
                <option value="">All nationalities</option>
                {meta.data?.constructor_nationalities.map((n) => <option key={n}>{n}</option>)}
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
              <label className="check"><input type="checkbox" checked={f.champions} onChange={set('champions')} /> Champions only</label>
            </div>
            <ErrorBox error={err} />
            <p className="muted small count">{loading ? 'Loading…' : `${fmt.int(data.total)} constructors`}</p>
            <div className="card-grid">
              {data.items.map((c) => (
                <Link key={c.constructorId} to={`/constructors/${c.constructorId}`} className="person-card team-card" style={{ '--team': teamColor(c.name) }}>
                  <div className="team-swatch" />
                  <h3><Flag nationality={c.nationality} /> {c.name}</h3>
                  <p className="pc-sub">{c.nationality} · {c.first_season === c.last_season ? c.first_season : `${c.first_season}–${c.last_season}`}</p>
                  <div className="pc-stats">
                    <span><b>{c.titles}</b>Titles</span>
                    <span><b>{c.wins}</b>Wins</span>
                    <span><b>{c.races}</b>Races</span>
                    <span><b>{fmt.pts(c.points)}</b>Points</span>
                  </div>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
