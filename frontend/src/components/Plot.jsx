import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'

const PlotBase = createPlotlyComponent(Plotly)

const THEMES = {
  fan: {
    font: { family: 'Titillium Web, sans-serif', color: '#c9c9d3', size: 13 },
    grid: '#2a2a36', zero: '#3a3a48', hover: { bgcolor: '#15151e', bordercolor: '#e10600', font: { color: '#fff' } },
  },
  admin: {
    font: { family: 'Inter, system-ui, sans-serif', color: '#374151', size: 12 },
    grid: '#eceef2', zero: '#d1d5db', hover: { bgcolor: '#ffffff', bordercolor: '#d1d5db', font: { color: '#111827' } },
  },
}

export default function Plot({ data, layout = {}, theme = 'admin', height = 320, config = {}, style }) {
  const t = THEMES[theme]
  const axis = (a = {}) => ({
    gridcolor: t.grid, zerolinecolor: t.zero, linecolor: t.grid, automargin: true,
    tickfont: { size: theme === 'admin' ? 11 : 12 }, ...a,
    title: a.title ? { text: typeof a.title === 'string' ? a.title : a.title.text, font: { size: 12 } } : undefined,
  })
  const merged = {
    autosize: true, height,
    margin: { l: 48, r: 16, t: layout.title ? 36 : 12, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: t.font, hoverlabel: t.hover,
    legend: { orientation: 'h', y: -0.18, font: { size: 11 } },
    ...layout,
    xaxis: axis(layout.xaxis), yaxis: axis(layout.yaxis),
    ...(layout.yaxis2 ? { yaxis2: axis(layout.yaxis2) } : {}),
  }
  if (layout.title) merged.title = { text: layout.title, font: { size: 14 }, x: 0, xanchor: 'left' }
  return (
    <PlotBase
      data={data}
      layout={merged}
      useResizeHandler
      style={{ width: '100%', ...style }}
      config={{ displaylogo: false, responsive: true, topojsonURL: '/topojson/', modeBarButtonsToRemove: ['lasso2d', 'select2d'], ...config }}
    />
  )
}
