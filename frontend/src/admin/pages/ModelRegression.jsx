import { ErrorBox, fmt } from '../../components/common'
import Plot from '../../components/Plot'
import { palette } from '../../teams'
import { Card, Kpis, Note, PageHeader, Table } from '../ui'
import { Bars, CorrHeatmap, Training, useModel } from './modelHooks'

export default function ModelRegression() {
  const { data: r, error, training } = useModel('/admin/models/regression')
  if (training) return <Training />
  if (error) return <ErrorBox error={error} />
  if (!r) return null
  const best = r.comparison[0]
  const s = r.scatter
  const lo = Math.min(...s.actual, ...s.predicted) - 5
  const hi = Math.max(...s.actual, ...s.predicted) + 5

  return (
    <>
      <PageHeader title="Fastest-lap speed regression" desc="Predicting each driver's fastest-lap speed (km/h) from f1_regression_project.ipynb. Trained on 2004–2020, tested on 2021–2024." />
      <Kpis items={[['Rows', fmt.int(r.rows), `${fmt.int(r.train_rows)} train / ${fmt.int(r.test_rows)} test`], ['Best model', best.model], ['Test RMSE', `${fmt.num(best.rmse, 2)} km/h`],
        ['Test MAE', `${fmt.num(best.mae, 2)} km/h`], ['Test R²', fmt.num(best.r2, 3)], ['Features', r.features.length]]} />
      <div className="a-grid">
        <Card title="Model comparison" sub="Held-out seasons 2021–2024, sorted by RMSE" span={2}>
          <Table dense rows={r.comparison} columns={[{ key: 'model', label: 'Model' }, { key: 'mae', label: 'MAE', num: true, render: (v) => fmt.num(v, 2) },
            { key: 'rmse', label: 'RMSE', num: true, render: (v) => fmt.num(v, 2) }, { key: 'r2', label: 'R²', num: true, render: (v) => fmt.num(v, 3) }]} />
          <Plot height={240} data={['mae', 'rmse'].map((m, i) => ({ type: 'bar', name: m.toUpperCase(), x: r.comparison.map((c) => c.model), y: r.comparison.map((c) => c[m]), marker: { color: palette(i) } }))}
            layout={{ barmode: 'group', yaxis: { title: 'km/h' } }} />
        </Card>
        <Card title="Random Forest feature importance">
          <Bars items={r.rf_importance} height={420} color="#059669" />
        </Card>
        <Card title={`Predicted vs actual (${best.model})`} sub="Sample of up to 1,200 test rows" span={2}>
          <Plot height={420} data={[
            { type: 'scattergl', mode: 'markers', x: s.actual, y: s.predicted, text: s.circuit.map((c, i) => `${s.season[i]} ${c}`), marker: { size: 5, color: '#2563eb', opacity: 0.45 },
              hovertemplate: '%{text}<br>Actual %{x:.1f} · Pred %{y:.1f}<extra></extra>', name: 'Rows' },
            { type: 'scatter', mode: 'lines', x: [lo, hi], y: [lo, hi], line: { dash: 'dot', color: '#ef4444' }, name: 'Perfect' },
          ]} layout={{ xaxis: { title: 'Actual (km/h)' }, yaxis: { title: 'Predicted (km/h)' } }} />
        </Card>
        <Card title="Residuals" sub="Predicted − actual">
          <Plot height={420} data={[{ type: 'histogram', x: r.residuals, nbinsx: 50, marker: { color: '#64748b' } }]} layout={{ xaxis: { title: 'km/h' }, bargap: 0.05 }} />
        </Card>
        <Card title="Error by circuit" sub="Mean absolute error on the test seasons" span={2}>
          <Table dense rows={r.by_circuit} columns={[{ key: 'circuit_name', label: 'Circuit' }, { key: 'n', label: 'Rows', num: true },
            { key: 'actual', label: 'Actual avg', num: true, render: (v) => fmt.num(v, 1) }, { key: 'predicted', label: 'Pred. avg', num: true, render: (v) => fmt.num(v, 1) },
            { key: 'mae', label: 'MAE', num: true, render: (v) => fmt.num(v, 2) }]} />
          <Note>Large errors usually come from circuits that changed layout or were new in the test period (e.g. Jeddah, Miami, Las Vegas), where the model has little history.</Note>
        </Card>
        <Card title="Correlation (numeric features + target)">
          <CorrHeatmap corr={r.correlation} height={420} />
        </Card>
      </div>
      <Note>{fmt.int(r.missing_target_rows)} rows without an official fastest-lap speed were excluded from training rather than imputed.</Note>
    </>
  )
}
