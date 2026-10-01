import { useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { teamColor } from '../../teams'
import { Card, Field, MultiSelect, Note, PageHeader, Table, useAdmin } from '../ui'

export default function Qualifying() {
  const { range, filters } = useAdmin()
  const [ids, setIds] = useState([])
  const { data, loading, error } = useApi('/admin/qualifying', { season_from: range.from, season_to: range.to, constructors: ids })
  const opts = filters.constructors.map((c) => ({ id: c.constructorId, name: c.constructor_name, first: c.first, last: c.last }))
  const teams = data ? [...new Set(data.gap_trend.map((r) => r.constructor_name))] : []

  return (
    <>
      <PageHeader title="Qualifying" desc="One-lap pace and how much the grid decides the race.">
        <Field label="Constructors (blank = 8 fastest)">
          <MultiSelect options={opts} value={ids} onChange={setIds} placeholder="All (auto)" sub={(o) => `${o.first}–${o.last}`} max={10} />
        </Field>
      </PageHeader>
      {loading && <Loader />}
      <ErrorBox error={error} />
      {data && (
        <div className="a-grid">
          <Card title="Gap to pole by season" sub="Median % gap of each team's best car per race; lower is faster" span={2}>
            {data.gap_trend.length ? (
              <Plot height={340} data={teams.map((t, i) => {
                const rows = data.gap_trend.filter((r) => r.constructor_name === t)
                return { type: 'scatter', mode: 'lines+markers', name: t, x: rows.map((r) => r.year), y: rows.map((r) => r.gap_pct), line: { color: teamColor(t, i), width: 2 } }
              })} layout={{ yaxis: { title: 'Gap to pole (%)', rangemode: 'tozero' }, xaxis: { dtick: 1 } }} />
            ) : <Note>No timed qualifying data in this range (lap times are recorded from 1994, consistently from 2003).</Note>}
          </Card>
          <Card title="Gap distribution" sub="Every race, best car per team">
            <Plot height={340} data={teams.map((t, i) => {
              const rows = data.gap_distribution.filter((r) => r.constructor_name === t)
              return { type: 'box', name: t, y: rows.map((r) => r.gap_pct), marker: { color: teamColor(t, i), size: 3 }, boxpoints: false }
            })} layout={{ showlegend: false, yaxis: { title: '%' }, xaxis: { tickangle: -35 } }} />
          </Card>
          <Card title="Grid → finish matrix" sub={`Classified finishes. Spearman ρ = ${fmt.num(data.spearman, 3)}`} span={2}>
            <Plot height={420} data={[{ type: 'heatmap', x: data.grid_finish_matrix.finish, y: data.grid_finish_matrix.grid, z: data.grid_finish_matrix.z,
              colorscale: [[0, '#f8fafc'], [0.2, '#bfdbfe'], [0.6, '#3b82f6'], [1, '#1e3a8a']], hovertemplate: 'Grid %{y} → P%{x}: %{z} times<extra></extra>' }]}
              layout={{ xaxis: { title: 'Finish position', dtick: 1 }, yaxis: { title: 'Grid position', dtick: 1, autorange: 'reversed' } }} />
          </Card>
          <Card title="Value of a grid slot" sub="Outcome rates by starting position">
            <Plot height={420} data={[
              { type: 'scatter', mode: 'lines+markers', name: 'Win', x: data.by_grid.map((r) => r.g), y: data.by_grid.map((r) => r.win_rate), line: { color: '#1d4ed8' } },
              { type: 'scatter', mode: 'lines+markers', name: 'Podium', x: data.by_grid.map((r) => r.g), y: data.by_grid.map((r) => r.podium_rate), line: { color: '#059669' } },
              { type: 'scatter', mode: 'lines+markers', name: 'Points (top 10)', x: data.by_grid.map((r) => r.g), y: data.by_grid.map((r) => r.points_rate), line: { color: '#d97706' } },
            ]} layout={{ xaxis: { title: 'Grid', dtick: 2 }, yaxis: { tickformat: '.0%' } }} />
          </Card>
          <Card title="By grid position" span={3}>
            <Table dense rows={data.by_grid} columns={[
              { key: 'g', label: 'Grid', num: true }, { key: 'n', label: 'Starts', num: true },
              { key: 'win_rate', label: 'Win %', num: true, render: (v) => fmt.pct(v) }, { key: 'podium_rate', label: 'Podium %', num: true, render: (v) => fmt.pct(v) },
              { key: 'points_rate', label: 'Top-10 %', num: true, render: (v) => fmt.pct(v) }, { key: 'avg_finish', label: 'Avg finish', num: true, render: (v) => fmt.num(v, 2) },
            ]} />
          </Card>
        </div>
      )}
    </>
  )
}
