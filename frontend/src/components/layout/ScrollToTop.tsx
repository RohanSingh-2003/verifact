import { useEffect, useRef } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'

/**
 * Global scroll-to-top handler across all client-side routes.
 *
 * Resets window and document scroll positions on normal internal navigations
 * (PUSH or REPLACE) and initial page loads, while preserving native browser
 * scroll restoration on Back / Forward navigation (POP).
 */
export function ScrollToTop() {
  const { pathname, hash } = useLocation()
  const navigationType = useNavigationType()
  const prevPathname = useRef<string | null>(null)

  useEffect(() => {
    const isRouteChange = prevPathname.current !== null && prevPathname.current !== pathname
    prevPathname.current = pathname

    // Preserve browser's native scroll restoration on Back/Forward navigation
    if (navigationType === 'POP' && isRouteChange) {
      return
    }

    // If an anchor hash exists (e.g. #section), scroll to that element if present
    if (hash) {
      const id = hash.replace('#', '')
      const element = document.getElementById(id)
      if (element) {
        element.scrollIntoView()
        return
      }
    }

    // Scroll window/document to the top
    if (typeof window !== 'undefined') {
      try {
        window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
      } catch {
        window.scrollTo(0, 0)
      }
    }

    if (typeof document !== 'undefined') {
      if (document.documentElement) {
        document.documentElement.scrollTop = 0
      }
      if (document.body) {
        document.body.scrollTop = 0
      }

      // Reset any dedicated layout or scroll containers if present
      const containers = document.querySelectorAll<HTMLElement>(
        '[data-scroll-container], main, #main-content',
      )
      containers.forEach((container) => {
        container.scrollTop = 0
      })
    }
  }, [pathname, hash, navigationType])

  return null
}
