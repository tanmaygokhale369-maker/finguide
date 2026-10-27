import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { FinancialProfile } from './FinancialProfile'
import { ApiError } from '../api/client'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual('../api/client')
  return {
    ...actual,
    getProfile: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: vi.fn(),
    getProfileMetrics: vi.fn(),
  }
})

import { getProfile, createProfile, getProfileMetrics } from '../api/client'

function labelInput(labelText) {
  return screen.getByText(labelText).closest('label').querySelector('input, select, textarea')
}

describe('FinancialProfile page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "Create profile" when no profile exists yet (404)', async () => {
    getProfile.mockRejectedValue(new ApiError('not found', { status: 404 }))
    render(<FinancialProfile />)
    expect(await screen.findByRole('button', { name: 'Create profile' })).toBeInTheDocument()
    // A 404 is the correct "no profile yet" state, not an error banner.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a real error state when the profile fetch fails for another reason', async () => {
    getProfile.mockRejectedValue(new ApiError('server exploded', { status: 500 }))
    render(<FinancialProfile />)
    expect(await screen.findByRole('alert')).toHaveTextContent('server exploded')
  })

  it('prefills the form and shows "Save changes" when a profile already exists', async () => {
    getProfile.mockResolvedValue({
      monthly_income: '60000.00',
      fixed_expenses: '20000.00',
      variable_expenses: null,
      savings: null,
      debt: null,
      emergency_fund_amount: null,
      dependents: null,
      has_insurance: null,
      existing_investments_amount: null,
      risk_preference: null,
      investment_horizon_years: null,
      financial_goals: null,
    })
    render(<FinancialProfile />)
    expect(await screen.findByRole('button', { name: 'Save changes' })).toBeInTheDocument()
    expect(labelInput('Monthly income').value).toBe('60000.00')
  })

  it('creates a profile, recomputes metrics, and shows the saved note', async () => {
    getProfile.mockRejectedValue(new ApiError('not found', { status: 404 }))
    createProfile.mockResolvedValue({
      monthly_income: '60000',
      fixed_expenses: null,
      variable_expenses: null,
      savings: null,
      debt: null,
      emergency_fund_amount: null,
      dependents: null,
      has_insurance: null,
      existing_investments_amount: null,
      risk_preference: null,
      investment_horizon_years: null,
      financial_goals: null,
    })
    getProfileMetrics.mockResolvedValue([
      { metric_name: 'savings_ratio', status: 'INCOMPLETE', value: null },
    ])

    render(<FinancialProfile />)
    await screen.findByRole('button', { name: 'Create profile' })

    fireEvent.change(labelInput('Monthly income'), { target: { value: '60000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))

    await waitFor(() => expect(createProfile).toHaveBeenCalled())
    // A blank field must be omitted from the payload, never sent as 0 —
    // Brick 05's "missing ≠ zero" rule applied at the UI layer too.
    const payload = createProfile.mock.calls[0][0]
    expect(payload.monthly_income).toBe('60000')
    expect(payload).not.toHaveProperty('fixed_expenses')

    expect(await screen.findByText('Saved and metrics recomputed.')).toBeInTheDocument()
    expect(await screen.findByText(/savings ratio/)).toBeInTheDocument()
  })

  it('shows a save error without losing the entered data', async () => {
    getProfile.mockRejectedValue(new ApiError('not found', { status: 404 }))
    createProfile.mockRejectedValue(new ApiError('income must be non-negative', { status: 422 }))

    render(<FinancialProfile />)
    await screen.findByRole('button', { name: 'Create profile' })
    fireEvent.change(labelInput('Monthly income'), { target: { value: '60000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('income must be non-negative')
    expect(labelInput('Monthly income').value).toBe('60000')
  })
})
