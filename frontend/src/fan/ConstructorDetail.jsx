import { Link, useParams } from 'react-router-dom'
import { ErrorBox, Flag, fmt, Loader, useApi } from '../components/common'
import Plot from '../components/Plot'
import { teamColor } from '../teams'

export default function ConstructorDetail() {
  const { id } = useParams()
  const { data, loading, error } = useApi(`/constructors/${id}`)
  if (loading) return <div className="wrap section"><Loader /></div>
  if (error) return <div className="wrap section"><ErrorBox error={error} /></div>
  const c = data.constructor
  const color = teamColor(c.name)
  const s = data.seasons
  const best = s.reduce((a, b) => (b.points > (a?.points ?? -1) ? b : a), null)
  const summary = `${c.name} is a ${c.nationality} constructor that entered ${c.races} Grands Prix between ${c.first_season} and ${c.last_season}, fielding ${c.drivers_count} different drivers. `
    + (c.titles ? `The team won the Constructors’ Championship ${c.titles} time${c.titles > 1 ? 's' : ''} (${c.title_years.join(', ')}). ` : '')
    + (c.wins ? `It has ${c.wins} race wins and ${c.podiums} podiums` : `Its best results include ${c.podiums} podium finishes`)
    + (best ? `, with its highest-scoring season in ${best.year} (${fmt.pts(best.points)} points).` : '.')

  return (
    <div className="detail" style={{ '--team': color }}>
      <section className="detail-hero">
        <div className="wrap detail-hero-inner">
          <div>
            <Link to="/constructors" className="back">← All constructors</Link>
            <p className="eyebrow"><Flag nationality={c.nationality} /> {c.nationality}</p>
            <h1 className="detail-name">{c.name}</h1>
            <p className="detail-meta">{c.first_season}–{c.last_season}{c.titles > 0 && <> · <b className="gold">{c.titles}× Constructors’ Champion</b></>}</p>
          </div>
          <div className="detail-swatch" />
        </div>
      </section>
      <div className="wrap">
        <div className="stat-strip">
          {[['Races', c.races], ['Wins', c.wins], ['Podiums', c.podiums], ['Poles', c.poles], ['Points', fmt.pts(c.points)], ['Titles', c.titles], ['Win rate', fmt.pct(c.win_rate)], ['DNF rate', fmt.pct(c.dnf_rate)]]
            .map(([l, v]) => <div key={l}><b>{v}</b><span>{l}</span></div>)}
        </div>
        <section className="section-tight two-col wide-left">
          <div>
            <h2 className="h2">Profile</h2>
            <p className="lead">{summary}</p>
            {c.url && <a className="wiki-link" href={c.url} target="_blank" rel="noreferrer">Read the full story on Wikipedia ↗</a>}
          </div>
          <div className="panel">
            <h3 className="h3">Why they retired</h3>
            {data.dnf_causes.length ? (
              <Plot theme="fan" height={240}
                data={[{ type: 'bar', orientation: 'h', y: data.dnf_causes.map((x) => x.status).reverse(), x: data.dnf_causes.map((x) => x.count).reverse(),
                  marker: { color }, hovertemplate: '%{y}: %{x}<extra></extra>' }]}
                layout={{ margin: { l: 110, r: 10, t: 6, b: 30 }, xaxis: { title: 'Retirements' } }} />
            ) : <p className="muted">No retirements recorded.</p>}
          </div>
        </section>
        <section className="section-tight">
          <div className="panel">
            <h3 className="h3">Points and championship position by season</h3>
            <Plot theme="fan" height={300}
              data={[
                { type: 'bar', name: 'Points', x: s.map((x) => x.year), y: s.map((x) => x.points), marker: { color },
                  customdata: s.map((x) => x.wins), hovertemplate: '%{x}: %{y} pts · %{customdata} wins<extra></extra>' },
                { type: 'scatter', mode: 'lines+markers', name: 'Constructors’ position', x: s.map((x) => x.year), y: s.map((x) => x.championship_pos),
                  yaxis: 'y2', line: { color: '#fff', width: 2 }, hovertemplate: 'P%{y}<extra></extra>' },
              ]}
              layout={{ yaxis: { title: 'Points' }, yaxis2: { title: 'Champ. pos.', overlaying: 'y', side: 'right', autorange: 'reversed', showgrid: false }, legend: { orientation: 'h', y: 1.12 } }} />
          </div>
        </section>
        <section className="section-tight">
          <div className="panel">
            <h3 className="h3">Drivers who raced for {c.name}</h3>
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Driver</th><th>Years</th><th>Races</th><th>Wins</th><th>Podiums</th><th>Points</th></tr></thead>
                <tbody>{data.drivers.map((d) => (
                  <tr key={d.driverId}><td><Link to={`/drivers/${d.driverId}`}>{d.driver_name}</Link></td><td>{d.first === d.last ? d.first : `${d.first}–${d.last}`}</td>
                    <td>{d.races}</td><td>{d.wins}</td><td>{d.podiums}</td><td>{fmt.pts(d.points)}</td></tr>))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
