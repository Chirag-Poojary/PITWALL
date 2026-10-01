import { useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { teamColor } from '../../teams'
import { Card, Field, MultiSelect, Note, PageHeader, Table, useAdmin } from '../ui'

export default function PitStops() {
  const { range, filters } = useAdmin()
  const [ids, setIds] = useState([])
  const from = Math.max(range.from, 2011)
  const { data, loading, error } = useApi('/admin/pitstops', { season_from: from, season_to: range.to, constructors: ids })
  const opts = filters.constructors.filter((c) => c.last >= 2011).map((c) => ({ id: c.constructorId, name: c.constructor_name }))
  const teams = data ? data.by_team.map((t) => t.constructor_name) : []

  return (
    <>
      <PageHeader title="Pit stops" desc={`Pit-lane performance, ${from}–${range.to}.`}>
        <Field label="Constructors (blank = 10 busiest)">
          <MultiSelect options={opts} value={ids} onChange={setIds} placeholder="All (auto)" max={10} />
        </Field>
      </PageHeader>
      {range.from < 2011 && <Note>Pit-stop timing starts in 2011; earlier seasons are ignored on this page.</Note>}
      {loading && <Loader />}
      <ErrorBox error={error} />
      {data && (
        <div className="a-grid">
          <Card title="Pit-lane time by season" sub="Median with interquartile band" span={2}>
            <Plot height={320} data={[
              { type: 'scatter', x: data.by_season.map((r) => r.year), y: data.by_season.map((r) => r.p75), line: { width: 0 }, showlegend: false, hoverinfo: 'skip' },
              { type: 'scatter', x: data.by_season.map((r) => r.year), y: data.by_season.map((r) => r.p25), fill: 'tonexty', fillcolor: 'rgba(37,99,235,.15)', line: { width: 0 }, name: 'IQR', hoverinfo: 'skip' },
              { type: 'scatter', mode: 'lines+markers', x: data.by_season.map((r) => r.year), y: data.by_season.map((r) => r.median), name: 'Median', line: { color: '#1d4ed8', width: 2 } },
            ]} layout={{ yaxis: { title: 'Seconds' }, xaxis: { dtick: 1 } }} />
          </Card>
          <Card title="Stops per car per race">
            <Plot height={320} data={[{ type: 'bar', x: data.by_season.map((r) => r.year), y: data.by_season.map((r) => r.stops_per_car), marker: { color: '#64748b' },
              hovertemplate: '%{x}: %{y:.2f}<extra></extra>' }]} layout={{ xaxis: { dtick: 1 } }} />
          </Card>
          <Card title="Distribution by team" sub="Sorted by median" span={2}>
            <Plot height={360} data={teams.map((t, i) => ({ type: 'box', name: t, y: data.distribution.filter((r) => r.constructor_name === t).map((r) => r.duration_s),
              marker: { color: teamColor(t, i), size: 2 }, boxpoints: false }))} layout={{ showlegend: false, yaxis: { title: 'Seconds', range: [15, 40] } }} />
          </Card>
          <Card title="Team ranking">
            <Table dense rows={data.by_team} columns={[
              { key: 'constructor_name', label: 'Team' }, { key: 'median', label: 'Median', num: true, render: (v) => fmt.num(v, 2) },
              { key: 'std', label: 'Std dev', num: true, render: (v) => fmt.num(v, 2) }, { key: 'size', label: 'Stops', num: true },
            ]} />
          </Card>
          <Card title="Median by team and season" span={2}>
            {(() => {
              const yrs = [...new Set(data.team_season.map((r) => r.year))].sort()
              return <Plot height={340} data={[{ type: 'heatmap', x: yrs, y: teams, z: teams.map((t) => yrs.map((y) => data.team_season.find((r) => r.year === y && r.constructor_name === t)?.duration_s ?? null)),
                colorscale: [[0, '#065f46'], [0.5, '#fef9c3'], [1, '#b91c1c']], hovertemplate: '%{y} %{x}: %{z:.2f} s<extra></extra>', colorbar: { title: { text: 's' } } }]}
                layout={{ xaxis: { dtick: 1 }, margin: { l: 120, r: 10, t: 10, b: 40 } }} />
            })()}
          </Card>
          <Card title="When teams stop" sub="All stops by lap number">
            <Plot height={340} data={[{ type: 'bar', x: data.lap_histogram.map((r) => r.lap), y: data.lap_histogram.map((r) => r.stops), marker: { color: '#94a3b8' } }]}
              layout={{ xaxis: { title: 'Lap', range: [0, 75] }, yaxis: { title: 'Stops' } }} />
          </Card>
          <Card title="Fastest pit-lane times" span={3}>
            <Table dense rows={data.fastest} columns={[
              { key: 'year', label: 'Season' }, { key: 'race_name', label: 'Race' }, { key: 'driver_name', label: 'Driver' }, { key: 'constructor_name', label: 'Team' },
              { key: 'lap', label: 'Lap', num: true }, { key: 'duration_s', label: 'Time (s)', num: true, render: (v) => fmt.num(v, 3) },
            ]} />
            <Note>{data.note}</Note>
          </Card>
        </div>
      )}
    </>
  )
}
