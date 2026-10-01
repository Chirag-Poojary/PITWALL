import { useEffect, useState } from 'react'
import { api } from '../../api'
import { fmt, Loader } from '../../components/common'
import Plot from '../../components/Plot'

/** Fetch a model report; while the server is still training, poll every 3 s. */
export function useModel(path) {
  const [state, setState] = useState({ data: null, error: null, training: false })
  useEffect(() => {
    let alive = true
    let timer
    const load = () => api(path).then((data) => alive && setState({ data, error: null, training: false }))
      .catch((e) => {
        if (!alive) return
        if (e.status === 503) { setState({ data: null, error: null, training: true }); timer = setTimeout(load, 3000) }
        else setState({ data: null, error: e, training: false })
      })
    load()
    return () => { alive = false; clearTimeout(timer) }
  }, [path])
  return state
}

export function Training() {
  return <div className="a-training"><Loader label="Models are training on first start (about 20 s). This page will refresh automatically" /></div>
}

export function Confusion({ z, labels, height = 300 }) {
  return (
    <Plot height={height} data={[{ type: 'heatmap', z, x: labels, y: labels, colorscale: [[0, '#f8fafc'], [1, '#1d4ed8']], showscale: false,
      text: z.map((r) => r.map(String)), texttemplate: '%{text}', hovertemplate: 'Actual %{y}<br>Predicted %{x}: %{z}<extra></extra>' }]}
      layout={{ xaxis: { title: 'Predicted', tickangle: labels.length > 4 ? -40 : 0 }, yaxis: { title: 'Actual', autorange: 'reversed' }, margin: { l: 100, r: 10, t: 10, b: 80 } }} />
  )
}

export function Bars({ items, height = 280, color = '#2563eb', valueFmt }) {
  return (
    <Plot height={height} data={[{ type: 'bar', orientation: 'h', y: items.map((i) => i.feature).reverse(), x: items.map((i) => i.value ?? i.accuracy).reverse(), marker: { color },
      hovertemplate: `%{y}: %{x:${valueFmt || '.3f'}}<extra></extra>` }]} layout={{ margin: { l: 150, r: 10, t: 10, b: 30 }, yaxis: { tickfont: { size: 11 } } }} />
  )
}

export function CorrHeatmap({ corr, height = 360 }) {
  return (
    <Plot height={height} data={[{ type: 'heatmap', z: corr.z, x: corr.labels, y: corr.labels, zmin: -1, zmax: 1,
      colorscale: [[0, '#b91c1c'], [0.5, '#f8fafc'], [1, '#1d4ed8']], text: corr.z.map((r) => r.map((v) => fmt.num(v, 2))), texttemplate: '%{text}', textfont: { size: 9 } }]}
      layout={{ xaxis: { tickangle: -40 }, yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 10, t: 10, b: 100 } }} />
  )
}
