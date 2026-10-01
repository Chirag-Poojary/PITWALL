import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { teamColor } from '../../teams'
import { Card, Kpis, PageHeader, Table, useAdmin } from '../ui'

export default function Overview() {
  const { range } = useAdmin()
  const { data, loading, error } = useApi('/admin/overview', { season_from: range.from, season_to: range.to })
  if (loading) return <Loader />
  if (error) return <ErrorBox error={error} />
  const k = data.kpis
  const bs = data.by_season
  const yrs = bs.map((r) => r.year)

  return (
    <>
      <PageHeader title="Overview" desc={`Championship landscape, ${range.from}–${range.to}.`} />
      <Kpis items={[
        ['Seasons', k.seasons], ['Races', fmt.int(k.races)], ['Drivers', k.drivers], ['Constructors', k.constructors],
        ['Different winners', k.winners, `${k.winning_teams} winning teams`], ['Pole → win', fmt.pct(k.pole_to_win)],
        ['DNF rate', fmt.pct(k.dnf_rate), 'share of all starts'], ['Median pit stop', k.median_pit ? `${fmt.num(k.median_pit)} s` : '–', 'pit-lane time, 2011+'],
      ]} />
      <div className="a-grid">
        <Card title="Race wins by constructor" sub="Top 8 winning teams in range; others grouped" span={2}>
          <Plot height={340} data={data.wins_by_constructor.series.map((s, i) => ({
            type: 'bar', name: s.name, x: data.wins_by_constructor.seasons, y: s.values,
            marker: { color: s.name === 'Other' ? '#cbd5e1' : teamColor(s.name, i) }, hovertemplate: `${s.name}: %{y}<extra>%{x}</extra>` }))}
            layout={{ barmode: 'stack', yaxis: { title: 'Wins' }, legend: { orientation: 'h', y: -0.15 } }} />
        </Card>
        <Card title="Points share" sub="All points scored in range">
          <Plot height={340} data={[{ type: 'pie', hole: 0.55, labels: data.points_share.map((p) => p.name), values: data.points_share.map((p) => p.value),
            marker: { colors: data.points_share.map((p, i) => (p.name === 'Other' ? '#e2e8f0' : teamColor(p.name, i))) }, textinfo: 'percent', sort: false,
            hovertemplate: '%{label}<br>%{value:,.0f} pts (%{percent})<extra></extra>' }]}
            layout={{ showlegend: true, legend: { orientation: 'v', x: 1, y: 0.5, font: { size: 10 } }, margin: { l: 0, r: 0, t: 0, b: 0 } }} />
        </Card>
        <Card title="Competitiveness" sub="Unique race winners and champion's winning margin per season" span={2}>
          <Plot height={300} data={[
            { type: 'bar', name: 'Unique winners', x: yrs, y: bs.map((r) => r.unique_winners), marker: { color: '#93c5fd' } },
            { type: 'scatter', mode: 'lines+markers', name: 'Title margin (pts)', x: yrs, y: bs.map((r) => r.title_margin), yaxis: 'y2', line: { color: '#1d4ed8' },
              customdata: bs.map((r) => r.champion), hovertemplate: '%{x}: %{y} pts<br>Champion: %{customdata}<extra></extra>' },
          ]} layout={{ yaxis: { title: 'Winners' }, yaxis2: { title: 'Margin (pts)', overlaying: 'y', side: 'right', showgrid: false } }} />
        </Card>
        <Card title="DNF rate & pole conversion" sub="Per season">
          <Plot height={300} data={[
            { type: 'scatter', mode: 'lines', name: 'DNF rate', x: yrs, y: bs.map((r) => r.dnf_rate), line: { color: '#dc2626' } },
            { type: 'scatter', mode: 'lines', name: 'Pole → win', x: yrs, y: bs.map((r) => r.pole_to_win), line: { color: '#059669' } },
          ]} layout={{ yaxis: { tickformat: '.0%', range: [0, 1] } }} />
        </Card>
        <Card title="Top drivers in range" sub="Click a column to sort" span={3}>
          <Table rows={data.top_drivers} columns={[
            { key: 'driver_name', label: 'Driver' }, { key: 'starts', label: 'Starts', num: true },
            { key: 'points', label: 'Points', num: true, render: fmt.pts }, { key: 'wins', label: 'Wins', num: true },
            { key: 'podiums', label: 'Podiums', num: true }, { key: 'poles', label: 'Poles', num: true },
            { key: 'avg_finish', label: 'Avg finish', num: true, render: (v) => fmt.num(v, 2) },
            { key: 'dnf_rate', label: 'DNF %', num: true, render: (v) => fmt.pct(v) },
          ]} />
        </Card>
        <Card title="Champions" span={3}>
          <Table dense rows={bs.slice().reverse()} columns={[
            { key: 'year', label: 'Season' }, { key: 'champion', label: 'Champion' },
            { key: 'champion_points', label: 'Points', num: true, render: fmt.pts }, { key: 'title_margin', label: 'Margin', num: true, render: fmt.pts },
            { key: 'races', label: 'Races', num: true }, { key: 'unique_winners', label: 'Winners', num: true },
            { key: 'dnf_rate', label: 'DNF %', num: true, render: (v) => fmt.pct(v) },
          ]} />
        </Card>
      </div>
    </>
  )
}
