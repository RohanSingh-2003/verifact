import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { MemoryRouter, Route, Routes, Link, useNavigate } from 'react-router-dom'
import { ScrollToTop } from './ScrollToTop'
import { useState } from 'react'

describe('ScrollToTop', () => {
  let scrollToSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    scrollToSpy = vi.fn()
    window.scrollTo = scrollToSpy as unknown as typeof window.scrollTo
    document.documentElement.scrollTop = 500
    document.body.scrollTop = 500
  })

  function TestApp({ initialEntries = ['/'] }: { initialEntries?: string[] }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <ScrollToTop />
        <nav>
          <Link to="/">Detect</Link>
          <Link to="/metaqa">MetaQA</Link>
          <Link to="/web-analysis">Web Analysis</Link>
          <Link to="/history">History</Link>
          <Link to="/settings">Settings</Link>
          <Link to="/metaqa#overview">MetaQA Anchor</Link>
        </nav>
        <Routes>
          <Route path="/" element={<TestPage title="Detect Page" />} />
          <Route path="/metaqa" element={<TestPage title="MetaQA Page" hasAnchor />} />
          <Route path="/web-analysis" element={<TestPage title="Web Analysis Page" />} />
          <Route path="/history" element={<TestPage title="History Page" />} />
          <Route path="/settings" element={<TestPage title="Settings Page" />} />
        </Routes>
      </MemoryRouter>
    )
  }

  function TestPage({ title, hasAnchor = false }: { title: string; hasAnchor?: boolean }) {
    const [counter, setCounter] = useState(0)
    const navigate = useNavigate()

    return (
      <main id="main-content">
        <h1>{title}</h1>
        <button onClick={() => setCounter((c) => c + 1)}>Re-render Counter: {counter}</button>
        <button onClick={() => navigate(-1)}>Go Back</button>
        {hasAnchor && <div id="overview">Overview Section</div>}
      </main>
    )
  }

  it('scrolls to top on initial page mount (PUSH/REPLACE)', () => {
    render(<TestApp initialEntries={['/']} />)

    expect(scrollToSpy).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })
    expect(document.documentElement.scrollTop).toBe(0)
    expect(document.body.scrollTop).toBe(0)
  })

  it('scrolls to top when navigating to another route via link', () => {
    render(<TestApp initialEntries={['/']} />)

    scrollToSpy.mockClear()
    document.documentElement.scrollTop = 400

    // Click link to MetaQA
    act(() => {
      screen.getByText('MetaQA').click()
    })

    expect(screen.getByText('MetaQA Page')).toBeDefined()
    expect(scrollToSpy).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })
    expect(document.documentElement.scrollTop).toBe(0)

    scrollToSpy.mockClear()

    // Click link to Web Analysis
    act(() => {
      screen.getByText('Web Analysis').click()
    })

    expect(screen.getByText('Web Analysis Page')).toBeDefined()
    expect(scrollToSpy).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })

    scrollToSpy.mockClear()

    // Click link to History
    act(() => {
      screen.getByText('History').click()
    })

    expect(screen.getByText('History Page')).toBeDefined()
    expect(scrollToSpy).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })
    scrollToSpy.mockClear()

    // Click link to Settings
    act(() => {
      screen.getByText('Settings').click()
    })

    expect(screen.getByText('Settings Page')).toBeDefined()
    expect(scrollToSpy).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })

    scrollToSpy.mockClear()

    // Click link back to Detect
    act(() => {
      screen.getByText('Detect').click()
    })

    expect(screen.getByText('Detect Page')).toBeDefined()
    expect(scrollToSpy).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })
  })

  it('resets scroll container element if layout uses dedicated scroll container', () => {
    render(<TestApp initialEntries={['/']} />)

    const mainContainer = document.getElementById('main-content')
    expect(mainContainer).toBeDefined()
    if (mainContainer) {
      mainContainer.scrollTop = 300
    }

    scrollToSpy.mockClear()

    act(() => {
      screen.getByText('Settings').click()
    })

    if (mainContainer) {
      expect(mainContainer.scrollTop).toBe(0)
    }
  })

  it('does NOT reset scroll position during same-route state updates or re-renders', () => {
    render(<TestApp initialEntries={['/']} />)

    scrollToSpy.mockClear()
    document.documentElement.scrollTop = 350

    // Simulate user state change (e.g. typing in form, loading updates, counter increment)
    act(() => {
      screen.getByText(/Re-render Counter/i).click()
    })

    expect(screen.getByText('Re-render Counter: 1')).toBeDefined()
    // scrollTo should NOT be called again on same route re-render
    expect(scrollToSpy).not.toHaveBeenCalled()
  })

  it('does NOT override native scroll restoration on POP (Back/Forward) navigation', () => {
    render(<TestApp initialEntries={['/', '/metaqa']} />)

    // Clear calls from mounting on /metaqa
    scrollToSpy.mockClear()

    // Click Go Back button (triggers navigate(-1) -> POP navigation)
    act(() => {
      screen.getByText('Go Back').click()
    })

    expect(screen.getByText('Detect Page')).toBeDefined()
    // For POP navigation, scrollTo is not called, allowing native scroll restoration
    expect(scrollToSpy).not.toHaveBeenCalled()
  })

  it('scrolls to element when anchor hash is specified and matching element exists', () => {
    const scrollIntoViewSpy = vi.fn()
    HTMLElement.prototype.scrollIntoView = scrollIntoViewSpy

    render(<TestApp initialEntries={['/']} />)
    scrollToSpy.mockClear()

    act(() => {
      screen.getByText('MetaQA Anchor').click()
    })

    expect(screen.getByText('Overview Section')).toBeDefined()
    expect(scrollIntoViewSpy).toHaveBeenCalled()
    expect(scrollToSpy).not.toHaveBeenCalled()
  })
})
