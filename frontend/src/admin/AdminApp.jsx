import { useMemo, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { ErrorBox, Loader, useApi } from '../components/common'
import { AdminCtx } from './ui'
import Overview from './pages/Overview'
import DriversCompare from './pages/DriversCompare'
import ConstructorsCompare from './pages/ConstructorsCompare'
import RaceAnalysis from './pages/RaceAnalysis'
import Qualifying from './pages/Qualifying'
import PitStops from './pages/PitStops'
import Reliability from './pages/Reliability'
import Circuits from './pages/Circuits'
import ModelPoints from './pages/ModelPoints'
import ModelWinner from './pages/ModelWinner'
import ModelRegression from './pages/ModelRegression'
import ModelClustering from './pages/ModelClustering'

const NAV = [
  ['Analysis', [
    ['overview', 'Overview'], ['drivers', 'Driver comparison'], ['constructors', 'Constructor comparison'],
    ['race', 'Race analysis'], ['qualifying', 'Qualifying'], ['pitstops', 'Pit stops'], ['reliability', 'Reliability'], ['circuits', 'Circuits'],
  ]],
  ['Models', [
    ['models/points', 'Points-finish classifier'], ['models/winner', 'Race-winner classifier'],
    ['models/regression', 'Lap-speed regression'], ['models/clustering', 'Driver clustering'],
  ]],
]
// pages that do not use the global season range
const NO_RANGE = ['race', 'models/points', 'models/winner', 'models/regression']

export default function AdminApp() {
  const { user, signOut } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const filters = useApi('/admin/filters')
  const [range, setRange] = useState({ from: 2014, to: 2024 })
  const [collapsed, setCollapsed] = useState(false)
  const sub = loc.pathname.replace(/^\/admin\/?/, '')
  const showRange = !NO_RANGE.some((p) => sub.startsWith(p))
  const ctx = useMemo(() => ({ range, setRange, filters: filters.data }), [range, filters.data])

  return (
    <div className={`admin-root a-shell ${collapsed ? 'collapsed' : ''}`}>
      <aside className="a-side">
        <div className="a-logo"><span className="a-logo-mark" />PITWALL <em>Analyst</em></div>
        {NAV.map(([group, items]) => (
          <nav key={group}>
            <h6>{group}</h6>
            {items.map(([to, label]) => <NavLink key={to} to={`/admin/${to}`}>{label}</NavLink>)}
          </nav>
        ))}
        <div className="a-side-foot">
          <span>{user?.name}</span>
          <small>{user?.email}</small>
          <button className="a-btn ghost sm" onClick={() => { signOut(); nav('/admin/login') }}>Sign out</button>
        </div>
      </aside>
      <div className="a-main">
        <div className="a-topbar">
          <button className="a-icon-btn" onClick={() => setCollapsed(!collapsed)} aria-label="Toggle sidebar">☰</button>
          {showRange && filters.data && (
            <div className="a-range">
              <span>Seasons</span>
              <select value={range.from} onChange={(e) => setRange({ ...range, from: +e.target.value })}>
                {filters.data.seasons.map((y) => <option key={y} disabled={y > range.to}>{y}</option>)}
              </select>
              <span>to</span>
              <select value={range.to} onChange={(e) => setRange({ ...range, to: +e.target.value })}>
                {filters.data.seasons.map((y) => <option key={y} disabled={y < range.from}>{y}</option>)}
              </select>
              <div className="a-presets">
                {[['Hybrid era', 2014, 2024], ['Ground effect', 2022, 2024], ['2010s', 2010, 2019], ['All time', 1950, 2024]].map(([l, f, t]) => (
                  <button key={l} className={range.from === f && range.to === t ? 'on' : ''} onClick={() => setRange({ from: f, to: t })}>{l}</button>
                ))}
              </div>
            </div>
          )}
          <span className="a-topbar-note">Data: 1950–2024 · Ergast/Jolpica</span>
        </div>
        <div className="a-content">
          {filters.loading ? <Loader /> : filters.error ? <ErrorBox error={filters.error} /> : (
            <AdminCtx.Provider value={ctx}>
              <Routes>
                <Route index element={<Navigate to="overview" replace />} />
                <Route path="overview" element={<Overview />} />
                <Route path="drivers" element={<DriversCompare />} />
                <Route path="constructors" element={<ConstructorsCompare />} />
                <Route path="race" element={<RaceAnalysis />} />
                <Route path="qualifying" element={<Qualifying />} />
                <Route path="pitstops" element={<PitStops />} />
                <Route path="reliability" element={<Reliability />} />
                <Route path="circuits" element={<Circuits />} />
                <Route path="models/points" element={<ModelPoints />} />
                <Route path="models/winner" element={<ModelWinner />} />
                <Route path="models/regression" element={<ModelRegression />} />
                <Route path="models/clustering" element={<ModelClustering />} />
                <Route path="*" element={<Navigate to="overview" replace />} />
              </Routes>
            </AdminCtx.Provider>
          )}
        </div>
      </div>
    </div>
  )
}
