import { useEffect, useState } from 'react'
import { api } from '../../api'
import { ErrorBox, fmt } from '../../components/common'
import Plot from '../../components/Plot'
import { palette, teamColor } from '../../teams'
import { Card, Kpis, Note, PageHeader, Segmented, Table } from '../ui'
import { Bars, Confusion, Training, useModel } from './modelHooks'

function Scenario({ report }) {
  const t = report.template_race.teams
  const [grids, setGrids] = useState(() => Object.fromEntries(report.top10.map((c) => [c, t[c]?.best_grid ?? 21])))
  const [form, setForm] = useState(() => Object.fromEntries(report.top10.map((c) => [c, { prev_wins_10: t[c]?.prev_wins_10 ?? 0, prev_podiums_10: t[c]?.prev_podiums_10 ?? 0 }])))
  const [out, setOut] = useState(null)
  const [err, setErr] = useState(null)
  const [model, setModel] = useState('Random Forest')
  useEffect(() => {
    const h = setTimeout(() => api('/admin/models/winner/predict', { method: 'POST', body: { grids, form } }).then((r) => { setOut(r); setErr(null) }).catch(setErr), 200)
    return () => clearTimeout(h)
  }, [grids, form])
  const res = out?.[model] || []
  return (
    <Card title="Scenario: who wins from this grid?" sub={`Starts from the last race in the data (${report.template_race.season} R${report.template_race.round}); edit best grid slot and recent form per team`} span={3}
      tools={<Segmented value={model} onChange={setModel} items={[['Random Forest', 'RF'], ['Decision Tree', 'Tree'], ['Naive Bayes', 'NB']]} />}>
      <div className="a-scenario">
        <table className="a-table dense">
          <thead><tr><th>Constructor</th><th className="num">Best grid</th><th className="num">Wins (last 10)</th><th className="num">Podiums (last 10)</th></tr></thead>
          <tbody>{report.top10.map((c) => (
            <tr key={c}>
              <td><i className="a-swatch" style={{ background: teamColor(c) }} />{c}</td>
              <td className="num"><input type="number" min={1} max={21} value={grids[c]} onChange={(e) => setGrids({ ...grids, [c]: +e.target.value })} /></td>
              <td className="num"><input type="number" min={0} max={10} value={form[c].prev_wins_10} onChange={(e) => setForm({ ...form, [c]: { ...form[c], prev_wins_10: +e.target.value } })} /></td>
              <td className="num"><input type="number" min={0} max={10} value={form[c].prev_podiums_10} onChange={(e) => setForm({ ...form, [c]: { ...form[c], prev_podiums_10: +e.target.value } })} /></td>
            </tr>))}
          </tbody>
        </table>
        <div>
          <ErrorBox error={err} />
          <Plot height={380} data={[{ type: 'bar', orientation: 'h', y: res.map((x) => x.team).reverse(), x: res.map((x) => x.p).reverse(), marker: { color: res.map((x) => teamColor(x.team)).reverse() },
            text: res.map((x) => fmt.pct(x.p)).reverse(), textposition: 'outside', hovertemplate: '%{y}: %{x:.1%}<extra></extra>' }]}
            layout={{ xaxis: { tickformat: '.0%', range: [0, Math.min(1, (res[0]?.p || 0.5) * 1.25)] }, margin: { l: 110, r: 30, t: 10, b: 30 } }} />
        </div>
      </div>
      <Note>Grid 21 means “no car qualified”. Probabilities only cover the ten most successful constructors since 2000 (the notebook's class set), so a team outside that list cannot be predicted.</Note>
    </Card>
  )
}

export default function ModelWinner() {
  const { data: r, error, training } = useModel('/admin/models/winner')
  const [cm, setCm] = useState('Random Forest')
  const [rel, setRel] = useState('rf')
  if (training) return <Training />
  if (error) return <ErrorBox error={error} />
  if (!r) return null
  const best = r.comparison.reduce((a, b) => (b.accuracy > a.accuracy ? b : a))
  const dist = Object.entries(r.class_distribution).sort((a, b) => b[1] - a[1])
  const majority = dist[0][1] / dist.reduce((s, x) => s + x[1], 0)

  return (
    <>
      <PageHeader title="Race-winner classifier" desc="Which constructor wins the race? Multi-class model from f1_classification_project.ipynb: one row per race, per-team grid and form features, time-based split." />
      <Kpis items={[['Classes', r.classes.length, 'top-10 winning teams since 2000'], ['Train races', r.train_races, `2000–${r.test_from - 1}`], ['Test races', r.test_races, `${r.test_from}–2024`],
        ['Features', r.n_features], ['Best accuracy', fmt.pct(best.accuracy), best.model], ['Most frequent winner share', fmt.pct(majority), dist[0][0]]]} />
      <div className="a-grid">
        <Scenario report={r} />
        <Card title="Model comparison" sub="Macro-averaged precision / recall / F1" span={2}>
          <Table dense rows={r.comparison} columns={[{ key: 'model', label: 'Model' }, ...['accuracy', 'precision', 'recall', 'f1'].map((k) => ({ key: k, label: k.toUpperCase(), num: true, render: (v) => fmt.num(v, 3) }))]} />
          <Plot height={240} data={['accuracy', 'f1'].map((m, i) => ({ type: 'bar', name: m.toUpperCase(), x: r.comparison.map((c) => c.model), y: r.comparison.map((c) => c[m]), marker: { color: palette(i) } }))}
            layout={{ barmode: 'group', yaxis: { range: [0, 1] } }} />
        </Card>
        <Card title="RF accuracy by test season">
          <Plot height={330} data={[{ type: 'bar', x: r.rf_by_season.map((x) => x.season), y: r.rf_by_season.map((x) => x.ok), marker: { color: '#2563eb' } }]} layout={{ yaxis: { tickformat: '.0%', range: [0, 1] }, xaxis: { dtick: 1 } }} />
        </Card>
        <Card title="Confusion matrix" span={2} tools={<select value={cm} onChange={(e) => setCm(e.target.value)}>{Object.keys(r.confusion).map((k) => <option key={k}>{k}</option>)}</select>}>
          <Confusion z={r.confusion[cm].z} labels={r.confusion[cm].labels} height={400} />
        </Card>
        <Card title="Top features" tools={<Segmented value={rel} onChange={setRel} items={[['rf', 'RF importance'], ['mi', 'Mutual info']]} />}>
          <Bars items={rel === 'rf' ? r.rf_importance : r.mutual_info} height={400} />
        </Card>
        <Card title="Winners in the training+test data" span={3}>
          <Plot height={260} data={[{ type: 'bar', x: dist.map((d) => d[0]), y: dist.map((d) => d[1]), marker: { color: dist.map((d) => teamColor(d[0])) } }]} layout={{ yaxis: { title: 'Races won' } }} />
        </Card>
      </div>
    </>
  )
}
