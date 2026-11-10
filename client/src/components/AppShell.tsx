import { NavLink, Outlet } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../auth/useAuth'

type NavItem = { to: string; label: string; icon: ReactNode }

const svgProps = {
  width: 20,
  height: 20,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
}

const BASE_NAV: NavItem[] = [
  {
    to: '/leads',
    label: 'Leads',
    icon: (
      <svg {...svgProps}>
        <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
      </svg>
    ),
  },
  {
    to: '/listings',
    label: 'Listings',
    icon: (
      <svg {...svgProps}>
        <path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16" />
        <path d="M14 10h5a1 1 0 0 1 1 1v10" />
        <path d="M8 8h2M8 12h2M8 16h2M3 21h18" />
      </svg>
    ),
  },
  {
    to: '/reports',
    label: 'Visits & reports',
    icon: (
      <svg {...svgProps}>
        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      </svg>
    ),
  },
]

const TEAM_NAV: NavItem = {
  to: '/team',
  label: 'Team',
  icon: (
    <svg {...svgProps}>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
      <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.2a6.5 6.5 0 0 1 3.5 5.8" />
    </svg>
  ),
}

const ROLE_LABEL: Record<string, string> = {
  salesperson: 'Salesperson',
  admin: 'Admin',
  owner: 'Owner',
}

export default function AppShell() {
  const { user, logout } = useAuth()
  const isAdmin = user?.role === 'admin' || user?.role === 'owner'
  const nav = isAdmin ? [...BASE_NAV, TEAM_NAV] : BASE_NAV

  return (
    <div className="flex h-full bg-charcoal-50">
      <aside className="hidden w-60 shrink-0 flex-col bg-charcoal-950 md:flex">
        <div className="flex h-14 items-center px-5 text-xl font-semibold text-white">
          Ghar<span className="text-brand-500">mind</span>
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1 px-3 py-2">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex h-10 items-center gap-3 rounded-md px-3 font-medium ${
                  isActive ? 'bg-charcoal-800 text-brand-500' : 'text-charcoal-200 hover:bg-charcoal-800'
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between bg-charcoal-950 px-4 text-white">
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold md:hidden">
              Ghar<span className="text-brand-500">mind</span>
            </span>
            <span className="hidden text-charcoal-200 md:inline">{user?.tenant_name ?? ''}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right leading-tight sm:block">
              <div className="font-medium">{user?.name}</div>
              <div className="text-xs text-charcoal-400">{user ? ROLE_LABEL[user.role] ?? user.role : ''}</div>
            </div>
            <button
              type="button"
              onClick={logout}
              className="h-10 rounded-md border border-charcoal-600 px-3 font-medium text-white hover:bg-charcoal-800"
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-auto pb-16 md:pb-0">
          <div className="mx-auto max-w-[1280px] p-4 md:p-6">
            <Outlet />
          </div>
        </main>

        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 flex border-t border-charcoal-600 bg-charcoal-950 md:hidden"
        >
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex min-h-14 flex-1 flex-col items-center justify-center gap-1 text-xs font-medium ${
                  isActive ? 'text-brand-500' : 'text-charcoal-200'
                }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}