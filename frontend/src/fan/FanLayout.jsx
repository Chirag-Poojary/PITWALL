import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { Brand } from './AuthShell'

const LINKS = [
  ['/about', 'About F1'],
  ['/drivers', 'Drivers'],
  ['/constructors', 'Constructors'],
  ['/feed', 'My Feed'],
]

export default function FanLayout() {
  const { user, signOut } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [menu, setMenu] = useState(false)
  useEffect(() => { setOpen(false); setMenu(false); window.scrollTo(0, 0) }, [loc.pathname])
  const initials = user?.name?.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()

  return (
    <div className="fan-root">
      <header className="topnav">
        <div className="topnav-inner">
          <NavLink to="/about" className="topnav-brand"><Brand small /></NavLink>
          <nav className={`topnav-links ${open ? 'open' : ''}`}>
            {LINKS.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
          </nav>
          <div className="topnav-right">
            <button className="avatar-btn" onClick={() => setMenu(!menu)} aria-label="Account menu">
              {user?.avatar ? <img src={user.avatar} alt="" referrerPolicy="no-referrer" /> : <span>{initials}</span>}
            </button>
            {menu && (
              <div className="menu" onMouseLeave={() => setMenu(false)}>
                <div className="menu-head"><b>{user?.name}</b><span>{user?.email}</span></div>
                <button onClick={() => nav('/profile')}>Profile & preferences</button>
                <button onClick={() => nav('/feed')}>My feed</button>
                <button onClick={() => { signOut(); nav('/login') }}>Sign out</button>
              </div>
            )}
            <button className="burger" onClick={() => setOpen(!open)} aria-label="Menu"><span /><span /><span /></button>
          </div>
        </div>
      </header>
      <Outlet />
      <footer className="fan-footer">
        <div className="wrap footer-inner">
          <Brand small />
          <p>Fan-made project. Historical data 1950–2024 (Ergast/Jolpica dataset); live season data from the Jolpica-F1 API.
            Not affiliated with Formula 1, the FIA or any team.</p>
        </div>
      </footer>
    </div>
  )
}
