import { useEffect, useState } from 'react'
import { api } from '../../api'
import { ErrorBox, fmt } from '../../components/common'
import Plot from '../../components/Plot'
import { palette } from '../../teams'
import { Card, Field, Kpis, Note, PageHeader, Segmented, Table, useAdmin } from '../ui'
import { Bars, Confusion, CorrHeatmap, Training, useModel } from './modelHooks'

function Predictor() {
  const { filters } = useAdmin()
  const drivers = filters.drivers.filter((d) => d.last >= 2004)
  const cons = filters.constructors.filter((c) => c.last >= 2004)
  const circuits = filters.circuits.filter((c) => c.last >= 2004)
  const [f, setF] = useState({ driver_id: 830, constructor_id: 9, grid: 5, circuit_id: 14, season: 2024, round: 16, driver_form: null, constructor_form: null })
  const [out, setOut] = useState(null)
  const [err, setErr] = useState(null)
  const [forms, setForms] = useState(null)

  useEffect(() => {
    api('/admin/models/points/forms', { params: { driver_id: f.driver_id, constructor_id: f.constructor_id } }).then(setForms).catch(() => {})
  }, [f.driver_id, f.constructor_id])

  useEffect(() => {
    const t = setTimeout(() => {
      api('/admin/models/points/predict', { method: 'POST', body: f }).then((r) => { setOut(r); setErr(null) }).catch(setErr)
    }, 200)
    return () => clearTimeout(t)
  }, [f])
  const set = (k, num = true) => (e) => setF({ ...f, [k]: e.target.value === '' ? null : num ? +e.target.value : e.target.value })

  return (
    <Card title="What-if predictor" sub="Probability of a top-10 finish for a hypothetical start" span={3}>
      <div className="a-form-grid">
        <Field label="Driver"><select value={f.driver_id} onChange={set('driver_id')}>{drivers.map((d) => <option key={d.driverId} value={d.driverId}>{d.driver_name}</option>)}</select></Field>
        <Field label="Constructor"><select value={f.constructor_id} onChange={set('constructor_id')}>{cons.map((c) => <option key={c.constructorId} value={c.constructorId}>{c.constructor_name}</option>)}</select></Field>
        <Field label="Circuit"><select value={f.circuit_id} onChange={set('circuit_id')}>{circuits.map((c) => <option key={c.circuitId} value={c.circuitId}>{c.circuit_name}</option>)}</select></Field>
        <Field label={`Grid: P${f.grid}`}><input type="range" min={1} max={22} value={f.grid} onChange={set('grid')} /></Field>
        <Field label="Season"><input type="number" value={f.season} onChange={set('season')} /></Field>
        <Field label="Round"><input type="number" min={1} max={24} value={f.round} onChange={set('round')} /></Field>
        <Field label={`Driver form (auto ${fmt.num(forms?.driver_form, 2)})`}><input type="number" step="0.1" min={0} max={1} placeholder="auto" value={f.driver_form ?? ''} onChange={set('driver_form')} /></Field>
        <Field label={`Team form (auto ${fmt.num(forms?.constructor_form, 2)})`}><input type="number" step="0.1" min={0} max={1} placeholder="auto" value={f.constructor_form ?? ''} onChange={set('constructor_form')} /></Field>
      </div>
      <ErrorBox error={err} />
      {out && (
        <div className="a-probs">
          {Object.entries(out.probabilities).map(([k, v]) => (
            <div key={k} className="a-prob"><span>{k}</span><div className="a-prob-bar"><i style={{ width: `${v * 100}%` }} /></div><b>{fmt.pct(v)}</b></div>
          ))}
        </div>
      )}
      <Note>Form = share of the last 10 starts that ended in the top 10 (leak-free, from the notebook). Leave blank to use the latest value from the data.</Note>
    </Card>
  )
}

export default function ModelPoints() {
  const { data: r, error, training } = useModel('/admin/models/points')
  const [cm, setCm] = useState('Naive Bayes')
  const [rel, setRel] = useState('single')
  if (training) return <Training />
  if (error) return <ErrorBox error={error} />
  if (!r) return null
  const best = r.comparison.reduce((a, b) => (b.accuracy > a.accuracy ? b : a))

  return (
    <>
      <PageHeader title="Points-finish classifier" desc="Gaussian Naïve Bayes (from f1_naive_bayes_classification.ipynb) predicting whether a driver finishes in the top 10, from pre-race information only (2004+)." />
      <Kpis items={[
        ['Rows', fmt.int(r.rows), `${fmt.int(r.train_rows)} train / ${fmt.int(r.test_rows)} test`], ['Positive class', fmt.pct(r.positive_rate), 'points finishes'],
        ['Majority baseline', fmt.pct(r.majority_baseline)], ['Best test accuracy', fmt.pct(best.accuracy), best.model],
        ['5-fold CV (tuned NB)', fmt.pct(r.cv_mean), `± ${fmt.pct(r.cv_std)}`], ['Best var_smoothing', r.best_var_smoothing.toExponential(0), `CV ${fmt.pct(r.best_cv)}`],
      ]} />
      <div className="a-grid">
        <Predictor />
        <Card title="Model comparison" sub="80/20 stratified split" span={2}>
          <Table dense rows={r.comparison} columns={[
            { key: 'model', label: 'Model' }, ...['accuracy', 'precision', 'recall', 'f1', 'auc'].map((k) => ({ key: k, label: k.toUpperCase(), num: true, render: (v) => fmt.num(v, 3) })),
          ]} />
          <Plot height={260} data={['accuracy', 'f1', 'auc'].map((m, i) => ({ type: 'bar', name: m.toUpperCase(), x: r.comparison.map((c) => c.model), y: r.comparison.map((c) => c[m]), marker: { color: palette(i) } }))}
            layout={{ barmode: 'group', yaxis: { range: [0.5, 1] }, shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: r.majority_baseline, y1: r.majority_baseline, line: { dash: 'dot', color: '#9ca3af' } }] }} />
        </Card>
        <Card title="ROC curves">
          <Plot height={380} data={[...Object.entries(r.roc).map(([k, v], i) => ({ type: 'scatter', mode: 'lines', name: k, x: v.fpr, y: v.tpr, line: { color: palette(i) } })),
            { type: 'scatter', mode: 'lines', x: [0, 1], y: [0, 1], line: { dash: 'dot', color: '#9ca3af' }, showlegend: false }]}
            layout={{ xaxis: { title: 'False positive rate' }, yaxis: { title: 'True positive rate' } }} />
        </Card>
        <Card title="Confusion matrix" tools={<select value={cm} onChange={(e) => setCm(e.target.value)}>{Object.keys(r.confusion).map((k) => <option key={k}>{k}</option>)}</select>}>
          <Confusion z={r.confusion[cm]} labels={['Outside', 'Points']} />
        </Card>
        <Card title="Which features carry the signal?" tools={<Segmented value={rel} onChange={setRel} items={[['single', 'Solo NB accuracy'], ['mi', 'Mutual info'], ['rf', 'RF importance']]} />}>
          <Bars items={rel === 'single' ? r.single_feature : rel === 'mi' ? r.mutual_info : r.rf_importance} />
        </Card>
        <Card title="Points rate by grid slot" sub="Why grid is the strongest feature">
          <Plot height={280} data={[{ type: 'bar', x: r.grid_curve.map((g) => g.grid), y: r.grid_curve.map((g) => g.rate), marker: { color: '#2563eb' } }]}
            layout={{ xaxis: { title: 'Grid', dtick: 2 }, yaxis: { tickformat: '.0%' } }} />
        </Card>
        <Card title="Feature correlation" sub="Naïve Bayes assumes weak dependence" span={2}>
          <CorrHeatmap corr={r.correlation} />
        </Card>
        <Card title="Cross-validation" sub="Tuned NB, 5 stratified folds">
          <Plot height={300} data={[{ type: 'bar', x: r.cv_scores.map((_, i) => `Fold ${i + 1}`), y: r.cv_scores, marker: { color: '#64748b' }, text: r.cv_scores.map((v) => fmt.pct(v)), textposition: 'outside' }]}
            layout={{ yaxis: { range: [0.6, 0.85], tickformat: '.0%' } }} />
        </Card>
        <Card title="Classification report (baseline NB)" span={3}>
          <Table dense rows={['Outside points', 'Points finish', 'macro avg', 'weighted avg'].map((k) => ({ cls: k, ...r.classification_report[k] }))} columns={[
            { key: 'cls', label: 'Class' }, { key: 'precision', label: 'Precision', num: true, render: (v) => fmt.num(v, 3) },
            { key: 'recall', label: 'Recall', num: true, render: (v) => fmt.num(v, 3) }, { key: 'f1-score', label: 'F1', num: true, render: (v) => fmt.num(v, 3) },
            { key: 'support', label: 'Support', num: true, render: (v) => fmt.int(v) },
          ]} />
        </Card>
      </div>
    </>
  )
}
