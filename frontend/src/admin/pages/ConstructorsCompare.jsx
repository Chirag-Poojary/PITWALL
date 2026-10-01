import { useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { teamColor } from '../../teams'
import { Card, Field, MultiSelect, Note, PageHeader, Table, useAdmin } from '../ui'

function Trend({ data, k, title, sub, fmtY, reversed, height = 300 }) {
  return (
    <Card title={title} sub={sub}>
      <Plot height={height} data={data.map((c, i) => ({ type: 'scatter', mode: 'lines+markers', name: c.name, x: c.seasons.map((s) => s.year), y: c.seasons.map((s) => s[k]),
        line: { color: teamColor(c.name, i), width: 2 }, marker: { size: 5 }, connectgaps: false }))}
        layout={{ yaxis: { tickformat: fmtY, autorange: reversed ? 'reversed' : true } }} />
    </Card>
  )
}

export default function ConstructorsCompare() {
  const { range, filters } = useAdmin()
  const [ids, setIds] = useState([9, 131, 6, 1])
  const { data, loading, error } = useApi(ids.length ? '/admin/constructors/compare' : null, { ids, season_from: range.from, season_to: range.to })
  const opts = filters.constructors.map((c) => ({ id: c.constructorId, name: c.constructor_name, first: c.first, last: c.last }))
  const cons = data?.constructors || []

  return (
    <>
      <PageHeader title="Constructor comparison" desc="Performance, qualifying pace, pit-stop speed and reliability side by side.">
        <Field label="Constructors">
          <MultiSelect options={opts} value={ids} onChange={setIds} placeholder="Search teams…" sub={(o) => `${o.first}–${o.last}`} />
        </Field>
      </PageHeader>
      {loading && <Loader />}
      <ErrorBox error={error} />
      {cons.length > 0 && (
        <div className="a-grid">
          <Card title="Summary" span={3}>
            <Table dense rows={cons.map((c) => ({ name: c.name, ...c.summary }))} columns={[
              { key: 'name', label: 'Constructor' }, { key: 'races', label: 'Races', num: true }, { key: 'points', label: 'Points', num: true, render: fmt.pts },
              { key: 'wins', label: 'Wins', num: true }, { key: 'podiums', label: 'Podiums', num: true }, { key: 'poles', label: 'Poles', num: true },
              { key: 'one_twos', label: '1-2 finishes', num: true }, { key: 'dnf_rate', label: 'DNF %', num: true, render: (v) => fmt.pct(v) },
            ]} />
          </Card>
          <Trend data={cons} k="points" title="Points per season" />
          <Trend data={cons} k="champ_pos" title="Constructors’ championship position" reversed />
          <Trend data={cons} k="points_per_race" title="Points per race" sub="Normalises for calendar length" />
          <Trend data={cons} k="quali_gap_pct" title="Qualifying gap to pole (%)" sub="Median of the team’s best car each race; lower is faster" />
          <Trend data={cons} k="median_pit_s" title="Median pit-stop time (s)" sub="Pit-lane time, 2011+" />
          <Trend data={cons} k="dnf_rate" title="DNF rate" fmtY=".0%" />
          <Card title="Why they retired" sub="DNFs by cause group in range" span={2}>
            <Plot height={320} data={(() => {
              const groups = [...new Set(cons.flatMap((c) => Object.keys(c.status_groups)))]
              return groups.map((g, gi) => ({ type: 'bar', name: g, x: cons.map((c) => c.name), y: cons.map((c) => c.status_groups[g] || 0),
                marker: { color: ['#ef4444', '#f59e0b', '#8b5cf6', '#0ea5e9', '#10b981', '#64748b', '#ec4899', '#a3a3a3', '#84cc16'][gi % 9] } }))
            })()} layout={{ barmode: 'stack', yaxis: { title: 'Retirements' } }} />
          </Card>
          <Card title="Top scorers per team">
            {cons.map((c) => (
              <div key={c.constructorId} className="a-mini-list">
                <h4 style={{ borderColor: teamColor(c.name) }}>{c.name}</h4>
                {c.drivers.slice(0, 4).map((d) => <div key={d.driver_name}><span>{d.driver_name}</span><b>{fmt.pts(d.points)}</b></div>)}
              </div>
            ))}
          </Card>
        </div>
      )}
      {!ids.length && <Note>Select at least one constructor.</Note>}
    </>
  )
}
