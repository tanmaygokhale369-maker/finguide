import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import './Layout.css'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/profile', label: 'Financial Profile' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/chat', label: 'Chat' },
  { to: '/recommendations', label: 'Recommendations' },
  { to: '/investments', label: 'Investments' },
  { to: '/settings', label: 'Settings' },
  { to: '/auth', label: 'Sign in' },
]

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="app-shell">
      <header className="app-header">
        <NavLink className="app-brand" to="/" aria-label="FinGuide+ home">
          <span className="app-brand-mark" aria-hidden="true">F</span>
          <span>FinGuide<span className="app-brand-plus">+</span></span>
        </NavLink>
        <button
          className="app-menu-toggle"
          type="button"
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span /><span /><span />
        </button>
        <nav id="primary-navigation" className={`app-nav${menuOpen ? ' app-nav-open' : ''}`}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'app-nav-link active' : 'app-nav-link')}
              onClick={() => setMenuOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
