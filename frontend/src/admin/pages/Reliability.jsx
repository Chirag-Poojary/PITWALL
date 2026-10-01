import { useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { teamColor } from '../../teams'
import { Card, Field, Kpis, MultiSelect, PageHeader, Table, useAdmin } from '../ui'

const GROUP_COLORS = { 'Accident / Collision': '#ef4444', 'Engine / Power unit': '#f59e0b', 'Gearbox / Driveline': '#8b5cf6', 'Hydraulics / Electrics': '#0ea5e9',
  'Chassis / Brakes / Tyres': '#10b981', Disqualified: '#64748b', 'Did not start / qualify': '#a3a3a3', 'Driver (injury / illness)': '#ec4899', 'Other / Retired': '#cbd5e1' }

export default function Reliability() {
  const { range, filters } = useAdmin()
  const [ids, setIds] = useState([])
  const [minEntries, setMin] = useState(30)
  const { data, loading, error } = useApi('/admin/reliability', { season_from: range.from, season_to: range.to, constructors: ids, min_entries: minEntries })
  const opts = filters.constructors.map((c) => ({ id: c.constructorId, name: c.constructor_name, first: c.first, last: c.last }))

  return (
    <>
      <PageHeader title="Reliability" desc="Retirements by cause, season and team.">
        <Field label="Constructors (blank = all)"><MultiSelect options={opts} value={ids} onChange={setIds} placeholder="All" sub={(o) => `${o.first}–${o.last}`} max={12} /></Field>
        <Field label="Min. entries"><input type="number" min={1} value={minEntries} onChange={(e) => setMin(+e.target.value || 1)} style={{ width: 90 }} /></Field>
      </PageHeader>
      {loading && <Loader />}
      <ErrorBox error={error} />
      {data && (
        <>
          <Kpis items={[['Overall DNF rate', fmt.pct(data.overall_dnf_rate)], ['Most common cause', data.top_causes[0]?.status || '–', `${data.top_causes[0]?.count || 0} retirements`],
            ['Most reliable team', data.teams[0]?.constructor_name || '–', data.teams[0] ? `${fmt.pct(data.teams[0].dnf_rate)} DNF` : ''],
            ['Least reliable team', data.teams[data.teams.length - 1]?.constructor_name || '–', data.teams.length ? `${fmt.pct(data.teams[data.teams.length - 1].dnf_rate)} DNF` : '']]} />
          <div className="a-grid">
            <Card title="Retirement rate by cause" sub="Share of all starts, per season" span={2}>
              <Plot height={360} data={data.season_rates.map((s) => ({ type: 'scatter', mode: 'lines', stackgroup: 'one', name: s.name, x: data.seasons, y: s.values,
                line: { width: 0.5, color: GROUP_COLORS[s.name] }, fillcolor: GROUP_COLORS[s.name], hovertemplate: `${s.name}: %{y:.1%}<extra>%{x}</extra>` }))}
                layout={{ yaxis: { tickformat: '.0%', title: 'Share of starts' } }} />
            </Card>
            <Card title="Top 20 recorded causes">
              <Plot height={360} data={[{ type: 'bar', orientation: 'h', y: data.top_causes.map((c) => c.status).reverse(), x: data.top_causes.map((c) => c.count).reverse(), marker: { color: '#64748b' } }]}
                layout={{ margin: { l: 120, r: 10, t: 10, b: 30 } }} />
            </Card>
            <Card title="DNF rate by team" sub={`Teams with ≥ ${minEntries} entries`} span={2}>
              <Plot height={Math.max(300, data.teams.length * 16)} data={[{ type: 'bar', orientation: 'h', y: data.teams.map((t) => t.constructor_name), x: data.teams.map((t) => t.dnf_rate),
                marker: { color: data.teams.map((t, i) => teamColor(t.constructor_name, i)) }, customdata: data.teams.map((t) => t.entries), hovertemplate: '%{y}: %{x:.1%} of %{customdata} entries<extra></extra>' }]}
                layout={{ xaxis: { tickformat: '.0%' }, yaxis: { autorange: 'reversed' }, margin: { l: 130, r: 10, t: 10, b: 30 } }} />
            </Card>
            <Card title="Cause mix by team" sub="Most reliable 12 teams (or your selection)">
              <Plot height={Math.max(300, data.team_causes.teams.length * 26)} data={data.team_causes.series.map((s) => ({ type: 'bar', orientation: 'h', name: s.name, y: data.team_causes.teams, x: s.values, marker: { color: GROUP_COLORS[s.name] } }))}
                layout={{ barmode: 'stack', margin: { l: 120, r: 10, t: 10, b: 30 }, legend: { font: { size: 9 } } }} />
            </Card>
            <Card title="Team table" span={3}>
              <Table dense rows={data.teams} columns={[{ key: 'constructor_name', label: 'Team' }, { key: 'entries', label: 'Entries', num: true }, { key: 'dnf_rate', label: 'DNF %', num: true, render: (v) => fmt.pct(v) }]} />
            </Card>
          </div>
        </>
      )}
    </>
  )
}
