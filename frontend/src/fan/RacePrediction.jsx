import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loader } from '../components/common'
import { teamColor } from '../teams'

const pct = (v) => (v >= 0.995 ? '99%' : v < 0.005 ? '<1%' : `${Math.round(v * 100)}%`)

function usePrediction(race) {
  const [state, setState] = useState({ data: null, error: null, training: false })
  const params = race ? { season: race.season, round: race.round } : undefined
  const key = race ? `${race.season}-${race.round}` : 'next'
  useEffect(() => {
    let alive = true
    let timer
    const load = () => api('/predictions/race', { params })
      .then((data) => alive && setState({ data, error: null, training: false }))
      .catch((e) => {
        if (!alive) return
        if (e.status === 503) { setState({ data: null, error: null, training: true }); timer = setTimeout(load, 4000) } else setState({ data: null, error: e, training: false })
      })
    load()
    return () => { alive = false; clearTimeout(timer) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return state
}

function Step({ p, place, fav }) {
  return (
    <div className={`pred-step place-${place} ${fav ? 'fav' : ''}`} style={{ '--team': teamColor(p.team) }}>
      <div className="pred-driver">
        <span className="pred-code">{p.code || p.name.split(' ').pop().slice(0, 3).toUpperCase()}</span>
        <b>{p.name}</b>
        <small>{p.team}{p.grid ? ` · starts P${p.grid}` : ''}</small>
      </div>
      <div className="pred-block">
        <span className="pred-place">P{place}</span>
        <strong>{pct(p.p_win)}</strong>
        <small>to win</small>
        <em>{pct(p.p_podium)} podium</em>
      </div>
    </div>
  )
}

export default function RacePrediction({ race, favDrivers = [] }) {
  const { data, error, training } = usePrediction(race)
  const fav = new Set(favDrivers)
  if (training) return <section className="panel prediction"><Loader label="The prediction model is warming up" /></section>
  if (error) return null
  if (!data) return <section className="panel prediction"><Loader label="Running the race prediction" /></section>
  if (!data.available) return null
  const p = data.predictions
  const bt = data.model.backtest
  const back = data.mode === 'backtest'
  const max = p[0]?.p_win || 1

  return (
    <section className="panel prediction">
      <div className="pred-head">
        <div>
          <p className="eyebrow">{back ? 'Model back-test' : 'Race prediction'}</p>
          <h3 className="pred-title">{back ? `How the model called the ${data.race.season} ${data.race.name}` : `Who wins the ${data.race.name}?`}</h3>
        </div>
        <span className={`pill ${data.uses_qualifying ? 'red' : ''}`}>{back ? 'Past race' : data.uses_qualifying ? 'Using qualifying grid' : 'Before qualifying'}</span>
      </div>
      {data.reason && <p className="muted small">{data.reason}</p>}

      <div className="pred-podium">
        {p[1] && <Step p={p[1]} place={2} fav={fav.has(p[1].driver_ref)} />}
        {p[0] && <Step p={p[0]} place={1} fav={fav.has(p[0].driver_ref)} />}
        {p[2] && <Step p={p[2]} place={3} fav={fav.has(p[2].driver_ref)} />}
      </div>

      <ol className="pred-rest" start={4}>
        {p.slice(3, 10).map((r, i) => (
          <li key={r.driver_ref} className={fav.has(r.driver_ref) ? 'fav' : ''}>
            <span className="rank">{i + 4}</span>
            <b>{r.name}</b>
            <i className="bar"><i style={{ width: `${(r.p_win / max) * 100}%`, background: teamColor(r.team) }} /></i>
            <em>{pct(r.p_win)}</em>
            {back && <small className="muted">finished P{r.actual}</small>}
          </li>
        ))}
      </ol>

      {back && data.actual_winner && (
        <p className="pred-actual">Actual result: <b>{data.actual_winner}</b> won. The model's top three finished {p.slice(0, 3).map((r) => `P${r.actual}`).join(', ')}.</p>
      )}
      <p className="muted small pred-note">
        {data.model.name} trained on Grands Prix from 2000 to 2024{data.live_seasons?.length ? ` plus live ${data.live_seasons.join('–')} results` : ''}.
        {' '}Each driver is scored on recent form, team form and their record at this circuit{data.uses_qualifying ? ', plus their qualifying position' : ''}.
        {' '}On the {data.model.backtest_seasons} seasons, which the model never saw, its favourite won {pct(bt.favourite_won)} of races and the winner was in its top three {pct(bt.winner_in_top3)} of the time.
        {' '}A prediction, not a promise: crashes, rain and strategy are not in the data.
      </p>
    </section>
  )
}
