import { Link, Outlet } from 'react-router-dom'
import PillNav from './PillNav'
import ThemeToggle from './ThemeToggle'

export default function AppShell() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="topbar-brand" aria-label="Planning Copilot, go to projects">
            <span className="topbar-name">
              Planning <span className="aurora-text">Copilot</span>
            </span>
          </Link>
          <PillNav />
          <ThemeToggle />
        </div>
      </header>
      <Outlet />
    </div>
  )
}
