import { Link, useParams } from 'react-router-dom'
import { ErrorBox, Flag, fmt, Loader, useApi } from '../components/common'
import Plot from '../components/Plot'
import { teamColor } from '../teams'

function listJoin(a) {
  if (a.length <= 1) return a.join('')
  return `${a.slice(0, -1).join(', ')} and ${a[a.length - 1]}`
}

function bio(d, stints) {
  const teams = [...new Set(stints.map((s) => s.team))]
  const span = d.first_season === d.last_season ? `in ${d.first_season}` : `between ${d.first_season} and ${d.last_season}`
  let s = `${d.name} is a ${d.nationality} driver who started ${d.starts} Grand${d.starts === 1 ? '' : 's'} Prix ${span}, driving for ${listJoin(teams.slice(0, 5))}${teams.length > 5 ? ` and ${teams.length - 5} other teams` : ''}.`
  if (d.titles) s += ` A ${d.titles}-time World Champion (${d.title_years.join(', ')}),`
  else s += ' '
  if (d.wins) s += `${d.titles ? ' they' : 'They'} won ${d.wins} race${d.wins > 1 ? 's' : ''}, took ${d.podiums} podiums and ${d.poles} pole positions.`
  else if (d.podiums) s += `${d.titles ? ' they' : 'They'} reached the podium ${d.podiums} time${d.podiums > 1 ? 's' : ''}.`
  else s += `${d.titles ? ' they' : 'Their'} best finish was P${d.best_finish}.`
  return s
}

export default function DriverDetail() {
  const { id } = useParams()
  const { data, loading, error } = useApi(`/drivers/${id}`)
  if (loading) return <div className="wrap section"><Loader /></div>
  if (error) return <div className="wrap section"><ErrorBox error={error} /></div>
  const d = data.driver
  const color = teamColor(d.last_team)
  const seasons = data.seasons

  return (
    <div className="detail" style={{ '--team': color }}>
      <section className="detail-hero">
        <div className="wrap detail-hero-inner">
          <div>
            <Link to="/drivers" className="back">← All drivers</Link>
            <p className="eyebrow"><Flag nationality={d.nationality} /> {d.nationality} · {d.last_team}</p>
            <h1 className="detail-name"><span>{d.forename}</span> {d.surname}</h1>
            <p className="detail-meta">
              {d.dob && <>Born {new Date(d.dob).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}{data.age && d.last_season >= 2020 ? ` (age ${data.age})` : ''} · </>}
              {d.first_season}–{d.last_season}
              {d.titles > 0 && <> · <b className="gold">{d.titles}× World Champion</b></>}
            </p>
          </div>
          <div className="detail-number">{d.number || d.code || ''}</div>
        </div>
      </section>

      <div className="wrap">
        <div className="stat-strip">
          {[['Starts', d.starts], ['Wins', d.wins], ['Podiums', d.podiums], ['Poles', d.poles], ['Fastest laps', d.fastest_laps], ['Points', fmt.pts(d.points)], ['Win rate', fmt.pct(d.win_rate)], ['DNFs', d.dnfs]]
            .map(([l, v]) => <div key={l}><b>{v}</b><span>{l}</span></div>)}
        </div>

        <section className="section-tight two-col wide-left">
          <div>
            <h2 className="h2">Profile</h2>
            <p className="lead">{bio(d, data.stints)}</p>
            <div className="stints">
              {data.stints.map((s) => (
                <Link to={`/constructors/${s.constructorId}`} key={`${s.team}${s.from}`} className="stint" style={{ '--c': teamColor(s.team) }}>
                  <b>{s.team}</b><span>{s.from === s.to ? s.from : `${s.from}–${s.to}`}</span>
                </Link>
              ))}
            </div>
            {d.url && <a className="wiki-link" href={d.url} target="_blank" rel="noreferrer">Read the full story on Wikipedia ↗</a>}
          </div>
          <div className="panel">
            <h3 className="h3">Finishing positions</h3>
            <Plot theme="fan" height={240}
              data={[{ type: 'bar', x: data.finish_distribution.map((x) => x.position), y: data.finish_distribution.map((x) => x.count),
                marker: { color: data.finish_distribution.map((x) => (x.position <= 3 ? '#e10600' : x.position <= 10 ? '#8b8b99' : '#3a3a48')) },
                hovertemplate: 'P%{x}: %{y} times<extra></extra>' }]}
              layout={{ xaxis: { title: 'Finish (classified results)', dtick: 1 }, yaxis: { title: 'Races' }, bargap: 0.15 }} />
          </div>
        </section>

        <section className="section-tight">
          <div className="panel">
            <h3 className="h3">Season by season</h3>
            <Plot theme="fan" height={300}
              data={[
                { type: 'bar', name: 'Points', x: seasons.map((s) => s.year), y: seasons.map((s) => s.points),
                  marker: { color: seasons.map((s) => teamColor(s.constructor_name)) }, customdata: seasons.map((s) => [s.constructor_name, s.wins]),
                  hovertemplate: '%{x} · %{customdata[0]}<br>%{y} pts · %{customdata[1]} wins<extra></extra>' },
                { type: 'scatter', mode: 'lines+markers', name: 'Championship position', x: seasons.map((s) => s.year), y: seasons.map((s) => s.championship_pos),
                  yaxis: 'y2', line: { color: '#fff', width: 2 }, marker: { size: 6 }, hovertemplate: 'P%{y} in championship<extra></extra>' },
              ]}
              layout={{ yaxis: { title: 'Points' }, yaxis2: { title: 'Champ. pos.', overlaying: 'y', side: 'right', autorange: 'reversed', showgrid: false },
                xaxis: { dtick: seasons.length > 15 ? 2 : 1 }, legend: { orientation: 'h', y: 1.12 } }} />
          </div>
        </section>

        <section className="section-tight two-col">
          <div className="panel">
            <h3 className="h3">Season table</h3>
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Year</th><th>Team</th><th>Races</th><th>Wins</th><th>Pod.</th><th>Pts</th><th>Pos</th></tr></thead>
                <tbody>{seasons.slice().reverse().map((s) => (
                  <tr key={s.year} className={s.championship_pos === 1 ? 'gold-row' : ''}>
                    <td>{s.year}</td><td>{s.constructor_name}</td><td>{s.races}</td><td>{s.wins}</td><td>{s.podiums}</td><td>{fmt.pts(s.points)}</td><td>{s.championship_pos ? `P${s.championship_pos}` : '–'}</td>
                  </tr>))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="panel">
            <h3 className="h3">Latest races</h3>
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Race</th><th>Grid</th><th>Result</th><th>Pts</th></tr></thead>
                <tbody>{data.recent_results.map((r) => (
                  <tr key={r.raceId}><td>{r.year} {r.race_name.replace(' Grand Prix', ' GP')}<small className="muted block">{r.constructor_name}</small></td>
                    <td>{r.grid || 'PL'}</td><td>{/^\d+$/.test(r.positionText) ? `P${r.positionText}` : <span className="muted">{r.status}</span>}</td><td>{fmt.pts(r.points)}</td></tr>))}
                </tbody>
              </table>
            </div>
            {data.dnf_causes.length > 0 && (
              <p className="muted small">Most common retirements: {data.dnf_causes.slice(0, 4).map((c) => `${c.status} (${c.count})`).join(', ')}</p>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
