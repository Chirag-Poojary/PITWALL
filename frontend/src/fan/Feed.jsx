import { Link } from 'react-router-dom'
import { ErrorBox, fmt, Loader, localTime, useApi, useCountdown } from '../components/common'
import { teamColor } from '../teams'
import { PageHead } from './Drivers'

const KIND_LABEL = { practice: 'Practice', qualifying: 'Qualifying', sprint: 'Sprint', race: 'Race' }

function Countdown({ iso }) {
  const c = useCountdown(iso)
  if (!c) return null
  if (c.past) return <div className="countdown live-now"><b>LIVE</b><span>weekend in progress</span></div>
  return (
    <div className="countdown">
      {[['d', 'days'], ['h', 'hrs'], ['m', 'min'], ['s', 'sec']].map(([k, l]) => (
        <div key={k}><b>{String(c[k]).padStart(2, '0')}</b><span>{l}</span></div>
      ))}
    </div>
  )
}

export default function Feed() {
  const { data, loading, error } = useApi('/me/feed')
  if (loading) return <div className="wrap section"><Loader label="Building your feed" /></div>
  if (error) return <div className="wrap section"><ErrorBox error={error} /></div>
  const p = data.preferences
  const empty = !p.fav_drivers.length && !p.fav_constructors.length
  const nr = data.next_race
  const favDriverRefs = new Set(p.fav_drivers)
  const favTeamRefs = new Set(p.fav_constructors)
  const firstSession = nr?.sessions?.find((s) => new Date(s.start) > new Date()) || nr?.sessions?.[0]

  return (
    <div>
      <PageHead eyebrow={`${data.season} season · ${data.source === 'live' ? 'live calendar' : 'dataset calendar'}`} title="My Feed">
        <p className="page-sub">Your sessions, your drivers, your teams. <Link to="/profile">Edit preferences →</Link></p>
      </PageHead>
      <div className="wrap section-tight">
        {data.source !== 'live' && (
          <div className="notice">The live F1 calendar (Jolpica-F1 API) could not be reached, so this feed is showing the {data.season} season from the dataset. Check your internet connection and refresh.</div>
        )}
        {empty && (
          <div className="cta-band slim">
            <div><h3>Make this feed yours</h3><p>Pick favourite drivers and teams, and choose which sessions you want to see.</p></div>
            <Link to="/profile" className="btn btn-red">Choose favourites</Link>
          </div>
        )}

        <div className="feed-grid">
          <div className="feed-main">
            {nr ? (
              <section className="next-race">
                <div className="nr-head">
                  <p className="eyebrow">Next up · Round {nr.round}</p>
                  <h2>{nr.race_name}</h2>
                  <p className="muted">{nr.circuit_name} · {nr.locality}, {nr.country}{nr.sprint_weekend && <span className="pill red">Sprint weekend</span>}</p>
                </div>
                <Countdown iso={firstSession?.start} />
                <p className="muted small">Countdown to {firstSession?.name} · {localTime(firstSession?.start)} (your time)</p>
                <div className="nr-sessions">
                  {nr.sessions.map((s) => (
                    <div key={s.name} className={`nr-session ${p.followed_sessions.includes(s.kind) ? 'followed' : ''}`}>
                      <span>{s.name}</span><b>{localTime(s.start)}</b>
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              <section className="next-race"><h2>No upcoming races</h2><p className="muted">The season is over, or none of the Grands Prix you follow are still to come.</p></section>
            )}

            <section className="panel">
              <h3 className="h3">Upcoming sessions you follow</h3>
              {data.upcoming_sessions.length === 0 && <p className="muted">Nothing scheduled for the sessions you follow.</p>}
              <ul className="session-list">
                {data.upcoming_sessions.map((s) => (
                  <li key={`${s.round}-${s.name}`} className={s.live ? 'live' : ''}>
                    <span className={`kind kind-${s.kind}`}>{KIND_LABEL[s.kind]}</span>
                    <div><b>{s.race_name}</b><small>{s.name} · {s.locality}, {s.country}</small></div>
                    <time>{s.live ? <span className="pill red">LIVE</span> : localTime(s.start)}</time>
                  </li>
                ))}
              </ul>
            </section>

            {data.last_race?.results?.length > 0 && (
              <section className="panel">
                <h3 className="h3">Latest result · {data.last_race.race_name}</h3>
                <div className="table-wrap">
                  <table className="tbl">
                    <thead><tr><th>Pos</th><th>Driver</th><th>Team</th><th>Grid</th><th>Pts</th></tr></thead>
                    <tbody>{data.last_race.results.slice(0, 10).map((r) => (
                      <tr key={r.driver_ref} className={favDriverRefs.has(r.driver_ref) || favTeamRefs.has(r.team_ref) ? 'fav-row' : ''}>
                        <td>{r.position}</td><td>{r.name}</td><td>{r.team}</td><td>{r.grid}</td><td>{fmt.pts(r.points)}</td></tr>))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>

          <aside className="feed-side">
            {data.fav_drivers.length > 0 && (
              <section>
                <h3 className="h3">Your drivers</h3>
                {data.fav_drivers.map((f) => (
                  <div key={f.ref} className="fav-card" style={{ '--team': teamColor(f.current?.team) }}>
                    <div className="fav-top">
                      <b>{f.current?.name || f.career?.name || f.ref}</b>
                      {f.current && <span className="pill">P{f.current.position} · {fmt.pts(f.current.points)} pts</span>}
                    </div>
                    <small className="muted">{f.current?.team}{f.current ? ` · ${f.current.wins} wins this season` : ''}</small>
                    {f.career && (
                      <div className="fav-stats"><span><b>{f.career.titles}</b>titles</span><span><b>{f.career.wins}</b>wins</span><span><b>{f.career.podiums}</b>podiums</span><span><b>{f.career.starts}</b>starts</span></div>
                    )}
                    {f.career && <Link to={`/drivers/${f.career.driverId}`} className="small">Career profile →</Link>}
                    {!f.career && <small className="muted">New driver: no history in the 1950–2024 dataset yet.</small>}
                  </div>
                ))}
              </section>
            )}
            {data.fav_constructors.length > 0 && (
              <section>
                <h3 className="h3">Your teams</h3>
                {data.fav_constructors.map((f) => (
                  <div key={f.ref} className="fav-card" style={{ '--team': teamColor(f.current?.name || f.career?.name) }}>
                    <div className="fav-top">
                      <b>{f.current?.name || f.career?.name || f.ref}</b>
                      {f.current && <span className="pill">P{f.current.position} · {fmt.pts(f.current.points)} pts</span>}
                    </div>
                    {f.career && <div className="fav-stats"><span><b>{f.career.titles}</b>titles</span><span><b>{f.career.wins}</b>wins</span><span><b>{f.career.races}</b>races</span></div>}
                    {f.career && <Link to={`/constructors/${f.career.constructorId}`} className="small">Team profile →</Link>}
                  </div>
                ))}
              </section>
            )}
            <section className="panel">
              <h3 className="h3">Drivers’ standings{data.standings_source !== 'live' ? ` (${data.season})` : ''}</h3>
              <ol className="mini-standings">
                {data.driver_standings.map((r) => (
                  <li key={r.driver_ref || r.name} className={favDriverRefs.has(r.driver_ref) ? 'fav' : ''}>
                    <span>{r.position}</span><b>{r.name}</b><i style={{ background: teamColor(r.team) }} /><em>{fmt.pts(r.points)}</em></li>
                ))}
              </ol>
            </section>
            <section className="panel">
              <h3 className="h3">Constructors’ standings</h3>
              <ol className="mini-standings">
                {data.constructor_standings.map((r) => (
                  <li key={r.team_ref || r.name} className={favTeamRefs.has(r.team_ref) ? 'fav' : ''}>
                    <span>{r.position}</span><b>{r.name}</b><i style={{ background: teamColor(r.name) }} /><em>{fmt.pts(r.points)}</em></li>
                ))}
              </ol>
            </section>
          </aside>
        </div>
      </div>
    </div>
  )
}
