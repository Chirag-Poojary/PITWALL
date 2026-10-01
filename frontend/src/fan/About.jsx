import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Flag, fmt, useApi } from '../components/common'
import { MEDIA, ytEmbed, ytWatch } from '../media'

function HeroVideo() {
  const [local, setLocal] = useState(null)
  useEffect(() => {
    fetch(MEDIA.heroLocalVideo, { method: 'HEAD' })
      .then((r) => setLocal(r.ok && (r.headers.get('content-type') || '').startsWith('video')))
      .catch(() => setLocal(false))
  }, [])
  if (local === null) return null
  if (local) return <video className="hero-media" src={MEDIA.heroLocalVideo} autoPlay muted loop playsInline />
  const id = MEDIA.heroYouTubeId
  return (
    <div className="hero-media hero-yt">
      <iframe title="Onboard lap" src={ytEmbed(id, `&autoplay=1&mute=1&controls=0&loop=1&playlist=${id}&playsinline=1&iv_load_policy=3&disablekb=1`)}
        allow="autoplay; encrypted-media" tabIndex={-1} />
    </div>
  )
}

const WEEKEND = [
  { tag: 'FRI', title: 'Practice', body: 'Up to three one-hour sessions (FP1–FP3) to dial in set-up, test tyres and learn the track. No points, but teams gather huge amounts of data.' },
  { tag: 'SAT', title: 'Qualifying', body: 'Three knockout rounds. The slowest cars drop out in Q1 and Q2; the top ten fight for pole position in Q3. The result sets the starting grid.' },
  { tag: 'SPRINT', title: 'Sprint weekends', body: 'At six events a year, a short Sprint Qualifying sets the grid for a ~100 km Sprint race on Saturday. The top eight score 8-7-6-5-4-3-2-1 points.' },
  { tag: 'SUN', title: 'Grand Prix', body: 'The main race: about 305 km (Monaco is shorter), two hours max. In the dry every car must use at least two tyre compounds, so pit strategy matters.' },
]

const POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

const FLAGS = [
  ['#16a34a', 'Green', 'Track is clear, racing resumes.'],
  ['#facc15', 'Yellow', 'Danger ahead: slow down, no overtaking. Double yellow: be ready to stop.'],
  ['#dc2626', 'Red', 'Session stopped. All cars return slowly to the pit lane.'],
  ['#2563eb', 'Blue', 'A faster car is about to lap you. Let it through.'],
  ['linear-gradient(135deg,#fff 50%,#111 50%)', 'Black & white', 'Warning for unsporting behaviour.'],
  ['#111', 'Black', 'Disqualified. Return to the pits.'],
  ['repeating-linear-gradient(90deg,#facc15 0 8px,#dc2626 8px 16px)', 'Yellow & red', 'Slippery surface: oil, water or debris.'],
  ['repeating-conic-gradient(#111 0 25%,#fff 0 50%) 0 0/14px 14px', 'Chequered', 'End of the session or race.'],
]

const GLOSSARY = [
  ['Pole position', 'First place on the starting grid, earned by the fastest qualifying lap.'],
  ['Undercut', 'Pitting before a rival so fresh tyres let you go faster and jump them when they stop.'],
  ['Overcut', 'Staying out longer than a rival, banking on clear air to gain time before your own stop.'],
  ['Safety Car / VSC', 'Neutralises the race after an incident. Cars bunch up behind it (or slow to a set delta under a Virtual Safety Car).'],
  ['DRS → active aero', 'From 2011 to 2025, a flap in the rear wing opened to help overtaking. From 2026 the cars use active aerodynamics and an electrical boost for attacking.'],
  ['Parc fermé', 'After qualifying, cars are locked down: teams can barely touch the set-up before the race.'],
  ['Power unit', 'The hybrid engine: a 1.6-litre turbo V6 plus electric motor-generator and battery.'],
  ['Dirty air', 'Turbulent air behind a car that robs the follower of downforce and makes close racing harder.'],
  ['DNF', 'Did Not Finish: a retirement because of a crash, mechanical failure or other problem.'],
  ['Box, box', 'Radio call telling the driver to come into the pits this lap.'],
]

const HISTORY = [
  ['1950', 'First World Championship race at Silverstone, Britain. Giuseppe Farina becomes the first champion.'],
  ['1958', 'The Constructors’ Championship is introduced; Vanwall win the first title.'],
  ['1977', 'Renault brings turbocharging; the turbo era peaks in the mid-1980s.'],
  ['1994', 'A dark weekend at Imola transforms safety standards across the sport.'],
  ['2014', 'The hybrid era begins with 1.6-litre V6 turbo power units.'],
  ['2018', 'The Halo cockpit protection becomes mandatory.'],
  ['2022', 'Ground-effect aerodynamics return to make following cars easier.'],
  ['2026', 'New rules: about half the power is electric, fuels are fully sustainable and active aero arrives. The grid grows to 11 teams.'],
]

export default function About() {
  const meta = useApi('/meta')
  const champs = useApi('/drivers', { champions: true, sort: 'titles', limit: 8 })
  const teams = useApi('/constructors', { champions: true, sort: 'titles', limit: 6 })
  const c = meta.data?.counts

  return (
    <div className="about">
      <section className="hero">
        <HeroVideo />
        <div className="hero-shade" />
        <div className="wrap hero-inner">
          <p className="eyebrow">The pinnacle of motorsport</p>
          <h1 className="hero-title">Formula 1,<br /><em>decoded.</em></h1>
          <p className="hero-sub">Twenty-odd drivers, eleven teams, one world title. Here is how the sport works, who made its history, and what to watch next.</p>
          <div className="hero-cta">
            <Link to="/drivers" className="btn btn-red">Explore drivers</Link>
            <Link to="/profile" className="btn btn-ghost">Build my feed</Link>
          </div>
        </div>
        <div className="hero-stats wrap">
          {[['Seasons', meta.data?.seasons?.length], ['Grands Prix', c?.races], ['Drivers', c?.drivers], ['Constructors', c?.constructors], ['Circuits', c?.circuits]]
            .map(([l, v]) => <div key={l}><b>{v ? fmt.int(v) : '–'}</b><span>{l}</span></div>)}
        </div>
      </section>

      <section className="wrap section two-col">
        <div>
          <p className="eyebrow">What is Formula 1?</p>
          <h2 className="section-title">The world’s fastest road-racing championship</h2>
          <p className="lead">Formula 1 is the top class of single-seater racing, run by the FIA since 1950. Each season is a world tour of Grands Prix on purpose-built tracks and closed city streets.</p>
          <p>Every team designs and builds its own car, so the championship is both a driving contest and an engineering race. Two titles are decided each year: the <b>Drivers’ Championship</b> for the individual with the most points, and the <b>Constructors’ Championship</b> for the team whose two cars score the most combined.</p>
        </div>
        <div className="pillars">
          <div className="pillar"><span>01</span><h4>Drivers’ title</h4><p>The best driver over around 24 races wins the World Championship.</p></div>
          <div className="pillar"><span>02</span><h4>Constructors’ title</h4><p>Both cars’ points count. It decides the prize money split between teams.</p></div>
          <div className="pillar"><span>03</span><h4>Global calendar</h4><p>Races across five continents, from March to December.</p></div>
        </div>
      </section>

      <section className="band">
        <div className="wrap section">
          <p className="eyebrow">Race weekend</p>
          <h2 className="section-title">Three days, four kinds of session</h2>
          <div className="weekend">
            {WEEKEND.map((w) => (
              <article key={w.title} className="weekend-card">
                <span className="weekend-tag">{w.tag}</span>
                <h3>{w.title}</h3>
                <p>{w.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="wrap section two-col">
        <div>
          <p className="eyebrow">Scoring</p>
          <h2 className="section-title">How points are awarded</h2>
          <p>The top ten in every Grand Prix score points. Ties in the championship are broken by number of wins, then second places, and so on. Between 2019 and 2024 a bonus point also went to the driver who set the fastest lap, if they finished in the top ten.</p>
        </div>
        <div className="points-grid">
          {POINTS.map((p, i) => (
            <div key={i} className={`points-cell ${i < 3 ? 'podium' : ''}`}><span>P{i + 1}</span><b>{p}</b></div>
          ))}
        </div>
      </section>

      <section className="band band-car">
        <div className="wrap section two-col car-col">
          <div>
            <p className="eyebrow">The machine</p>
            <h2 className="section-title">What is inside an F1 car?</h2>
            <p>A modern F1 car is a carbon-fibre monocoque wrapped around the driver, built from thousands of parts and redesigned every year.</p>
            <ul className="spec-list">
              <li><b>Power unit</b><span>1.6 L V6 turbo hybrid. From 2026 about half its power is electric and it runs on fully sustainable fuel.</span></li>
              <li><b>Top speed</b><span>Around 350 km/h, with cornering forces up to about 5 g.</span></li>
              <li><b>Aerodynamics</b><span>Wings and an underfloor that suck the car to the track (downforce).</span></li>
              <li><b>Tyres</b><span>18-inch slicks in several compounds, plus intermediate and full-wet tyres for rain.</span></li>
              <li><b>Safety</b><span>Halo cockpit protection, a survival cell and energy-absorbing crash structures.</span></li>
            </ul>
            <a className="btn btn-ghost" href={ytWatch(MEDIA.carVideoAltId)} target="_blank" rel="noreferrer">Watch: How It’s Made, F1 cars ↗</a>
          </div>
          <div className="video-frame">
            <iframe title="How a Formula 1 car is made" src={ytEmbed(MEDIA.carVideoId)} allowFullScreen
              allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" loading="lazy" />
            <p className="caption">Video: <i>How A Formula 1 Car is Made</i> on YouTube. <a href={ytWatch(MEDIA.carVideoId)} target="_blank" rel="noreferrer">Open on YouTube ↗</a></p>
          </div>
        </div>
      </section>

      <section className="wrap section">
        <p className="eyebrow">Hall of fame</p>
        <h2 className="section-title">Most successful champions</h2>
        <div className="champs">
          {champs.data?.items.map((d) => (
            <Link key={d.driverId} to={`/drivers/${d.driverId}`} className="champ">
              <span className="champ-titles">{d.titles}<small>×</small></span>
              <span className="champ-name"><Flag nationality={d.nationality} /> {d.name}</span>
              <span className="champ-meta">{d.wins} wins · {d.first_season}–{d.last_season}</span>
            </Link>
          ))}
        </div>
        <div className="champs champs-teams">
          {teams.data?.items.map((t) => (
            <Link key={t.constructorId} to={`/constructors/${t.constructorId}`} className="champ team">
              <span className="champ-titles">{t.titles}<small>×</small></span>
              <span className="champ-name"><Flag nationality={t.nationality} /> {t.name}</span>
              <span className="champ-meta">{t.wins} wins · Constructors’ titles</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="band">
        <div className="wrap section two-col">
          <div>
            <p className="eyebrow">Signals</p>
            <h2 className="section-title">Flags you will see</h2>
            <div className="flags">
              {FLAGS.map(([bg, name, desc]) => (
                <div key={name} className="flag-row"><span className="flag-chip" style={{ background: bg }} /><div><b>{name}</b><p>{desc}</p></div></div>
              ))}
            </div>
          </div>
          <div>
            <p className="eyebrow">Paddock talk</p>
            <h2 className="section-title">Ten terms to know</h2>
            <dl className="glossary">
              {GLOSSARY.map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}
            </dl>
          </div>
        </div>
      </section>

      <section className="wrap section">
        <p className="eyebrow">75 years in 8 moments</p>
        <h2 className="section-title">A very short history</h2>
        <ol className="timeline">
          {HISTORY.map(([y, t]) => <li key={y}><b>{y}</b><p>{t}</p></li>)}
        </ol>
        <div className="cta-band">
          <div><h3>Ready to pick your side?</h3><p>Choose favourite drivers, teams and the Grands Prix you follow. Your feed fills with their next sessions and standings.</p></div>
          <Link to="/profile" className="btn btn-red">Set up my feed</Link>
        </div>
      </section>
    </div>
  )
}
