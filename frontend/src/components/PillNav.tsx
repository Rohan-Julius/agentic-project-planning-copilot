import { Link, useLocation } from 'react-router-dom'
import logo from '../assets/logo-mark.png'

interface PillNavItem {
  label: string
  to: string
  /** Whether this item counts as "active" for any path other than an exact match — used
   * for "Projects", which should stay lit across every /projects/* sub-page, not just "/".
   * Each item's own explicit check (not a catch-all "anything else" fallback) so a new route
   * can't silently light up the wrong tab — see the "Standards" gap this replaced. */
  isActive: (pathname: string) => boolean
}

const ITEMS: PillNavItem[] = [
  {
    label: 'Projects',
    to: '/',
    isActive: (pathname) => pathname === '/' || pathname.startsWith('/projects'),
  },
  { label: 'Standards', to: '/standards', isActive: (pathname) => pathname === '/standards' },
  { label: 'About', to: '/about', isActive: (pathname) => pathname === '/about' },
]

/** Site-wide primary nav. Ported from a reference "PillNav" component's visual language
 * (circular logo mark, pill items, a fill that rises from the bottom on hover/active) —
 * not its implementation. The reference uses gsap and per-pill DOM measurements to size an
 * exact circle for that fill; here it's a fixed, generously-oversized circle animated with
 * a plain CSS transition (see .pill-nav-fill in index.css), reusing the same gold-fill +
 * label-swap mechanic already built for .button-hover elsewhere in this app, instead of
 * inventing a third hover treatment or adding a new animation dependency for one nav bar. */
export default function PillNav() {
  const { pathname } = useLocation()

  return (
    <nav className="pill-nav" aria-label="Primary">
      <Link to="/" className="pill-nav-logo" aria-label="Planning Copilot, go to projects">
        <img src={logo} alt="" width={32} height={32} />
      </Link>
      <ul className="pill-nav-list" role="menubar">
        {ITEMS.map((item) => {
          const active = item.isActive(pathname)
          return (
            <li key={item.to} role="none">
              <Link
                to={item.to}
                role="menuitem"
                className={`pill-nav-item${active ? ' is-active' : ''}`}
              >
                <span className="pill-nav-fill" aria-hidden="true" />
                <span className="pill-nav-label-stack">
                  <span className="pill-nav-label">{item.label}</span>
                  <span className="pill-nav-label pill-nav-label-hover" aria-hidden="true">
                    {item.label}
                  </span>
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
