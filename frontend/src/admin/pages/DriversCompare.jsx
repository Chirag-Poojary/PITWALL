import { useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { palette } from '../../teams'
import { Card, Field, MultiSelect, Note, PageHeader, Segmented, Table, useAdmin } from '../ui'

const METRICS = [['points', 'Points'], ['wins', 'Wins'], ['avg_finish', 'Avg finish'], ['avg_grid', 'Avg grid'], ['champ_pos', 'Champ. position'], ['dnf_rate', 'DNF rate']]

export default function DriversCompare() {
  const { range, filters } = useAdmin()
  const [ids, setIds] = useState([1, 830, 846])
  const [metric, setMetric] = useState('points')
  const { data, loading, error } = useApi(ids.length ? '/admin/drivers/compare' : null, { ids, season_from: range.from, season_to: range.to })
  const opts = filters.drivers.map((d) => ({ id: d.driverId, name: d.driver_name, first: d.first, last: d.last }))
  const drv = data?.drivers || []
  const reversed = ['avg_finish', 'avg_grid', 'champ_pos'].includes(metric)

  return (
    <>
      <PageHeader title="Driver comparison" desc="Compare up to six drivers across the selected seasons.">
        <Field label="Drivers">
          <MultiSelect options={opts} value={ids} onChange={setIds} placeholder="Search drivers…" sub={(o) => `${o.first}–${o.last}`} />
        </Field>
      </PageHeader>
      {!ids.length && <Note>Select at least one driver.</Note>}
      {loading && <Loader />}
      <ErrorBox error={error} />
      {data && drv.length === 0 && <Note>None of the selected drivers raced in {range.from}–{range.to}.</Note>}
      {drv.length > 0 && (
        <div className="a-grid">
          <Card title="Summary" span={3}>
            <Table dense rows={drv.map((d) => ({ name: d.name, ...d.summary, h2h_race: `${d.teammate.race.ahead}–${d.teammate.race.behind}`, h2h_quali: `${d.teammate.quali.ahead}–${d.teammate.quali.behind}` }))}
              columns={[
                { key: 'name', label: 'Driver' }, { key: 'starts', label: 'Starts', num: true }, { key: 'points', label: 'Points', num: true, render: fmt.pts },
                { key: 'points_per_race', label: 'Pts / race', num: true, render: (v) => fmt.num(v, 2) }, { key: 'wins', label: 'Wins', num: true },
                { key: 'podiums', label: 'Podiums', num: true }, { key: 'poles', label: 'Poles', num: true },
                { key: 'avg_grid', label: 'Avg grid', num: true, render: (v) => fmt.num(v, 2) }, { key: 'avg_finish', label: 'Avg finish', num: true, render: (v) => fmt.num(v, 2) },
                { key: 'avg_gained', label: 'Avg places gained', num: true, render: (v) => fmt.num(v, 2) }, { key: 'dnf_rate', label: 'DNF %', num: true, render: (v) => fmt.pct(v) },
                { key: 'avg_quali_gap_pct', label: 'Median quali gap', num: true, render: (v) => (v === null ? '–' : `${fmt.num(v, 2)}%`) },
                { key: 'h2h_race', label: 'Race H2H vs team-mate', num: true }, { key: 'h2h_quali', label: 'Quali H2H', num: true },
              ]} />
            <Note>Head-to-head counts races where both team-mates were classified (race) or both set a qualifying position (quali), shown as ahead–behind. Quali gap is the % gap of the driver’s best qualifying lap to pole.</Note>
          </Card>
          <Card title="Season trend" span={2} tools={<Segmented value={metric} onChange={setMetric} items={METRICS} />}>
            <Plot height={340} data={drv.map((d, i) => ({ type: 'scatter', mode: 'lines+markers', name: d.name, x: d.seasons.map((s) => s.year), y: d.seasons.map((s) => s[metric]),
              line: { color: palette(i), width: 2 }, marker: { size: 6 } }))}
              layout={{ yaxis: { autorange: reversed ? 'reversed' : true, tickformat: metric === 'dnf_rate' ? '.0%' : undefined }, xaxis: { dtick: 1 } }} />
          </Card>
          <Card title="Finishing positions" sub="Classified finishes only">
            <Plot height={340} data={drv.map((d, i) => ({ type: 'bar', name: d.name, x: d.finish_distribution.map((x) => x.position), y: d.finish_distribution.map((x) => x.count), marker: { color: palette(i) } }))}
              layout={{ barmode: 'group', xaxis: { dtick: 1, title: 'Position' }, yaxis: { title: 'Races' } }} />
          </Card>
          <Card title="Grid vs finish" sub="Each dot is a classified race; below the diagonal means places gained" span={2}>
            <Plot height={360} data={[
              ...drv.map((d, i) => ({ type: 'scattergl', mode: 'markers', name: d.name, x: d.grid_vs_finish.map((r) => r.grid0 + (Math.random() - 0.5) * 0.4), y: d.grid_vs_finish.map((r) => r.positionOrder + (Math.random() - 0.5) * 0.4),
                marker: { color: palette(i), size: 6, opacity: 0.55 }, text: d.grid_vs_finish.map((r) => `${r.year} ${r.race_name}`), hovertemplate: '%{text}<br>Grid %{x:.0f} → P%{y:.0f}<extra></extra>' })),
              { type: 'scatter', mode: 'lines', x: [1, 24], y: [1, 24], line: { color: '#9ca3af', dash: 'dot' }, showlegend: false, hoverinfo: 'skip' },
            ]} layout={{ xaxis: { title: 'Grid', range: [0, 24] }, yaxis: { title: 'Finish', range: [24, 0] } }} />
          </Card>
          <Card title="Outcome mix" sub="Share of starts by result type">
            <Plot height={360} data={(() => {
              const groups = [...new Set(drv.flatMap((d) => Object.keys(d.status_groups)))]
              return groups.map((g, gi) => ({ type: 'bar', orientation: 'h', name: g, y: drv.map((d) => d.name),
                x: drv.map((d) => (d.status_groups[g] || 0) / d.summary.starts), marker: { color: g === 'Finished' ? '#94a3b8' : palette(gi + 1) }, hovertemplate: `${g}: %{x:.1%}<extra></extra>` }))
            })()} layout={{ barmode: 'stack', xaxis: { tickformat: '.0%' }, margin: { l: 110, r: 10, t: 10, b: 30 }, legend: { font: { size: 10 } } }} />
          </Card>
          {drv.map((d) => (
            <Card key={d.driverId} title={`${d.name}: team-mate record`} sub="Races where both finished">
              <Table dense maxHeight={240} rows={d.teammate.by_teammate} columns={[
                { key: 'driver_name', label: 'Team-mate' }, { key: 'races', label: 'Races', num: true },
                { key: 'ahead', label: 'Ahead', num: true }, { key: 'pct', label: 'Ahead %', num: true, render: (_, r) => fmt.pct(r.ahead / r.races, 0) },
              ]} />
            </Card>
          ))}
        </div>
      )}
    </>
  )
}
