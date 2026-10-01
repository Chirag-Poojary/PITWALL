import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

export function useApi(path, params, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const key = JSON.stringify([path, params])
  const seq = useRef(0)
  useEffect(() => {
    if (!path) { setState({ data: null, loading: false, error: null }); return }
    const my = ++seq.current
    setState((s) => ({ ...s, loading: true, error: null }))
    api(path, { params })
      .then((data) => my === seq.current && setState({ data, loading: false, error: null }))
      .catch((error) => my === seq.current && setState({ data: null, loading: false, error }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ...deps])
  return state
}

export function Loader({ label = 'Loading' }) {
  return <div className="loader"><span className="loader-bar" /><span>{label}…</span></div>
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="error-box">{error.message || String(error)}</div>
}

const NAT = {
  British: 'gb', German: 'de', Italian: 'it', French: 'fr', Brazilian: 'br', Finnish: 'fi', Spanish: 'es',
  Dutch: 'nl', Australian: 'au', American: 'us', Austrian: 'at', Belgian: 'be', Canadian: 'ca', Swiss: 'ch',
  Japanese: 'jp', Mexican: 'mx', Monegasque: 'mc', Danish: 'dk', Swedish: 'se', 'New Zealander': 'nz',
  Argentine: 'ar', Argentinian: 'ar', 'South African': 'za', Polish: 'pl', Russian: 'ru', Thai: 'th', Chinese: 'cn',
  Venezuelan: 've', Colombian: 'co', Indian: 'in', Irish: 'ie', Portuguese: 'pt', Hungarian: 'hu', Czech: 'cz',
  Indonesian: 'id', Malaysian: 'my', Chilean: 'cl', Uruguayan: 'uy', 'East German': 'de', Rhodesian: 'zw',
  'Hong Kong': 'hk', Liechtensteiner: 'li', Estonian: 'ee', Swedish_: 'se', Emirati: 'ae', Saudi: 'sa',
}
export function Flag({ nationality, size = 20 }) {
  const c = NAT[nationality]
  if (!c) return null
  return <img className="flag" src={`https://flagcdn.com/w40/${c}.png`} alt={nationality} title={nationality}
    width={size} height={Math.round(size * 0.7)} loading="lazy" />
}

export const fmt = {
  int: (v) => (v === null || v === undefined ? '–' : Math.round(v).toLocaleString()),
  num: (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? '–' : Number(v).toFixed(d)),
  pct: (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? '–' : `${(v * 100).toFixed(d)}%`),
  pts: (v) => (v === null || v === undefined ? '–' : Number.isInteger(v) ? v.toLocaleString() : Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 })),
}

export function localTime(iso, opts = {}) {
  if (!iso) return '–'
  return new Date(iso).toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', ...opts })
}

export function useCountdown(iso) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [])
  if (!iso) return null
  let ms = new Date(iso).getTime() - now
  if (ms < 0) return { past: true, d: 0, h: 0, m: 0, s: 0 }
  const d = Math.floor(ms / 864e5); ms -= d * 864e5
  const h = Math.floor(ms / 36e5); ms -= h * 36e5
  const m = Math.floor(ms / 6e4); ms -= m * 6e4
  return { past: false, d, h, m, s: Math.floor(ms / 1000) }
}
