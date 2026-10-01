import { useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { Card, PageHeader, Segmented, Table, useAdmin } from '../ui'

const METRICS = [['pole_to_win', 'Pole → win'], ['avg_abs_change', 'Position changes'], ['dnf_rate', 'DNF rate'], ['avg_fl_speed', 'Fastest-lap speed']]

export default function Circuits() {
  const { range } = useAdmin()
  const [metric, setMetric] = useState('pole_to_win')
  const { data, loading, error } = useApi('/admin/circuits', { season_from: range.from, season_to: range.to })
  if (loading) return <Loader />
  if (error) return <ErrorBox error={error} />
  const c = data.circuits.filter((x) => x[metric] !== null)
  const label = METRICS.find((m) => m[0] === metric)[1]
  const isPct = metric === 'pole_to_win' || metric === 'dnf_rate'

  return (
    <>
      <PageHeader title="Circuits" desc={`Track characteristics from race results, ${range.from}–${range.to}.`} />
      <div className="a-grid">
        <Card title="Circuit map" sub={`Bubble size = races hosted · colour = ${label}`} span={3} tools={<Segmented value={metric} onChange={setMetric} items={METRICS} />}>
          <Plot height={440} data={[{ type: 'scattergeo', lat: c.map((x) => x.lat), lon: c.map((x) => x.lng), text: c.map((x) => `${x.name} (${x.country})`),
            marker: { size: c.map((x) => 6 + Math.sqrt(x.races) * 3), color: c.map((x) => x[metric]), colorscale: 'Viridis', line: { color: '#fff', width: 0.5 },
              colorbar: { title: { text: label, side: 'right' }, tickformat: isPct ? '.0%' : undefined } },
            customdata: c.map((x) => x.races), hovertemplate: `%{text}<br>${label}: %{marker.color:${isPct ? '.0%' : '.2f'}}<br>Races: %{customdata}<extra></extra>` }]}
            layout={{ geo: { showland: true, landcolor: '#eef2f7', showcountries: true, countrycolor: '#cbd5e1', coastlinecolor: '#cbd5e1', projection: { type: 'natural earth' }, bgcolor: 'rgba(0,0,0,0)' }, margin: { l: 0, r: 0, t: 0, b: 0 } }} />
        </Card>
        <Card title={`Ranking: ${label}`} span={1}>
          <Plot height={520} data={[{ type: 'bar', orientation: 'h', y: [...c].sort((a, b) => b[metric] - a[metric]).slice(0, 20).map((x) => x.name.replace(/ (Grand Prix )?Circuit$/, '')),
            x: [...c].sort((a, b) => b[metric] - a[metric]).slice(0, 20).map((x) => x[metric]), marker: { color: '#3b82f6' } }]}
            layout={{ yaxis: { autorange: 'reversed', tickfont: { size: 10 } }, xaxis: { tickformat: isPct ? '.0%' : undefined }, margin: { l: 170, r: 10, t: 10, b: 30 } }} />
        </Card>
        <Card title="All circuits" span={2}>
          <Table dense maxHeight={520} rows={data.circuits} columns={[
            { key: 'name', label: 'Circuit' }, { key: 'country', label: 'Country' }, { key: 'races', label: 'Races', num: true },
            { key: 'pole_to_win', label: 'Pole→win', num: true, render: (v) => fmt.pct(v, 0) }, { key: 'winner_avg_grid', label: 'Winner avg grid', num: true, render: (v) => fmt.num(v, 1) },
            { key: 'avg_abs_change', label: 'Avg |Δpos|', num: true, render: (v) => fmt.num(v, 2) }, { key: 'dnf_rate', label: 'DNF %', num: true, render: (v) => fmt.pct(v, 0) },
            { key: 'avg_fl_speed', label: 'FL km/h', num: true, render: (v) => fmt.num(v, 1) }, { key: 'top_winner', label: 'Most wins', render: (v, r) => (v ? `${v} (${r.top_winner_wins})` : '–') },
          ]} />
        </Card>
      </div>
    </>
  )
}
