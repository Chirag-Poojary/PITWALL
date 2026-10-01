import { useEffect, useMemo, useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { teamColor } from '../../teams'
import { Card, Field, Note, PageHeader, Segmented, Table, useAdmin } from '../ui'

// distinguish team-mates: first driver solid, second dashed
function styleFor(laps) {
  const seen = {}
  return laps.map((l) => {
    seen[l.team] = (seen[l.team] || 0) + 1
    return { color: teamColor(l.team), dash: seen[l.team] > 1 ? 'dot' : 'solid' }
  })
}

export default function RaceAnalysis() {
  const { filters } = useAdmin()
  const seasons = filters.seasons.filter((y) => y >= 1996).slice().reverse()
  const [season, setSeason] = useState(2024)
  const races = useApi('/admin/races', { season })
  const [raceId, setRaceId] = useState(null)
  const [chart, setChart] = useState('position')
  const [clean, setClean] = useState(true)
  const [focus, setFocus] = useState([])

  useEffect(() => {
    if (races.data?.length) {
      const withLaps = races.data.filter((r) => r.has_laps)
      setRaceId((withLaps[withLaps.length - 1] || races.data[races.data.length - 1]).raceId)
    }
  }, [races.data])
  useEffect(() => setFocus([]), [raceId])

  const race = useApi(raceId ? `/admin/race/${raceId}` : null)
  const d = race.data
  const styles = useMemo(() => (d ? styleFor(d.laps) : []), [d])
  const visible = (code) => !focus.length || focus.includes(code)

  const lapTraces = useMemo(() => {
    if (!d?.laps.length) return []
    return d.laps.map((l, i) => {
      let y = chart === 'position' ? l.position : chart === 'gap' ? l.gap : l.time
      if (chart === 'time' && clean) {
        const sorted = [...l.time].sort((a, b) => a - b)
        const med = sorted[Math.floor(sorted.length / 2)]
        y = l.time.map((t) => (t > med * 1.07 ? null : t))
      }
      return { type: 'scatter', mode: chart === 'time' ? 'lines+markers' : 'lines', name: l.code, x: l.lap, y,
        line: { color: styles[i].color, dash: styles[i].dash, width: visible(l.code) ? 2 : 1 }, marker: { size: 3 },
        opacity: visible(l.code) ? 1 : 0.12, connectgaps: false,
        hovertemplate: `${l.name} (${l.team})<br>Lap %{x}: %{y}<extra></extra>` }
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, chart, clean, focus, styles])

  const pitTraces = useMemo(() => {
    if (!d?.pit_stops.length) return []
    return [{ type: 'scatter', mode: 'markers', x: d.pit_stops.map((p) => p.lap), y: d.pit_stops.map((p) => p.code || p.driver_name),
      marker: { size: d.pit_stops.map((p) => Math.max(8, Math.min(22, (p.duration_s || 20) / 1.4))), color: d.pit_stops.map((p) => teamColor(p.constructor_name)), line: { color: '#fff', width: 1 } },
      text: d.pit_stops.map((p) => `${p.driver_name}: stop ${p.stop}, ${fmt.num(p.duration_s, 2)} s`), hovertemplate: '%{text}<br>Lap %{x}<extra></extra>' }]
  }, [d])

  return (
    <>
      <PageHeader title="Race analysis" desc="Lap-by-lap positions, gaps, lap times, pit stops and qualifying for a single Grand Prix (lap data from 1996).">
        <Field label="Season">
          <select value={season} onChange={(e) => { setSeason(+e.target.value); setRaceId(null) }}>{seasons.map((y) => <option key={y}>{y}</option>)}</select>
        </Field>
        <Field label="Race">
          <select value={raceId || ''} onChange={(e) => setRaceId(+e.target.value)}>
            {races.data?.map((r) => <option key={r.raceId} value={r.raceId}>R{r.round} · {r.race_name}{r.has_laps ? '' : ' (no lap data)'}</option>)}
          </select>
        </Field>
      </PageHeader>
      {(races.loading || race.loading) && <Loader />}
      <ErrorBox error={races.error || race.error} />
      {d && (
        <div className="a-grid">
          <Card span={3} title={`${d.race.season} ${d.race.name}`} sub={`Round ${d.race.round} · ${d.race.circuit}, ${d.race.country} · ${d.race.date}`}
            tools={<Segmented value={chart} onChange={setChart} items={[['position', 'Positions'], ['gap', 'Gap to leader'], ['time', 'Lap times']]} />}>
            {d.laps.length ? (
              <>
                <div className="a-chipbar">
                  <span className="a-muted small">Focus:</span>
                  {d.laps.map((l) => (
                    <button key={l.code} className={`a-chip ${focus.includes(l.code) ? 'on' : ''}`} style={{ '--c': teamColor(l.team) }}
                      onClick={() => setFocus(focus.includes(l.code) ? focus.filter((c) => c !== l.code) : [...focus, l.code])}>{l.code}</button>
                  ))}
                  {focus.length > 0 && <button className="a-link" onClick={() => setFocus([])}>Clear</button>}
                  {chart === 'time' && <label className="a-check"><input type="checkbox" checked={clean} onChange={(e) => setClean(e.target.checked)} /> Hide pit / SC laps (&gt;107% of median)</label>}
                </div>
                <Plot height={460} data={lapTraces} layout={{
                  xaxis: { title: 'Lap' },
                  yaxis: chart === 'position' ? { title: 'Position', autorange: 'reversed', dtick: 1 } : chart === 'gap' ? { title: 'Gap to leader (s)', autorange: 'reversed' } : { title: 'Lap time (s)' },
                  legend: { orientation: 'v', x: 1.01, y: 1, font: { size: 10 } }, margin: { l: 56, r: 70, t: 10, b: 40 } }} />
              </>
            ) : <Note>No lap-by-lap timing for this race in the dataset.</Note>}
          </Card>
          <Card title="Classification" span={2}>
            <Table dense maxHeight={520} rows={d.results} columns={[
              { key: 'positionText', label: 'Pos' }, { key: 'driver_name', label: 'Driver' }, { key: 'constructor_name', label: 'Team' },
              { key: 'grid', label: 'Grid', num: true, render: (v) => (v === 0 ? 'PL' : v) },
              { key: 'gained', label: '+/-', num: true, render: (v) => (v === null || v === undefined ? '–' : <span className={v > 0 ? 'a-up' : v < 0 ? 'a-down' : ''}>{v > 0 ? `+${v}` : v}</span>) },
              { key: 'laps', label: 'Laps', num: true }, { key: 'time', label: 'Time / status', render: (v, r) => v || r.status },
              { key: 'fastestLapTime', label: 'Fastest lap', render: (v, r) => (v ? <span className={r.rank === '1' || r.rank === 1 ? 'a-purple' : ''}>{v}</span> : '–') },
              { key: 'points', label: 'Pts', num: true, render: fmt.pts },
            ]} />
          </Card>
          <Card title="Qualifying">
            {d.qualifying.length ? (
              <Table dense maxHeight={520} rows={d.qualifying} columns={[
                { key: 'position', label: 'Pos', num: true }, { key: 'driver_name', label: 'Driver' },
                { key: 'q3', label: 'Q3' }, { key: 'q2', label: 'Q2' }, { key: 'q1', label: 'Q1' },
                { key: 'gap_pct', label: 'Gap', num: true, render: (v) => (v === null || v === undefined ? '–' : `+${fmt.num(v, 2)}%`) },
              ]} />
            ) : <Note>No qualifying data.</Note>}
          </Card>
          <Card title="Pit stops" sub="Marker size = pit-lane time" span={2}>
            {d.pit_stops.length ? (
              <Plot height={Math.max(300, d.results.length * 20)} data={pitTraces}
                layout={{ xaxis: { title: 'Lap', range: [0, Math.max(...d.results.map((r) => r.laps || 0)) + 1] },
                  yaxis: { type: 'category', categoryorder: 'array', categoryarray: d.results.map((r) => r.code || r.driver_name).reverse() }, showlegend: false, margin: { l: 60, r: 10, t: 10, b: 40 } }} />
            ) : <Note>Pit-stop data is only available from 2011.</Note>}
          </Card>
          <Card title="Stop times">
            <Table dense maxHeight={420} rows={d.pit_stops} columns={[
              { key: 'driver_name', label: 'Driver' }, { key: 'stop', label: '#', num: true }, { key: 'lap', label: 'Lap', num: true },
              { key: 'duration_s', label: 'Time (s)', num: true, render: (v) => fmt.num(v, 3) },
            ]} />
          </Card>
        </div>
      )}
    </>
  )
}
