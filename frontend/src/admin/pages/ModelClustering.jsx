import { useMemo, useState } from 'react'
import { ErrorBox, fmt, Loader, useApi } from '../../components/common'
import Plot from '../../components/Plot'
import { Card, Field, Kpis, Note, PageHeader, Table, useAdmin } from '../ui'

const TIER_COLORS = ['#1d4ed8', '#059669', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#65a30d']
const FEATS = [['avg_grid', 'Avg grid'], ['avg_finish', 'Avg finish'], ['total_points', 'Total points'], ['points_rate', 'Points rate']]

export default function ModelClustering() {
  const { range } = useAdmin()
  const [k, setK] = useState(4)
  const [minRaces, setMin] = useState(5)
  const [feats, setFeats] = useState(['avg_grid', 'avg_finish'])
  const [axes, setAxes] = useState(['avg_grid', 'avg_finish'])
  const [q, setQ] = useState('')
  const from = Math.max(range.from, 1950)
  const { data, loading, error } = useApi('/admin/models/clustering', { k, season_from: from, season_to: range.to, min_races: minRaces, features: feats })
  const label = (f) => FEATS.find((x) => x[0] === f)[1]

  const traces = useMemo(() => {
    if (!data) return []
    const tiers = [...new Set(data.points.map((p) => p.tier_rank))].sort()
    const hl = q.length >= 3 ? q.toLowerCase() : null
    const t = tiers.map((tr) => {
      const pts = data.points.filter((p) => p.tier_rank === tr)
      return { type: 'scattergl', mode: 'markers', name: pts[0].tier, x: pts.map((p) => p[axes[0]]), y: pts.map((p) => p[axes[1]]),
        text: pts.map((p) => `${p.driver_name} ${p.season} (${p.team})<br>${fmt.pts(p.total_points)} pts, ${p.races} races`),
        marker: { color: TIER_COLORS[tr], size: 7, opacity: hl ? 0.15 : 0.7, line: { color: '#fff', width: 0.5 } }, hovertemplate: '%{text}<extra></extra>' }
    })
    if (hl) {
      const pts = data.points.filter((p) => p.driver_name.toLowerCase().includes(hl))
      t.push({ type: 'scatter', mode: 'markers+text', name: 'Search', x: pts.map((p) => p[axes[0]]), y: pts.map((p) => p[axes[1]]), text: pts.map((p) => String(p.season)),
        textposition: 'top center', textfont: { size: 10 }, marker: { color: '#111827', size: 10, symbol: 'diamond' }, hovertemplate: '%{text}<extra></extra>' })
    }
    if (data.features.includes(axes[0]) && data.features.includes(axes[1])) {
      t.push({ type: 'scatter', mode: 'markers', name: 'Centroids', x: data.centroids.map((c) => c[axes[0]]), y: data.centroids.map((c) => c[axes[1]]),
        marker: { symbol: 'x', size: 16, color: '#111827', line: { width: 2 } }, hovertemplate: 'Centroid<extra></extra>' })
    }
    return t
  }, [data, axes, q])

  const toggleFeat = (f) => setFeats(feats.includes(f) ? (feats.length > 2 ? feats.filter((x) => x !== f) : feats) : [...feats, f])
  const rev = (f) => (f === 'avg_grid' || f === 'avg_finish' ? 'reversed' : true)

  return (
    <>
      <PageHeader title="Driver clustering (K-Means)" desc="Groups driver-seasons into performance tiers, as in clustering.ipynb. Features are standardised before clustering; tiers are ordered by average finish.">
        <Field label={`K = ${k}`}><input type="range" min={2} max={8} value={k} onChange={(e) => setK(+e.target.value)} /></Field>
        <Field label="Min. races"><input type="number" min={1} max={20} value={minRaces} onChange={(e) => setMin(+e.target.value || 1)} style={{ width: 80 }} /></Field>
        <Field label="Clustering features">
          <div className="a-seg">{FEATS.map(([f, l]) => <button key={f} className={feats.includes(f) ? 'on' : ''} onClick={() => toggleFeat(f)}>{l}</button>)}</div>
        </Field>
      </PageHeader>
      {loading && <Loader />}
      <ErrorBox error={error} />
      {data && (
        <>
          <Kpis items={[['Driver-seasons', fmt.int(data.n), `${from}–${range.to}, ≥ ${minRaces} races`], ['Clusters', data.k], ['Silhouette', fmt.num(data.silhouette, 3), 'higher = better separated'],
            ['Features', data.features.map(label).join(', ')]]} />
          <div className="a-grid">
            <Card title="Clusters" span={2} tools={
              <div className="a-inline">
                <select value={axes[0]} onChange={(e) => setAxes([e.target.value, axes[1]])}>{FEATS.map(([f, l]) => <option key={f} value={f}>X: {l}</option>)}</select>
                <select value={axes[1]} onChange={(e) => setAxes([axes[0], e.target.value])}>{FEATS.map(([f, l]) => <option key={f} value={f}>Y: {l}</option>)}</select>
                <input placeholder="Highlight driver…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 160 }} />
              </div>}>
              <Plot height={480} data={traces} layout={{ xaxis: { title: label(axes[0]), autorange: rev(axes[0]) }, yaxis: { title: label(axes[1]), autorange: rev(axes[1]) } }} />
            </Card>
            <Card title="Choosing K" sub="Elbow (inertia) and silhouette score">
              <Plot height={480} data={[
                { type: 'scatter', mode: 'lines+markers', name: 'Inertia', x: data.elbow.map((e) => e.k), y: data.elbow.map((e) => e.inertia), line: { color: '#1d4ed8' } },
                { type: 'scatter', mode: 'lines+markers', name: 'Silhouette', x: data.elbow.map((e) => e.k), y: data.elbow.map((e) => e.silhouette), yaxis: 'y2', line: { color: '#d97706' } },
              ]} layout={{ xaxis: { title: 'K', dtick: 1 }, yaxis: { title: 'Inertia' }, yaxis2: { title: 'Silhouette', overlaying: 'y', side: 'right', showgrid: false },
                shapes: [{ type: 'line', x0: k, x1: k, yref: 'paper', y0: 0, y1: 1, line: { dash: 'dot', color: '#9ca3af' } }] }} />
            </Card>
            <Card title="Cluster profiles" span={2}>
              <Table dense rows={data.summary} columns={[
                { key: 'tier', label: 'Tier', render: (v, r) => <span><i className="a-swatch" style={{ background: TIER_COLORS[r.tier_rank] }} />{v}</span> },
                { key: 'n', label: 'Driver-seasons', num: true }, { key: 'avg_grid', label: 'Avg grid', num: true, render: (v) => fmt.num(v, 2) },
                { key: 'avg_finish', label: 'Avg finish', num: true, render: (v) => fmt.num(v, 2) }, { key: 'total_points', label: 'Avg points', num: true, render: (v) => fmt.num(v, 1) },
              ]} />
            </Card>
            <Card title="Tier sizes">
              <Plot height={260} data={[{ type: 'bar', x: data.summary.map((s) => s.tier), y: data.summary.map((s) => s.n), marker: { color: data.summary.map((s) => TIER_COLORS[s.tier_rank]) } }]}
                layout={{ xaxis: { tickangle: -20, tickfont: { size: 10 } } }} />
            </Card>
            <Card title="Best seasons in each tier" span={3}>
              <Table dense rows={data.top_members} columns={[
                { key: 'tier', label: 'Tier' }, { key: 'driver_name', label: 'Driver' }, { key: 'season', label: 'Season' }, { key: 'team', label: 'Team' },
                { key: 'avg_grid', label: 'Avg grid', num: true, render: (v) => fmt.num(v, 2) }, { key: 'avg_finish', label: 'Avg finish', num: true, render: (v) => fmt.num(v, 2) },
                { key: 'total_points', label: 'Points', num: true, render: fmt.pts },
              ]} />
              <Note>Points systems changed over the decades, so “Total points” is only comparable within similar eras; avg grid / finish travel better across eras.</Note>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
