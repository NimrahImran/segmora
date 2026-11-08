import { Component, lazy, Suspense, useEffect, type ReactNode } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Home from './pages/Home'

const Finder = lazy(() => import('./pages/Finder'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Personas = lazy(() => import('./pages/Personas'))
const About = lazy(() => import('./pages/About'))

export const Logo = () => (
  <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
    <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f3d2b0" /><stop offset="1" stopColor="#a9683c" /></linearGradient></defs>
    <circle cx="20" cy="20" r="19" fill="#3a1a0e" stroke="url(#lg)" strokeWidth="1.5" />
    <path d="M20 1a19 19 0 0 1 0 38a9.5 9.5 0 0 1 0-19a9.5 9.5 0 0 0 0-19z" fill="url(#lg)" />
  </svg>
)

class PageBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (!this.state.failed) return this.props.children
    return <div className="page"><h1>This page hit a problem.</h1><p className="muted">Reload to continue.</p><p><button className="primary small" onClick={() => location.reload()}>Reload page</button></p></div>
  }
}

const LINKS = [['/', 'Home'], ['/finder', 'Segment Finder'], ['/analytics', 'Analytics'], ['/personas', 'AI Persona'], ['/about', 'About']]

export default function App() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return (
    <>
      <nav className="nav" aria-label="Main">
        <Link className="brand" to="/"><Logo />Segmora</Link>
        <div className="links">{LINKS.map(([to, label]) => <NavLink key={to} to={to} end={to === '/'} aria-label={label}>{label === 'Segment Finder' ? <><span className="long">Segment </span>Finder</> : label}</NavLink>)}</div>
        <Link className="launch" to="/finder">Find a segment</Link>
      </nav>
      <PageBoundary><Suspense fallback={<div className="page"><p className="muted">Loading</p></div>}>
        <Routes>
          <Route path="/" element={<Home />} /><Route path="/finder" element={<Finder />} />
          <Route path="/analytics" element={<Analytics />} /><Route path="/personas" element={<Personas />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<div className="page"><h1>This page does not exist.</h1><p><Link className="primary" to="/">Go home</Link></p></div>} />
        </Routes>
      </Suspense></PageBoundary>
      <footer className="foot"><span>Segmora</span><a href="/#hire">Hire me</a><span>Built by Nimra Imran</span></footer>
    </>
  )
}
