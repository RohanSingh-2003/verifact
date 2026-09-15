import { Link, NavLink } from 'react-router-dom'
import { BookOpen, FlaskConical, History, ScanSearch, Settings } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { classNames } from '../../lib/format'
import { getHealth } from '../../services/api'

const primaryNav = [
  { to: '/', label: 'Detect', icon: ScanSearch, end: true },
  { to: '/history', label: 'History', icon: History, end: false },
  { to: '/experiments', label: 'Experiments', icon: FlaskConical, end: false },
] as const

const secondaryNav = [
  { to: '/metaqa', label: 'MetaQA', icon: BookOpen },
  { to: '/settings', label: 'Settings', icon: Settings },
] as const

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      to="/"
      className={classNames('flex items-center gap-2.5', compact ? 'justify-center' : '')}
      aria-label="VeriFact home"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-canvas" aria-hidden="true">
        <svg viewBox="0 0 24 24" className="h-[18px] w-[18px]" fill="none">
          <path
            d="M12 3.5c-2.8 1.4-5 1.8-7 1.8v7.1c0 3.8 2.6 6.7 7 8.1 4.4-1.4 7-4.3 7-8.1V5.3c-2 0-4.2-.4-7-1.8z"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <path
            d="M8.6 12.2l2.2 2.2 4.6-4.8"
            stroke="#7eb9a6"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      {compact ? (
        <span className="sr-only">VeriFact</span>
      ) : (
        <span className="text-[15px] font-semibold tracking-tight text-ink">VeriFact</span>
      )}
    </Link>
  )
}

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  compact,
}: {
  to: string
  label: string
  icon: typeof ScanSearch
  end?: boolean
  compact?: boolean
}) {
  return (
    <NavLink
      to={to}
      end={end}
      title={compact ? label : undefined}
      className={({ isActive }) =>
        classNames(
          'flex items-center rounded-[var(--radius-sm)] text-sm font-medium transition-colors',
          compact ? 'justify-center px-0 py-2.5' : 'gap-2.5 px-2.5 py-2',
          isActive
            ? 'bg-surface-muted text-ink'
            : 'text-ink-secondary hover:bg-surface-muted/70 hover:text-ink',
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
      {compact ? <span className="sr-only">{label}</span> : label}
    </NavLink>
  )
}

export function Sidebar({ compact = false }: { compact?: boolean }) {
  return (
    <aside
      className={classNames(
        'sticky top-0 hidden h-dvh flex-col border-r border-line bg-surface md:flex',
        compact ? 'w-[72px] px-2 py-5' : 'w-[220px] px-3 py-5',
      )}
    >
      <div className={classNames('mb-8', compact ? 'px-0' : 'px-2')}>
        <Logo compact={compact} />
      </div>

      <nav className="flex flex-1 flex-col justify-between" aria-label="Primary">
        <div className="space-y-0.5">
          {primaryNav.map((item) => (
            <NavItem key={item.to} {...item} compact={compact} />
          ))}
        </div>
        <div className="space-y-0.5 border-t border-line pt-3">
          {secondaryNav.map((item) => (
            <NavItem key={item.to} {...item} compact={compact} />
          ))}
        </div>
      </nav>
    </aside>
  )
}

export function MobileTopBar() {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-canvas px-4 py-3 md:hidden">
      <Logo />
      <NavLink
        to="/settings"
        className="rounded-[var(--radius-sm)] p-2 text-ink-secondary hover:bg-surface-muted hover:text-ink"
        aria-label="Settings"
      >
        <Settings className="h-4 w-4" strokeWidth={1.75} />
      </NavLink>
    </header>
  )
}

export function MobileNav() {
  const items = [...primaryNav, secondaryNav[0]]

  return (
    <nav
      aria-label="Mobile"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] md:hidden"
    >
      <ul className="grid grid-cols-4 gap-1">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={'end' in item ? item.end : false}
                className={({ isActive }) =>
                  classNames(
                    'flex flex-col items-center gap-1 rounded-[var(--radius-sm)] px-2 py-1.5 text-[11px] font-medium',
                    isActive ? 'text-ink' : 'text-ink-muted',
                  )
                }
              >
                <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
                {item.label}
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<'unknown' | 'mock' | 'live'>('unknown')

  useEffect(() => {
    void getHealth()
      .then((health) => setMode(health.llm_mode === 'live' ? 'live' : 'mock'))
      .catch(() => setMode('unknown'))
  }, [])

  return (
    <div className="min-h-dvh md:flex">
      <div className="hidden lg:block">
        <Sidebar />
      </div>
      <div className="hidden md:block lg:hidden">
        <Sidebar compact />
      </div>
      <div className="min-w-0 flex-1">
        <MobileTopBar />
        <div className="mx-auto w-full max-w-[1120px] px-4 pt-6 pb-[calc(5.75rem+env(safe-area-inset-bottom))] sm:px-6 sm:pt-8 lg:px-10 lg:pt-10 lg:pb-12">
          {mode === 'mock' ? (
            <div
              role="status"
              className="mb-5 rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3 py-2 text-xs leading-5 text-ink-secondary"
            >
              Demo / Mock Mode — responses are deterministic development data, not live model output.
            </div>
          ) : null}
          {mode === 'live' ? (
            <div
              role="status"
              className="mb-5 rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3 py-2 text-xs leading-5 text-ink-secondary"
            >
              Live LLM Mode — answers and verifications use the configured provider. API keys stay on the server.
            </div>
          ) : null}
          {children}
        </div>
      </div>
      <MobileNav />
    </div>
  )
}
