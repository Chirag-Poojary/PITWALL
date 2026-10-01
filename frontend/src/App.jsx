import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import { Loader } from './components/common'
import FanLayout from './fan/FanLayout'
import Login from './fan/Login'
import Register from './fan/Register'

const About = lazy(() => import('./fan/About'))
const Drivers = lazy(() => import('./fan/Drivers'))
const DriverDetail = lazy(() => import('./fan/DriverDetail'))
const Constructors = lazy(() => import('./fan/Constructors'))
const ConstructorDetail = lazy(() => import('./fan/ConstructorDetail'))
const Feed = lazy(() => import('./fan/Feed'))
const Profile = lazy(() => import('./fan/Profile'))
const AdminLogin = lazy(() => import('./admin/AdminLogin'))
const AdminApp = lazy(() => import('./admin/AdminApp'))

function RequireFan({ children }) {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return <div className="fan-root center-page"><Loader /></div>
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  if (user.role === 'admin') return <Navigate to="/admin" replace />
  return children
}

function RequireAdmin({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="admin-root center-page"><Loader /></div>
  if (!user || user.role !== 'admin') return <Navigate to="/admin/login" replace />
  return children
}

function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'admin' ? '/admin' : '/about'} replace />
}

export default function App() {
  return (
    <Suspense fallback={<div className="center-page"><Loader /></div>}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin/*" element={<RequireAdmin><AdminApp /></RequireAdmin>} />
        <Route element={<RequireFan><FanLayout /></RequireFan>}>
          <Route path="/about" element={<About />} />
          <Route path="/drivers" element={<Drivers />} />
          <Route path="/drivers/:id" element={<DriverDetail />} />
          <Route path="/constructors" element={<Constructors />} />
          <Route path="/constructors/:id" element={<ConstructorDetail />} />
          <Route path="/feed" element={<Feed />} />
          <Route path="/profile" element={<Profile />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
