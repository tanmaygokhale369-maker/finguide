import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import App from './App'

afterEach(() => {
  window.history.pushState({}, '', '/')
})

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ status: 'ok', app_name: 'FinGuide+', environment: 'test' }),
      }),
    ),
  )
})

describe('App routing', () => {
  it('renders the Dashboard at the root route by default', async () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/Backend status:/)).toBeInTheDocument())
  })

  it('navigates to Transactions when the nav link is clicked', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Transactions' }))
    expect(await screen.findByRole('heading', { name: 'Transactions' })).toBeInTheDocument()
  })

  it('navigates to Financial Profile when the nav link is clicked', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('link', { name: 'Financial Profile' }))
    expect(await screen.findByRole('heading', { name: 'Financial Profile' })).toBeInTheDocument()
  })

  it('shows the not-found page for an unknown route', async () => {
    window.history.pushState({}, '', '/does-not-exist')
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it('shows an error state on the Dashboard when the health check fails', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('network down'))))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach the FinGuide+ backend.')
  })
})
