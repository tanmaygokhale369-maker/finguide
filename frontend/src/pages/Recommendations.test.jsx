import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { Recommendations } from './Recommendations'

vi.mock('../api/client', async () => {
  const actual = await vi.importActual('../api/client')
  return {
    ...actual,
    listRecommendations: vi.fn(),
    generateRecommendations: vi.fn(),
    evaluatePendingRecommendations: vi.fn(),
    evaluateRecommendation: vi.fn(),
    getRecommendationExplanation: vi.fn(),
    presentRecommendation: vi.fn(),
    submitRecommendationFeedback: vi.fn(),
  }
})

import {
  listRecommendations,
  generateRecommendations,
  evaluatePendingRecommendations,
  evaluateRecommendation,
  getRecommendationExplanation,
  presentRecommendation,
  submitRecommendationFeedback,
} from '../api/client'

function renderPage() {
  return render(
    <MemoryRouter>
      <Recommendations />
    </MemoryRouter>,
  )
}

const CANDIDATE = {
  id: 'rec-1',
  category: 'emergency_fund',
  title: 'Build up your emergency fund',
  reason: 'Your emergency fund covers about 1 month of expenses.',
  state: 'candidate',
  suitability_status: null,
  confidence: '1.00',
}

const APPROVED = {
  id: 'rec-2',
  category: 'savings',
  title: 'Increase your savings rate',
  reason: "You're saving about 5% of your income.",
  state: 'approved',
  suitability_status: 'APPROVE',
  confidence: '1.00',
}

describe('Recommendations page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the empty state when there are no recommendations yet', async () => {
    listRecommendations.mockResolvedValue([])
    renderPage()
    expect(await screen.findByText(/No recommendations yet/)).toBeInTheDocument()
  })

  it('renders existing recommendations with the right status label', async () => {
    listRecommendations.mockResolvedValue([CANDIDATE, APPROVED])
    renderPage()
    expect(await screen.findByText('Build up your emergency fund')).toBeInTheDocument()
    expect(screen.getByText('Needs review')).toBeInTheDocument()
    expect(screen.getByText('Approved')).toBeInTheDocument()
  })

  it('shows a link to the profile page when generation finds no computed metrics', async () => {
    listRecommendations.mockResolvedValue([])
    generateRecommendations.mockResolvedValue({ context_status: 'NO_METRICS_COMPUTED', candidates: [], skipped: [] })
    renderPage()
    await screen.findByText(/No recommendations yet/)

    fireEvent.click(screen.getByRole('button', { name: 'Check for recommendations' }))

    // The notice text is split across sibling nodes by the <Link/> in the
    // middle of the sentence, so query the link directly by its own
    // accessible name rather than the surrounding paragraph's full text.
    const link = await screen.findByRole('link', { name: 'financial profile' })
    expect(link).toHaveAttribute('href', '/profile')
    expect(screen.getByText(/enough financial data/)).toBeInTheDocument()
  })

  it('generating candidates refetches and shows a summary notice', async () => {
    listRecommendations.mockResolvedValueOnce([]).mockResolvedValueOnce([CANDIDATE])
    generateRecommendations.mockResolvedValue({
      context_status: 'OK',
      candidates: [CANDIDATE],
      skipped: [
        { rule_id: 'low_savings_ratio', reason: 'threshold_not_met' },
        { rule_id: 'high_expense_to_income_ratio', reason: 'threshold_not_met' },
        { rule_id: 'high_debt_to_income_ratio', reason: 'metric_incomplete' },
      ],
    })

    renderPage()
    await screen.findByText(/No recommendations yet/)
    fireEvent.click(screen.getByRole('button', { name: 'Check for recommendations' }))

    expect(await screen.findByText('Checked 4 rules — 1 triggered.')).toBeInTheDocument()
    expect(await screen.findByText('Build up your emergency fund')).toBeInTheDocument()
  })

  it('reviewing a single candidate calls evaluate and refreshes the list', async () => {
    listRecommendations
      .mockResolvedValueOnce([CANDIDATE])
      .mockResolvedValueOnce([{ ...CANDIDATE, state: 'approved', suitability_status: 'APPROVE' }])
    evaluateRecommendation.mockResolvedValue({
      recommendation_id: 'rec-1',
      decision: 'APPROVE',
      state: 'approved',
    })

    renderPage()
    await screen.findByText('Needs review')
    fireEvent.click(screen.getByRole('button', { name: 'Review' }))

    await waitFor(() => expect(evaluateRecommendation).toHaveBeenCalledWith('rec-1'))
    expect(await screen.findByText('Approved')).toBeInTheDocument()
  })

  it('"Review all pending" is hidden when no candidate is present', async () => {
    listRecommendations.mockResolvedValue([APPROVED])
    renderPage()
    await screen.findByText('Increase your savings rate')
    expect(screen.queryByRole('button', { name: /Review all pending/ })).not.toBeInTheDocument()
  })

  it('"Review all pending" calls evaluate-pending and refreshes the whole list', async () => {
    listRecommendations
      .mockResolvedValueOnce([CANDIDATE])
      .mockResolvedValueOnce([{ ...CANDIDATE, state: 'approved', suitability_status: 'APPROVE' }])
    evaluatePendingRecommendations.mockResolvedValue([
      { recommendation_id: 'rec-1', decision: 'APPROVE', state: 'approved' },
    ])

    renderPage()
    await screen.findByText('Needs review')
    fireEvent.click(screen.getByRole('button', { name: 'Review all pending' }))

    await waitFor(() => expect(evaluatePendingRecommendations).toHaveBeenCalled())
    expect(await screen.findByText('Approved')).toBeInTheDocument()
    // Bulk review must not call the single-item endpoint.
    expect(evaluateRecommendation).not.toHaveBeenCalled()
  })

  it('requires presentation before offering feedback and records the user choice', async () => {
    listRecommendations
      .mockResolvedValueOnce([APPROVED])
      .mockResolvedValueOnce([{ ...APPROVED, state: 'presented' }])
      .mockResolvedValueOnce([{ ...APPROVED, state: 'evaluated' }])
    presentRecommendation.mockResolvedValue({ state: 'presented' })
    submitRecommendationFeedback.mockResolvedValue({ action: 'accepted' })

    renderPage()
    await screen.findByText('Increase your savings rate')
    fireEvent.click(screen.getByRole('button', { name: 'Present to me' }))
    expect(await screen.findByRole('button', { name: 'Accept & helpful' })).toBeInTheDocument()
    expect(presentRecommendation).toHaveBeenCalledWith('rec-2')
    fireEvent.click(screen.getByRole('button', { name: 'Accept & helpful' }))
    await waitFor(() => expect(submitRecommendationFeedback).toHaveBeenCalledWith('rec-2', { action: 'accepted', rating: 'helpful' }))
    expect(await screen.findByText('Approved')).toBeInTheDocument()
  })

  it('expanding a card lazily fetches and displays its explanation', async () => {
    listRecommendations.mockResolvedValue([CANDIDATE])
    getRecommendationExplanation.mockResolvedValue({
      recommendation_id: 'rec-1',
      what: CANDIDATE.title,
      why: CANDIDATE.reason,
      user_data_used: {
        metric_name: 'emergency_fund_coverage_months',
        metric_value: '1.00',
        formula: 'emergency_fund_amount / (fixed_expenses + variable_expenses)',
      },
      external_evidence: [],
      assumptions: ['Uses a 3-month expense coverage threshold.'],
      confidence: '1.00',
      confidence_note: 'This is a deterministic threshold rule.',
      limitations: ['Safety review has not yet passed for this candidate.'],
    })

    renderPage()
    await screen.findByText('Build up your emergency fund')
    fireEvent.click(screen.getByRole('button', { name: 'Why am I seeing this?' }))

    expect(await screen.findByText(/emergency fund coverage months/)).toBeInTheDocument()
    expect(screen.getByText(/Uses a 3-month expense coverage threshold/)).toBeInTheDocument()
    expect(getRecommendationExplanation).toHaveBeenCalledTimes(1)

    // Collapsing and re-expanding must NOT refetch — it's cached.
    fireEvent.click(screen.getByRole('button', { name: 'Hide details' }))
    fireEvent.click(screen.getByRole('button', { name: 'Why am I seeing this?' }))
    expect(getRecommendationExplanation).toHaveBeenCalledTimes(1)
  })

  it('shows an inline error if generation itself fails, without crashing the page', async () => {
    listRecommendations.mockResolvedValue([])
    generateRecommendations.mockRejectedValue(new Error('backend unreachable'))
    renderPage()
    await screen.findByText(/No recommendations yet/)
    fireEvent.click(screen.getByRole('button', { name: 'Check for recommendations' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('backend unreachable')
  })
})
